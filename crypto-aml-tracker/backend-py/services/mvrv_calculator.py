"""
MVRV Calculator Service
=======================
Computes per-address and per-cluster MVRV (Market Value to Realized Value) ratios.

Definitions (EVM account-based model):
  Market Value (MV)    = current_price × current_balance
  Realized Value (RV)  = avg_cost_basis × current_balance
  MVRV Ratio           = MV / RV   (>1 profit, <1 loss)
  Unrealized PnL       = MV − RV
  Realized PnL         = Σ (exit_price − entry_price) × amount  for all outflows
  Net PnL              = Realized PnL + Unrealized PnL

Accounting methods supported: FIFO, LIFO, HIFO
Historical prices: Chainlink oracle via Alchemy, cached in token_price_history table.
Single source of truth: no CoinGecko, no fallback market APIs.
"""

import asyncio
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Literal, Optional

import aiohttp

from db.mysql import fetch_all, fetch_one, get_pool

AccountingMethod = Literal["FIFO", "LIFO", "HIFO"]

# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

async def _ensure_hist_price_schema():
    pool = get_pool()
    if not pool:
        return
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS token_price_history (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    token_symbol VARCHAR(20) NOT NULL,
                    price_date DATE NOT NULL,
                    price_usd DECIMAL(24,8) NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_token_date (token_symbol, price_date),
                    INDEX idx_symbol_date (token_symbol, price_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS mvrv_snapshots (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    entity_id VARCHAR(255) NOT NULL,
                    entity_type ENUM('address','cluster') NOT NULL,
                    accounting_method VARCHAR(8) NOT NULL DEFAULT 'FIFO',
                    market_value_usd DECIMAL(24,2) NOT NULL DEFAULT 0,
                    realized_value_usd DECIMAL(24,2) NOT NULL DEFAULT 0,
                    mvrv_ratio DECIMAL(12,6) NOT NULL DEFAULT 0,
                    unrealized_pnl_usd DECIMAL(24,2) NOT NULL DEFAULT 0,
                    realized_pnl_usd DECIMAL(24,2) NOT NULL DEFAULT 0,
                    snapshot_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_entity (entity_id, entity_type),
                    INDEX idx_snapshot_at (snapshot_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            # Add accounting_method column if it doesn't exist yet (migration)
            try:
                await cur.execute("""
                    ALTER TABLE mvrv_snapshots
                    ADD COLUMN IF NOT EXISTS accounting_method VARCHAR(8) NOT NULL DEFAULT 'FIFO'
                """)
            except Exception:
                pass
            await conn.commit()


# ---------------------------------------------------------------------------
# Historical price cache
# ---------------------------------------------------------------------------

_HIST_PRICE_CACHE: Dict[str, Dict[str, Decimal]] = {}
_HIST_CACHE_WARMED: set = set()

# Symbols we track for historical prices (stablecoins excluded — always $1)
_PRICE_SYMBOLS = ["ETH", "WETH"]

# ---------------------------------------------------------------------------
# Chainlink oracle — single source of truth for ETH/USD pricing
# Contract: 0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419 (Mainnet ETH/USD feed)
# ABI selector: latestRoundData() → (roundId, answer, startedAt, updatedAt, answeredInRound)
# answer is int256 with 8 decimal places (divide by 1e8 to get USD)
# ---------------------------------------------------------------------------

_CHAINLINK_ETH_USD = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
_LATEST_ROUND_DATA_SELECTOR = "0xfeaf968c"   # keccak256("latestRoundData()")[:4]
_BLOCKS_PER_DAY = 7150                        # post-Merge: 12s slots → 7200/day; 7150 is conservative


def _get_alchemy_url() -> str:
    """Return the configured Alchemy RPC URL. Raises if not set."""
    url = (os.getenv("ALCHEMY_RPC") or "").strip()
    if not url or "/v2/demo" in url.lower():
        raise RuntimeError(
            "ALCHEMY_RPC is not configured. "
            "Set ALCHEMY_RPC=https://eth-mainnet.g.alchemy.com/v2/<your-key> in .env"
        )
    return url


async def _eth_call_at_block(
    session: "aiohttp.ClientSession",
    url: str,
    contract: str,
    data: str,
    block_hex: str,
) -> Optional[str]:
    """Send a single eth_call at a specific block height. Returns raw hex result or None."""
    payload = {
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"to": contract, "data": data}, block_hex],
        "id": 1,
    }
    try:
        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                return None
            body = await resp.json()
            result = body.get("result")
            if not result or result == "0x":
                return None
            return result
    except Exception:
        return None


def _decode_chainlink_answer(hex_result: str) -> Optional[Decimal]:
    """
    Decode the latestRoundData() return value.
    Returns: (roundId, answer, startedAt, updatedAt, answeredInRound) — each 32 bytes.
    answer is at slot index 1 (bytes 32-63 of the ABI-encoded payload).

    IMPORTANT: The Chainlink contract may return a hex string shorter than 320 chars
    because leading zero bytes are omitted. We left-pad with zfill(320) before slicing
    to ensure correct slot alignment.

    answer is int256 with 8 decimal places → divide by 1e8 to get USD.
    Sanity check: valid ETH/USD price must be between $1 and $1,000,000.
    """
    try:
        raw = hex_result.lstrip("0x")
        if not raw:
            return None
        # Left-pad to exactly 320 hex chars (5 slots × 64 chars each)
        padded = raw.zfill(320)
        if len(padded) < 128:
            return None
        # answer is the second 32-byte slot (chars 64–127 of the padded string)
        answer_hex = padded[64:128]
        answer_int = int(answer_hex, 16)
        # Handle int256 sign (two's complement)
        if answer_int >= (1 << 255):
            answer_int -= (1 << 256)
        if answer_int <= 0:
            return None
        price = Decimal(answer_int) / Decimal(10 ** 8)
        # Sanity guard: reject obviously invalid prices
        if price <= 0 or price > Decimal("1000000"):
            return None
        return price
    except Exception:
        return None


async def _fetch_hist_prices_chainlink(days: int = 730) -> Dict[str, Decimal]:
    """
    Fetch historical daily ETH/USD prices from the Chainlink oracle via Alchemy archive node.

    Method:
      1. Get current head block via eth_blockNumber.
      2. For each of the past `days` days, subtract (day_index × 7150) blocks.
      3. Call latestRoundData() on the Chainlink ETH/USD feed at that block.
      4. Decode the answer (int256, 8 decimals) → USD price.
      5. Return Dict["YYYY-MM-DD" → Decimal].

    This is the ONLY pricing source. No fallbacks.
    """
    import ssl as _ssl
    try:
        url = _get_alchemy_url()
    except RuntimeError as exc:
        print(f"  ✗ Chainlink fetch skipped: {exc}")
        return {}

    ssl_ctx = _ssl.create_default_context()
    try:
        import certifi
        ssl_ctx = _ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = _ssl.CERT_NONE

    connector = aiohttp.TCPConnector(ssl=ssl_ctx)
    out: Dict[str, Decimal] = {}

    async with aiohttp.ClientSession(connector=connector) as session:
        # Step 1: get current head block
        try:
            async with session.post(
                url,
                json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                body = await resp.json()
                head_block = int(body["result"], 16)
        except Exception as exc:
            print(f"  ✗ Chainlink: could not fetch head block: {exc}")
            return {}

        print(f"  Chainlink: head block {head_block}, fetching {days} daily prices…")

        # Step 2: build (date_str, block_hex) pairs
        today = datetime.now(timezone.utc)
        targets = []
        for day_index in range(days):
            target_block = max(head_block - day_index * _BLOCKS_PER_DAY, 1)
            date = today.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            from datetime import timedelta
            date = date - timedelta(days=day_index)
            targets.append((date.strftime("%Y-%m-%d"), hex(target_block)))

        # Step 3: batch eth_call requests concurrently (50 at a time to avoid rate limits)
        BATCH = 50
        for i in range(0, len(targets), BATCH):
            batch = targets[i:i + BATCH]
            tasks = [
                _eth_call_at_block(
                    session, url, _CHAINLINK_ETH_USD,
                    _LATEST_ROUND_DATA_SELECTOR, block_hex
                )
                for _, block_hex in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for (date_str, _), result in zip(batch, results):
                if isinstance(result, Exception) or result is None:
                    continue
                price = _decode_chainlink_answer(result)
                if price and price > 0:
                    out[date_str] = price

            # Small pause between batches to respect Alchemy rate limits
            await asyncio.sleep(0.1)

    print(f"  ✓ Chainlink ETH/USD: {len(out)}/{days} days resolved")
    return out


async def _load_hist_prices_from_db(symbol: str) -> Dict[str, Decimal]:
    rows = await fetch_all(
        "SELECT price_date, price_usd FROM token_price_history WHERE token_symbol = %s",
        (symbol,),
    ) or []
    return {str(r["price_date"]): Decimal(str(r["price_usd"])) for r in rows}


async def _save_hist_prices_to_db(symbol: str, prices: Dict[str, Decimal]):
    pool = get_pool()
    if not pool or not prices:
        return
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                for date_str, price in prices.items():
                    await cur.execute(
                        "INSERT INTO token_price_history (token_symbol, price_date, price_usd) "
                        "VALUES (%s, %s, %s) "
                        "ON DUPLICATE KEY UPDATE price_usd = %s",
                        (symbol, date_str, float(price), float(price)),
                    )
            await conn.commit()
    except Exception as exc:
        print(f"  save hist prices error: {exc}")


async def _fetch_current_price_chainlink() -> Optional[Decimal]:
    """
    Fetch today's ETH/USD spot price from the Chainlink oracle at the latest block.
    Used only to seed today's date when the full historical fetch is not yet complete.
    No CoinGecko. No fallbacks.
    """
    import ssl as _ssl
    try:
        url = _get_alchemy_url()
    except RuntimeError:
        return None

    ssl_ctx = _ssl.create_default_context()
    try:
        import certifi
        ssl_ctx = _ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = _ssl.CERT_NONE

    connector = aiohttp.TCPConnector(ssl=ssl_ctx)
    async with aiohttp.ClientSession(connector=connector) as session:
        result = await _eth_call_at_block(
            session, url, _CHAINLINK_ETH_USD,
            _LATEST_ROUND_DATA_SELECTOR, "latest"
        )
    if result is None:
        return None
    return _decode_chainlink_answer(result)


async def warm_hist_price_cache():
    """
    Called ONCE at server startup.
    Single source of truth: Chainlink ETH/USD oracle via Alchemy archive node.
    No CoinGecko. No fallbacks. No external market APIs.

    Flow:
      1. Load existing prices from token_price_history DB table into memory.
      2. If DB is empty, fetch 730 days from Chainlink oracle and persist.
      3. If Chainlink fetch fails (Alchemy not configured), log a clear error.
         usd_at_execution will remain NULL until ALCHEMY_RPC is configured.
    """
    print("🌡  Warming historical price cache (Chainlink/Alchemy oracle)…")
    for sym in _PRICE_SYMBOLS:
        db_prices = await _load_hist_prices_from_db(sym)
        if db_prices:
            _HIST_PRICE_CACHE.setdefault(sym, {}).update(db_prices)
            print(f"  ✓ {sym}: {len(db_prices)} days loaded from DB (Chainlink oracle data)")
        else:
            print(f"  ↓ {sym}: no DB data, querying Chainlink oracle via Alchemy…")
            # ETH and WETH share the same Chainlink ETH/USD feed
            fresh = await _fetch_hist_prices_chainlink(days=730)
            if fresh:
                _HIST_PRICE_CACHE.setdefault(sym, {}).update(fresh)
                await _save_hist_prices_to_db(sym, fresh)
                print(f"  ✓ {sym}: {len(fresh)} days fetched from Chainlink and persisted")
            else:
                print(
                    f"  ✗ {sym}: Chainlink oracle fetch failed. "
                    "Ensure ALCHEMY_RPC is set in .env. "
                    "usd_at_execution will be NULL until prices are loaded."
                )
        _HIST_CACHE_WARMED.add(sym)
    total = sum(len(v) for v in _HIST_PRICE_CACHE.values())
    print(f"✓ Historical price cache warm ({total} total entries, source: Chainlink/Alchemy)")


async def get_hist_price(symbol: str, dt: datetime) -> Decimal:
    """
    USD price of `symbol` on the date of `dt`.
    Stablecoins always return 1.
    Never calls CoinGecko — relies entirely on the cache warmed at startup.
    """
    sym = symbol.upper()
    if sym in ("USDT", "USDC", "DAI", "BUSD"):
        return Decimal("1")

    date_str = dt.strftime("%Y-%m-%d")

    # Direct memory cache lookup — O(1), no I/O
    cached = _HIST_PRICE_CACHE.get(sym, {})
    if date_str in cached:
        return cached[date_str]

    # If cache wasn't warmed yet for this symbol (shouldn't happen after startup),
    # load from DB as a one-time fallback — still no CoinGecko call
    if sym not in _HIST_CACHE_WARMED:
        db_prices = await _load_hist_prices_from_db(sym)
        if db_prices:
            _HIST_PRICE_CACHE.setdefault(sym, {}).update(db_prices)
            _HIST_CACHE_WARMED.add(sym)
            if date_str in _HIST_PRICE_CACHE[sym]:
                return _HIST_PRICE_CACHE[sym][date_str]

    # Date not in cache — return 0 (caller will fall back to current price)
    return Decimal("0")


# ---------------------------------------------------------------------------
# Cost-basis engine — FIFO / LIFO / HIFO
# ---------------------------------------------------------------------------

class CostBasisTracker:
    """
    Tracks cost basis for a single (address, token) pair.
    Supports FIFO, LIFO, HIFO accounting methods.
    """

    def __init__(self, method: AccountingMethod = "FIFO"):
        self.method = method
        self._lots: List[List] = []          # [[amount, price_usd], ...]
        self.realized_pnl: Decimal = Decimal("0")
        self.total_received: Decimal = Decimal("0")
        self.total_sent: Decimal = Decimal("0")

    def receive(self, amount: Decimal, price_usd: Decimal):
        if amount <= 0:
            return
        self._lots.append([amount, price_usd])
        self.total_received += amount

    def send(self, amount: Decimal, price_usd: Decimal):
        if amount <= 0 or not self._lots:
            return
        remaining = amount
        self.total_sent += amount

        # Choose lot order based on method
        if self.method == "FIFO":
            indices = list(range(len(self._lots)))
        elif self.method == "LIFO":
            indices = list(range(len(self._lots) - 1, -1, -1))
        else:  # HIFO
            indices = sorted(range(len(self._lots)), key=lambda i: self._lots[i][1], reverse=True)

        consumed = []
        for i in indices:
            if remaining <= 0:
                break
            lot_amt, lot_price = self._lots[i]
            if lot_amt <= remaining:
                self.realized_pnl += lot_amt * (price_usd - lot_price)
                remaining -= lot_amt
                consumed.append(i)
            else:
                self.realized_pnl += remaining * (price_usd - lot_price)
                self._lots[i][0] -= remaining
                remaining = Decimal("0")

        # Remove fully consumed lots (in reverse order to preserve indices)
        for i in sorted(consumed, reverse=True):
            self._lots.pop(i)

    @property
    def current_balance(self) -> Decimal:
        return sum(lot[0] for lot in self._lots)

    @property
    def realized_value(self) -> Decimal:
        """Sum of (amount × cost_basis) for remaining lots."""
        return sum(lot[0] * lot[1] for lot in self._lots)

    @property
    def average_cost_basis(self) -> Decimal:
        bal = self.current_balance
        if bal <= 0:
            return Decimal("0")
        return self.realized_value / bal


# ---------------------------------------------------------------------------
# Transaction history fetch
# ---------------------------------------------------------------------------

TRACKED_TOKENS = {
    "ETH":  {"decimals": 18, "is_native": True},
    "WETH": {"decimals": 18, "contract": "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"},
    "USDT": {"decimals": 6,  "contract": "0xdac17f958d2ee523a2206206994597c13d831ec7"},
    "USDC": {"decimals": 6,  "contract": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"},
    "DAI":  {"decimals": 18, "contract": "0x6b175474e89094c44da98b954eedeac495271d0f"},
}


async def _get_address_tx_history(address: str) -> List[dict]:
    """
    Pull all ETH transactions for `address` from the local DB.
    Includes usd_at_execution (Chainlink oracle price at time of tx) for cost basis.
    """
    addr = address.lower()
    rows = await fetch_all(
        """
        SELECT
            tx_hash,
            LOWER(from_address) AS from_address,
            LOWER(to_address)   AS to_address,
            value_eth           AS amount,
            timestamp,
            block_number,
            usd_at_execution,
            'ETH'               AS token_symbol
        FROM transactions
        WHERE (LOWER(from_address) = %s OR LOWER(to_address) = %s)
          AND value_eth > 0
        ORDER BY block_number ASC, tx_hash ASC
        """,
        (addr, addr),
    ) or []
    return rows


# ---------------------------------------------------------------------------
# Core MVRV computation
# ---------------------------------------------------------------------------

async def compute_mvrv_for_address(
    address: str,
    current_prices: Dict[str, Decimal],
    current_balances: Dict[str, Decimal],
    method: AccountingMethod = "FIFO",
) -> dict:
    """
    Compute full MVRV metrics for a single address using the specified accounting method.
    """
    addr = address.lower()
    tx_rows = await _get_address_tx_history(addr)

    trackers: Dict[str, CostBasisTracker] = {
        sym: CostBasisTracker(method) for sym in TRACKED_TOKENS
    }

    tx_in = tx_out = 0

    for row in tx_rows:
        sym = (row.get("token_symbol") or "ETH").upper()
        if sym not in trackers:
            continue

        amount = Decimal(str(row.get("amount") or 0))
        if amount <= 0:
            continue

        # Price resolution priority:
        # 1. usd_at_execution — already Chainlink oracle price stored at transform time
        # 2. get_hist_price() — Chainlink oracle lookup by date
        # 3. current price — last resort for dates outside oracle window
        usd_exec = row.get("usd_at_execution")
        if usd_exec is not None and float(usd_exec) > 0:
            hist_price = Decimal(str(usd_exec)) / amount  # usd_at_execution = amount × price
        else:
            ts = row.get("timestamp")
            if ts is None:
                hist_price = current_prices.get(sym, Decimal("0"))
            else:
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except ValueError:
                        ts = datetime.now(timezone.utc)
                if getattr(ts, "tzinfo", None) is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                hist_price = await get_hist_price(sym, ts)
                if hist_price == 0:
                    hist_price = current_prices.get(sym, Decimal("0"))

        from_addr = (row.get("from_address") or "").lower()
        to_addr   = (row.get("to_address")   or "").lower()

        if to_addr == addr:
            trackers[sym].receive(amount, hist_price)
            tx_in += 1
        elif from_addr == addr:
            trackers[sym].send(amount, hist_price)
            tx_out += 1

    # Aggregate
    market_value_usd   = Decimal("0")
    realized_value_usd = Decimal("0")
    realized_pnl_usd   = Decimal("0")
    cost_basis_per_token: Dict[str, dict] = {}

    for sym, tracker in trackers.items():
        cur_price = current_prices.get(sym, Decimal("0"))
        cur_bal   = current_balances.get(sym, tracker.current_balance)

        mv = cur_bal * cur_price
        # If we have cost basis data use it; otherwise MV == RV (break-even)
        avg_cb = tracker.average_cost_basis
        rv = cur_bal * avg_cb if avg_cb > 0 else mv

        market_value_usd   += mv
        realized_value_usd += rv
        realized_pnl_usd   += tracker.realized_pnl

        if cur_bal > 0 or tracker.realized_pnl != 0:
            cost_basis_per_token[sym] = {
                "balance":            float(cur_bal),
                "current_price_usd":  float(cur_price),
                "avg_cost_basis_usd": float(avg_cb),
                "market_value_usd":   float(mv),
                "realized_value_usd": float(rv),
                "unrealized_pnl_usd": float(mv - rv),
                "realized_pnl_usd":   float(tracker.realized_pnl),
                "tx_in":              float(tracker.total_received),
                "tx_out":             float(tracker.total_sent),
            }

    unrealized_pnl_usd = market_value_usd - realized_value_usd
    if realized_value_usd > 0:
        mvrv_ratio         = float(market_value_usd / realized_value_usd)
        unrealized_pnl_pct = float(unrealized_pnl_usd / realized_value_usd * 100)
    else:
        mvrv_ratio         = 0.0   # 0 = no cost basis, NOT break-even
        unrealized_pnl_pct = 0.0

    # Determine cost basis completeness
    has_incoming = tx_in > 0
    cost_basis_available = has_incoming and realized_value_usd > 0

    return {
        "market_value_usd":      float(market_value_usd),
        "realized_value_usd":    float(realized_value_usd) if cost_basis_available else 0.0,
        "mvrv_ratio":            round(mvrv_ratio, 6),
        "unrealized_pnl_usd":    float(unrealized_pnl_usd) if cost_basis_available else 0.0,
        "unrealized_pnl_pct":    round(unrealized_pnl_pct, 4) if cost_basis_available else 0.0,
        "realized_pnl_usd":      float(realized_pnl_usd),
        "net_pnl_usd":           float(unrealized_pnl_usd + realized_pnl_usd) if cost_basis_available else float(realized_pnl_usd),
        "cost_basis_per_token":  cost_basis_per_token,
        "tx_count_in":           tx_in,
        "tx_count_out":          tx_out,
        "tx_count_total":        tx_in + tx_out,
        "accounting_method":     method,
        "cost_basis_available":  cost_basis_available,
        "history_complete":      cost_basis_available,
        "pricing_source":        "chainlink_oracle",
        "cost_basis_method":     method,
    }


async def compute_mvrv_for_cluster(
    cluster_id: str,
    addresses: List[str],
    current_prices: Dict[str, Decimal],
    current_balances_by_addr: Dict[str, Dict[str, Decimal]],
    method: AccountingMethod = "FIFO",
) -> dict:
    """Aggregate MVRV across all addresses in a cluster."""
    tasks = [
        compute_mvrv_for_address(
            addr, current_prices,
            current_balances_by_addr.get(addr.lower(), {}),
            method,
        )
        for addr in addresses
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    agg = {
        "market_value_usd":   0.0,
        "realized_value_usd": 0.0,
        "unrealized_pnl_usd": 0.0,
        "realized_pnl_usd":   0.0,
        "net_pnl_usd":        0.0,
        "tx_count_total":     0,
        "wallet_count":       len(addresses),
        "cost_basis_per_token": {},
        "accounting_method":  method,
    }

    for r in results:
        if isinstance(r, Exception):
            continue
        agg["market_value_usd"]   += r["market_value_usd"]
        agg["realized_value_usd"] += r["realized_value_usd"]
        agg["unrealized_pnl_usd"] += r["unrealized_pnl_usd"]
        agg["realized_pnl_usd"]   += r["realized_pnl_usd"]
        agg["net_pnl_usd"]        += r["net_pnl_usd"]
        agg["tx_count_total"]     += r["tx_count_total"]

    rv = agg["realized_value_usd"]
    mv = agg["market_value_usd"]
    agg["mvrv_ratio"]         = round(mv / rv, 6) if rv > 0 else (1.0 if mv == 0 else 0.0)
    agg["unrealized_pnl_pct"] = round(agg["unrealized_pnl_usd"] / rv * 100, 4) if rv > 0 else 0.0

    return agg


# ---------------------------------------------------------------------------
# Snapshot persistence & history
# ---------------------------------------------------------------------------

async def save_mvrv_snapshot(entity_id: str, entity_type: str, mvrv: dict):
    """
    Upsert the latest MVRV snapshot for an entity.
    Uses INSERT ... ON DUPLICATE KEY UPDATE so only one row per entity exists.
    Requires a UNIQUE KEY on (entity_id, entity_type) — added via migration below.
    """
    pool = get_pool()
    if not pool:
        return
    # Only save if we have a real market value
    if not mvrv.get("market_value_usd", 0):
        return
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO mvrv_snapshots
                        (entity_id, entity_type, accounting_method,
                         market_value_usd, realized_value_usd, mvrv_ratio,
                         unrealized_pnl_usd, realized_pnl_usd, snapshot_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE
                        accounting_method  = VALUES(accounting_method),
                        market_value_usd   = VALUES(market_value_usd),
                        realized_value_usd = VALUES(realized_value_usd),
                        mvrv_ratio         = VALUES(mvrv_ratio),
                        unrealized_pnl_usd = VALUES(unrealized_pnl_usd),
                        realized_pnl_usd   = VALUES(realized_pnl_usd),
                        snapshot_at        = NOW()
                    """,
                    (
                        entity_id, entity_type,
                        mvrv.get("accounting_method", "FIFO"),
                        mvrv["market_value_usd"],
                        mvrv.get("realized_value_usd", 0),
                        mvrv.get("mvrv_ratio", 0),
                        mvrv.get("unrealized_pnl_usd", 0),
                        mvrv.get("realized_pnl_usd", 0),
                    ),
                )
            await conn.commit()
    except Exception as exc:
        print(f"  save_mvrv_snapshot error: {exc}")


async def reconstruct_wallet_balances_from_txs(
    addresses: List[str],
    current_prices: Dict[str, Decimal],
) -> int:
    """
    Reconstruct wallet_balances for a list of addresses using local transaction data.
    No RPC calls — derives ETH balance as (total_in - total_out) from the transactions table.
    Writes to wallet_balances with balance_reconstructed=true marker via updated_at.

    Returns the number of addresses successfully reconstructed.
    """
    pool = get_pool()
    if not pool or not addresses:
        return 0

    eth_price = current_prices.get("ETH", Decimal("0"))
    if eth_price <= 0:
        return 0

    reconstructed = 0
    for addr in addresses:
        addr = addr.lower()
        try:
            # Compute net ETH from transaction history
            row = await fetch_one(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN LOWER(to_address)   = %s THEN value_eth ELSE 0 END), 0) AS total_in,
                    COALESCE(SUM(CASE WHEN LOWER(from_address) = %s THEN value_eth ELSE 0 END), 0) AS total_out
                FROM transactions
                WHERE (LOWER(from_address) = %s OR LOWER(to_address) = %s)
                  AND value_eth > 0
                """,
                (addr, addr, addr, addr),
            )
            if not row:
                continue

            total_in  = Decimal(str(row["total_in"]  or 0))
            total_out = Decimal(str(row["total_out"] or 0))
            net_eth   = max(total_in - total_out, Decimal("0"))

            if net_eth <= 0:
                continue

            balance_usd = net_eth * eth_price

            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO wallet_balances
                            (address, token_symbol, token_contract, balance, balance_usd, updated_at)
                        VALUES (%s, 'ETH', '', %s, %s, NOW())
                        ON DUPLICATE KEY UPDATE
                            balance     = %s,
                            balance_usd = %s,
                            updated_at  = NOW()
                        """,
                        (addr, float(net_eth), float(balance_usd),
                         float(net_eth), float(balance_usd)),
                    )
                await conn.commit()
            reconstructed += 1

        except Exception:
            continue

    return reconstructed


def _snapshot_status(mvrv: dict) -> str:
    """
    Derive a snapshot status string for forensic traceability.
    COMPLETE  — MV > 0, real cost basis available
    PARTIAL   — MV > 0, but no cost basis (only outgoing txs)
    EMPTY     — MV = 0 (no holdings)
    """
    mv = mvrv.get("market_value_usd", 0)
    if mv <= 0:
        return "EMPTY"
    if mvrv.get("cost_basis_available"):
        return "COMPLETE"
    return "PARTIAL"
    if not ts:
        return None
    if isinstance(ts, str):
        return ts
    if getattr(ts, "tzinfo", None) is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat()


def _fmt_ts(ts) -> Optional[str]:
    if not ts:
        return None
    if isinstance(ts, str):
        return ts
    if getattr(ts, "tzinfo", None) is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).isoformat()


async def get_mvrv_history(entity_id: str, entity_type: str, days: int = 30) -> List[dict]:
    rows = await fetch_all(
        """
        SELECT market_value_usd, realized_value_usd, mvrv_ratio,
               unrealized_pnl_usd, realized_pnl_usd, accounting_method, snapshot_at
        FROM mvrv_snapshots
        WHERE entity_id = %s AND entity_type = %s
          AND snapshot_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
        ORDER BY snapshot_at ASC
        """,
        (entity_id, entity_type, days),
    ) or []
    return [
        {
            "market_value_usd":   float(r["market_value_usd"]   or 0),
            "realized_value_usd": float(r["realized_value_usd"] or 0),
            "mvrv_ratio":         float(r["mvrv_ratio"]         or 0),
            "unrealized_pnl_usd": float(r["unrealized_pnl_usd"] or 0),
            "realized_pnl_usd":   float(r["realized_pnl_usd"]   or 0),
            "accounting_method":  r.get("accounting_method") or "FIFO",
            "timestamp":          _fmt_ts(r.get("snapshot_at")),
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Intelligence flags
# ---------------------------------------------------------------------------

def generate_mvrv_flags(mvrv: dict, assets: list) -> list:
    flags = []
    ratio    = mvrv.get("mvrv_ratio", 1.0)
    mv       = mvrv.get("market_value_usd", 0)
    rv       = mvrv.get("realized_value_usd", 0)
    upnl_pct = mvrv.get("unrealized_pnl_pct", 0)
    rpnl     = mvrv.get("realized_pnl_usd", 0)

    if rv > 100:
        if ratio > 3.0:
            flags.append({
                "type": "mvrv_extreme_profit", "severity": "warning",
                "label": "Extreme Unrealized Profit",
                "description": f"MVRV {ratio:.2f}× — holdings worth {ratio:.1f}× cost basis. Distribution risk.",
            })
        elif ratio > 1.5:
            flags.append({
                "type": "mvrv_profit", "severity": "info",
                "label": "Significant Unrealized Profit",
                "description": f"MVRV {ratio:.2f}× — position is {upnl_pct:.1f}% in profit.",
            })
        elif 0 < ratio < 0.7:
            flags.append({
                "type": "mvrv_deep_loss", "severity": "warning",
                "label": "Deep Unrealized Loss",
                "description": f"MVRV {ratio:.2f}× — holdings {abs(upnl_pct):.1f}% below cost basis.",
            })
        elif 0 < ratio < 1.0:
            flags.append({
                "type": "mvrv_underwater", "severity": "info",
                "label": "Underwater Position",
                "description": f"MVRV {ratio:.2f}× — average position is at a loss.",
            })

    if mv > 100_000:
        flags.append({
            "type": "high_value", "severity": "info",
            "label": "High Value Wallet",
            "description": f"Market value ${mv:,.0f} exceeds $100K.",
        })

    if rpnl > 50_000:
        flags.append({
            "type": "large_realized_profit", "severity": "warning",
            "label": "Large Realized Profit",
            "description": f"Realized PnL ${rpnl:,.0f} — significant profit-taking detected.",
        })

    stable_val = sum(
        a.get("market_value_usd", 0)
        for a in assets
        if a.get("token_symbol", "").upper() in ("USDT", "USDC", "DAI", "BUSD")
    )
    if mv > 0 and stable_val / mv > 0.7:
        flags.append({
            "type": "stablecoin_heavy", "severity": "warning",
            "label": "Stablecoin Heavy",
            "description": f"Stablecoins {stable_val/mv*100:.1f}% of portfolio — possible layering or exit.",
        })

    return flags
