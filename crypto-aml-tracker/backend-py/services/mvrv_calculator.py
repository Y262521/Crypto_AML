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
Historical prices: CoinGecko /market_chart, cached in token_price_history table.
"""

import asyncio
import os
from collections import deque
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
# Set of symbols whose data has been fully loaded into memory (from DB or CoinGecko).
# Once a symbol is in this set, we NEVER call CoinGecko again during this process run.
_HIST_CACHE_WARMED: set = set()

_CG_IDS = {
    "ETH":  "ethereum",
    "WETH": "weth",
    "USDT": "tether",
    "USDC": "usd-coin",
    "DAI":  "dai",
    "BUSD": "binance-usd",
}

# Symbols we track for historical prices (stablecoins excluded — always $1)
_PRICE_SYMBOLS = ["ETH", "WETH"]


async def _fetch_hist_prices_coingecko(symbol: str, days: int = 730) -> Dict[str, Decimal]:
    cg_id = _CG_IDS.get(symbol.upper())
    if not cg_id:
        return {}
    api_key = os.getenv("COINGECKO_API_KEY", "")
    url = f"https://api.coingecko.com/api/v3/coins/{cg_id}/market_chart"
    params = {"vs_currency": "usd", "days": str(days), "interval": "daily"}
    headers = {"x-cg-pro-api-key": api_key} if api_key else {}
    try:
        import ssl
        ssl_ctx = ssl.create_default_context()
        try:
            import certifi
            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=30)) as s:
            async with s.get(url, params=params, headers=headers) as resp:
                if resp.status != 200:
                    print(f"  CoinGecko hist {symbol}: HTTP {resp.status}")
                    return {}
                data = await resp.json()
                out: Dict[str, Decimal] = {}
                for ts_ms, price in data.get("prices", []):
                    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
                    out[dt.strftime("%Y-%m-%d")] = Decimal(str(price))
                print(f"  ✓ CoinGecko hist {symbol}: {len(out)} days")
                return out
    except Exception as exc:
        print(f"  CoinGecko hist {symbol} error: {exc}")
        return {}


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


async def _fetch_current_price_fallback(symbol: str) -> Optional[Decimal]:
    """Fetch today's price from CoinGecko simple/price endpoint as a fallback."""
    cg_id = _CG_IDS.get(symbol.upper())
    if not cg_id:
        return None
    api_key = os.getenv("COINGECKO_API_KEY", "")
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {"ids": cg_id, "vs_currencies": "usd"}
    headers = {"x-cg-pro-api-key": api_key} if api_key else {}
    try:
        import ssl
        ssl_ctx = ssl.create_default_context()
        try:
            import certifi
            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=15)) as s:
            async with s.get(url, params=params, headers=headers) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                price = data.get(cg_id, {}).get("usd")
                return Decimal(str(price)) if price else None
    except Exception as exc:
        print(f"  fallback price {symbol} error: {exc}")
        return None


async def _seed_prices_for_all_tx_dates(symbol: str, current_price: Decimal):
    """
    Seed token_price_history with current_price for every date that appears
    in the transactions table. This makes MVRV work without historical data.
    """
    rows = await fetch_all(
        "SELECT DISTINCT DATE(timestamp) AS d FROM transactions WHERE timestamp IS NOT NULL"
    ) or []
    if not rows:
        return None
    prices = {str(r["d"]): current_price for r in rows}
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    prices[today] = current_price
    await _save_hist_prices_to_db(symbol, prices)
    print(f"  ✓ {symbol}: seeded {len(prices)} dates with price ${current_price:.2f}")
    return prices


async def warm_hist_price_cache():
    """
    Called ONCE at server startup.
    1. Load existing prices from DB into memory.
    2. Try CoinGecko historical endpoint (needs free API key for /market_chart).
    3. If that fails, seed all transaction dates with today's current price.
       This gives approximate MVRV (assumes constant price) but is never zero.
    """
    print("🌡  Warming historical price cache…")
    for sym in _PRICE_SYMBOLS:
        db_prices = await _load_hist_prices_from_db(sym)
        if db_prices:
            _HIST_PRICE_CACHE.setdefault(sym, {}).update(db_prices)
            print(f"  ✓ {sym}: {len(db_prices)} days loaded from DB")
        else:
            print(f"  ↓ {sym}: no DB data, fetching from CoinGecko…")
            fresh = await _fetch_hist_prices_coingecko(sym)
            if fresh:
                _HIST_PRICE_CACHE.setdefault(sym, {}).update(fresh)
                await _save_hist_prices_to_db(sym, fresh)
            else:
                print(f"  ↓ {sym}: CoinGecko hist unavailable, seeding from current price…")
                current = await _fetch_current_price_fallback(sym)
                if current and current > 0:
                    seeded = await _seed_prices_for_all_tx_dates(sym, current)
                    if seeded:
                        _HIST_PRICE_CACHE.setdefault(sym, {}).update(seeded)
                else:
                    print(f"  ✗ {sym}: all price sources failed")
        _HIST_CACHE_WARMED.add(sym)
    total = sum(len(v) for v in _HIST_PRICE_CACHE.values())
    print(f"✓ Historical price cache warm ({total} total entries)")


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
    Uses block_number + tx_hash for ordering (avoids dependency on auto-inc id).
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
        mvrv_ratio       = float(market_value_usd / realized_value_usd)
        unrealized_pnl_pct = float(unrealized_pnl_usd / realized_value_usd * 100)
    else:
        mvrv_ratio         = 1.0 if market_value_usd == 0 else 0.0
        unrealized_pnl_pct = 0.0

    return {
        "market_value_usd":    float(market_value_usd),
        "realized_value_usd":  float(realized_value_usd),
        "mvrv_ratio":          round(mvrv_ratio, 6),
        "unrealized_pnl_usd":  float(unrealized_pnl_usd),
        "unrealized_pnl_pct":  round(unrealized_pnl_pct, 4),
        "realized_pnl_usd":    float(realized_pnl_usd),
        "net_pnl_usd":         float(unrealized_pnl_usd + realized_pnl_usd),
        "cost_basis_per_token": cost_basis_per_token,
        "tx_count_in":         tx_in,
        "tx_count_out":        tx_out,
        "tx_count_total":      tx_in + tx_out,
        "accounting_method":   method,
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
    pool = get_pool()
    if not pool:
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
                    """,
                    (
                        entity_id, entity_type,
                        mvrv.get("accounting_method", "FIFO"),
                        mvrv["market_value_usd"],
                        mvrv["realized_value_usd"],
                        mvrv["mvrv_ratio"],
                        mvrv["unrealized_pnl_usd"],
                        mvrv["realized_pnl_usd"],
                    ),
                )
            await conn.commit()
    except Exception as exc:
        print(f"  save_mvrv_snapshot error: {exc}")


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
