"""
Balance Aggregator Service
Fetches on-chain balances for addresses and aggregates them into cluster portfolios.
Integrates with Alchemy/Infura for Ethereum RPC access.
"""

import os
import json
import asyncio
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
import aiohttp
from db.mysql import get_pool
import aiomysql

# Supported tokens (start with major ones)
SUPPORTED_TOKENS = {
    "ETH": {
        "symbol": "ETH",
        "contract": None,  # Native token
        "decimals": 18,
        "coingecko_id": "ethereum"
    },
    "WETH": {
        "symbol": "WETH",
        "contract": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "decimals": 18,
        "coingecko_id": "weth"
    },
    "USDT": {
        "symbol": "USDT",
        "contract": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "decimals": 6,
        "coingecko_id": "tether"
    },
    "USDC": {
        "symbol": "USDC",
        "contract": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "decimals": 6,
        "coingecko_id": "usd-coin"
    },
    "DAI": {
        "symbol": "DAI",
        "contract": "0x6B175474E89094C44Da98b954EedeAC495271d0F",
        "decimals": 18,
        "coingecko_id": "dai"
    }
}

STABLECOINS = {"USDT", "USDC", "DAI", "BUSD"}

# Stablecoin prices are always $1 — no oracle call needed
_STABLECOIN_PRICES = {sym: Decimal("1") for sym in STABLECOINS}

# Chainlink ETH/USD feed (Mainnet)
_CHAINLINK_ETH_USD = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
_LATEST_ROUND_DATA_SELECTOR = "0xfeaf968c"


def _collect_rpc_urls() -> List[str]:
    """
    Return the single Alchemy RPC URL from environment.
    Alchemy is the ONLY permitted blockchain data provider.
    No fallback URLs. No alternative providers.
    """
    url = (os.getenv("ALCHEMY_RPC") or "").strip()
    if not url or "/v2/demo" in url.lower():
        raise RuntimeError(
            "ALCHEMY_RPC is not configured or uses the demo key. "
            "Set ALCHEMY_RPC=https://eth-mainnet.g.alchemy.com/v2/<your-key> in .env"
        )
    return [url]


class BalanceAggregator:
    """Aggregates on-chain balances for addresses and clusters."""

    def __init__(self):
        self.rpc_urls = _collect_rpc_urls()
        preview = self.rpc_urls[0][:56] + "…" if len(self.rpc_urls[0]) > 56 else self.rpc_urls[0]
        print(f"🔗 Alchemy RPC: {preview}")
        # No CoinGecko key — pricing is oracle-only
        self.price_cache: Dict[str, Decimal] = {}
        self.price_cache_time = None

    async def _jsonrpc(self, payload: dict) -> Tuple[Optional[dict], Optional[str]]:
        """POST JSON-RPC to first endpoint that returns valid JSON with optional result or error object."""
        import ssl as _ssl
        ssl_ctx = _ssl.create_default_context()
        try:
            import certifi
            ssl_ctx = _ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = _ssl.CERT_NONE
        timeout = aiohttp.ClientTimeout(total=25)
        last_err: Optional[str] = None
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            for url in self.rpc_urls:
                try:
                    async with session.post(
                        url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    ) as resp:
                        text = await resp.text()
                        if resp.status == 429:
                            last_err = f"{url[:40]}…: HTTP 429"
                            continue
                        if resp.status != 200:
                            last_err = f"{url[:40]}…: HTTP {resp.status}"
                            continue
                        try:
                            data = json.loads(text)
                        except json.JSONDecodeError:
                            last_err = f"{url[:40]}…: non-JSON response"
                            continue
                        if not isinstance(data, dict):
                            last_err = f"{url[:40]}…: unexpected JSON shape"
                            continue
                        if data.get("error"):
                            last_err = f"RPC error: {data['error']}"
                            continue
                        return data, None
                except asyncio.TimeoutError:
                    last_err = "RPC timeout"
                    continue
                except Exception as exc:
                    last_err = str(exc)
                    continue
        return None, last_err
    
    async def fetch_eth_balance(self, address: str) -> Decimal:
        """Fetch ETH balance for an address via RPC."""
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_getBalance",
            "params": [address, "latest"],
            "id": 1,
        }
        data, err = await self._jsonrpc(payload)
        if err:
            print(f"  ✗ Error fetching ETH balance for {address}: {err}")
            return Decimal(0)
        try:
            if data and "result" in data:
                wei_balance = int(data["result"], 16)
                eth_balance = Decimal(wei_balance) / Decimal(10 ** 18)
                print(f"  ✓ ETH balance for {address[:10]}…: {eth_balance}")
                return eth_balance
        except Exception as e:
            print(f"  ✗ Error parsing ETH balance for {address}: {e}")
        return Decimal(0)
    
    async def fetch_erc20_balance(self, address: str, token_contract: str, decimals: int) -> Decimal:
        """Fetch ERC20 token balance via RPC."""
        function_sig = "0x70a08231"
        padded_address = address[2:].zfill(64)
        call_data = function_sig + padded_address
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{"to": token_contract, "data": call_data}, "latest"],
            "id": 1,
        }
        data, err = await self._jsonrpc(payload)
        if err:
            print(f"Error fetching ERC20 balance for {address} ({token_contract}): {err}")
            return Decimal(0)
        try:
            if data and "result" in data and data["result"] not in (None, "0x"):
                balance_wei = int(data["result"], 16)
                return Decimal(balance_wei) / Decimal(10 ** decimals)
        except Exception as e:
            print(f"Error parsing ERC20 balance for {address} ({token_contract}): {e}")
        return Decimal(0)
    
    async def fetch_token_prices(self) -> Dict[str, Decimal]:
        """
        Fetch current ETH/USD price from the Chainlink oracle via Alchemy.
        Stablecoins are always $1 — no oracle call needed.
        Caches for 5 minutes. No CoinGecko. No external market APIs.
        """
        now = datetime.now(timezone.utc)
        if self.price_cache_time and (now - self.price_cache_time).total_seconds() < 300:
            return self.price_cache

        print("💰 Fetching ETH/USD price from Chainlink oracle via Alchemy…")
        prices: Dict[str, Decimal] = {}

        # Stablecoins: always $1
        for sym in STABLECOINS:
            prices[sym] = Decimal("1")

        # ETH/WETH: query Chainlink oracle at latest block
        try:
            url = self.rpc_urls[0]
            import ssl as _ssl
            ssl_ctx = _ssl.create_default_context()
            try:
                import certifi
                ssl_ctx = _ssl.create_default_context(cafile=certifi.where())
            except ImportError:
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = _ssl.CERT_NONE

            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            async with aiohttp.ClientSession(connector=connector) as session:
                payload = {
                    "jsonrpc": "2.0",
                    "method": "eth_call",
                    "params": [
                        {"to": _CHAINLINK_ETH_USD, "data": _LATEST_ROUND_DATA_SELECTOR},
                        "latest",
                    ],
                    "id": 1,
                }
                async with session.post(
                    url, json=payload, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    body = await resp.json()
                    result = body.get("result")

            if result and result != "0x":
                raw = result.lstrip("0x")
                # Left-pad to 320 hex chars — Chainlink omits leading zeros on roundId
                padded = raw.zfill(320)
                if len(padded) >= 128:
                    answer_int = int(padded[64:128], 16)
                    if answer_int >= (1 << 255):
                        answer_int -= (1 << 256)
                    if answer_int > 0:
                        eth_price = Decimal(answer_int) / Decimal(10 ** 8)
                        # Sanity guard: reject obviously invalid prices
                        if Decimal("1") < eth_price < Decimal("1000000"):
                            prices["ETH"]  = eth_price
                            prices["WETH"] = eth_price
                            print(f"  ✓ ETH/WETH: ${eth_price:.2f} (Chainlink oracle)")
                        else:
                            print(f"  ✗ Chainlink price out of range: {eth_price}")
                    else:
                        print("  ✗ Chainlink returned non-positive answer")
                else:
                    print("  ✗ Chainlink response too short to decode")
            else:
                print("  ✗ Chainlink oracle returned empty result")

        except Exception as exc:
            print(f"  ✗ Chainlink price fetch error: {exc}")
            # Try loading from DB cache as last resort (still oracle data, just stale)
            cached = await self.load_prices_from_db()
            if cached.get("ETH", Decimal(0)) > 0:
                prices.update(cached)
                print("  ↩ Using stale oracle price from DB cache")

        if prices.get("ETH", Decimal(0)) > 0:
            self.price_cache = prices
            self.price_cache_time = now
            await self.save_prices_to_db(prices)

        return prices
    
    async def save_prices_to_db(self, prices: Dict[str, Decimal]):
        """Save token prices to database cache."""
        pool = get_pool()
        if not pool:
            return
        
        try:
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    for symbol, price in prices.items():
                        token_info = SUPPORTED_TOKENS.get(symbol)
                        if token_info:
                            await cur.execute(
                                """
                                INSERT INTO token_price_cache (token_symbol, token_contract, price_usd, updated_at)
                                VALUES (%s, %s, %s, NOW())
                                ON DUPLICATE KEY UPDATE price_usd = %s, updated_at = NOW()
                                """,
                                (symbol, token_info["contract"], float(price), float(price))
                            )
                    await conn.commit()
        except Exception as e:
            print(f"Error saving prices to DB: {e}")
    
    async def load_prices_from_db(self) -> Dict[str, Decimal]:
        """Load cached prices from database."""
        pool = get_pool()
        if not pool:
            return {symbol: Decimal(0) for symbol in SUPPORTED_TOKENS.keys()}
        
        try:
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(
                        """
                        SELECT token_symbol, price_usd
                        FROM token_price_cache
                        WHERE updated_at >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
                        """
                    )
                    rows = await cur.fetchall()
                    return {row["token_symbol"]: Decimal(str(row["price_usd"])) for row in rows}
        except Exception as e:
            print(f"Error loading prices from DB: {e}")
            return {symbol: Decimal(0) for symbol in SUPPORTED_TOKENS.keys()}
    
    async def fetch_address_balances(self, address: str) -> List[Dict]:
        """Fetch all token balances for a single address."""
        balances = []
        prices = await self.fetch_token_prices()
        
        # Fetch ETH balance
        eth_balance = await self.fetch_eth_balance(address)
        eth_price = prices.get("ETH", Decimal(0))
        balances.append({
            "address": address.lower(),
            "token_symbol": "ETH",
            "token_contract": "",
            "balance": eth_balance,
            "balance_usd": eth_balance * eth_price
        })
        
        # Fetch ERC20 balances
        for symbol, token_info in SUPPORTED_TOKENS.items():
            if symbol == "ETH":
                continue
            
            contract = token_info["contract"]
            decimals = token_info["decimals"]
            
            balance = await self.fetch_erc20_balance(address, contract, decimals)
            price = prices.get(symbol, Decimal(0))
            
            balances.append({
                "address": address.lower(),
                "token_symbol": symbol,
                "token_contract": contract.lower() if contract else "",
                "balance": balance,
                "balance_usd": balance * price
            })
        
        return balances
    
    async def save_balances_to_db(self, balances: List[Dict]):
        """Save address balances to database."""
        pool = get_pool()
        if not pool:
            return
        
        try:
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    for bal in balances:
                        tc = bal.get("token_contract") or ""
                        await cur.execute(
                            """
                            INSERT INTO wallet_balances 
                            (address, token_symbol, token_contract, balance, balance_usd, updated_at)
                            VALUES (%s, %s, %s, %s, %s, NOW())
                            ON DUPLICATE KEY UPDATE 
                                balance = %s, 
                                balance_usd = %s, 
                                updated_at = NOW()
                            """,
                            (
                                bal["address"],
                                bal["token_symbol"],
                                tc,
                                float(bal["balance"]),
                                float(bal["balance_usd"]),
                                float(bal["balance"]),
                                float(bal["balance_usd"])
                            )
                        )
                    await conn.commit()
        except Exception as e:
            print(f"Error saving balances to DB: {e}")
    
    async def aggregate_cluster_portfolio(self, cluster_id: str, addresses: List[str]):
        """
        Aggregate portfolio for a cluster from its member addresses.
        """
        pool = get_pool()
        if not pool or not addresses:
            return
        
        try:
            # Fetch balances for all addresses
            placeholders = ','.join(['%s'] * len(addresses))
            
            async with pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    # Aggregate balances
                    await cur.execute(
                        f"""
                        SELECT 
                            SUM(balance_usd) as total_value_usd,
                            SUM(CASE WHEN token_symbol IN ('ETH', 'WETH') THEN balance_usd ELSE 0 END) as eth_value_usd,
                            SUM(CASE WHEN token_symbol IN ('USDT', 'USDC', 'DAI', 'BUSD') THEN balance_usd ELSE 0 END) as stablecoin_value_usd,
                            COUNT(DISTINCT token_symbol) as token_count
                        FROM wallet_balances
                        WHERE address IN ({placeholders})
                        """,
                        tuple(addresses)
                    )
                    result = await cur.fetchone()
                    
                    if result:
                        # Save cluster portfolio
                        await cur.execute(
                            """
                            INSERT INTO cluster_portfolios 
                            (cluster_id, total_value_usd, eth_value_usd, stablecoin_value_usd, 
                             defi_exposure_usd, token_count, wallet_count, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                            ON DUPLICATE KEY UPDATE 
                                total_value_usd = %s,
                                eth_value_usd = %s,
                                stablecoin_value_usd = %s,
                                defi_exposure_usd = %s,
                                token_count = %s,
                                wallet_count = %s,
                                updated_at = NOW()
                            """,
                            (
                                cluster_id,
                                float(result["total_value_usd"] or 0),
                                float(result["eth_value_usd"] or 0),
                                float(result["stablecoin_value_usd"] or 0),
                                0,  # DeFi exposure - TODO
                                int(result["token_count"] or 0),
                                len(addresses),
                                float(result["total_value_usd"] or 0),
                                float(result["eth_value_usd"] or 0),
                                float(result["stablecoin_value_usd"] or 0),
                                0,
                                int(result["token_count"] or 0),
                                len(addresses)
                            )
                        )
                        
                        try:
                            await cur.execute(
                                """
                                INSERT INTO portfolio_history 
                                (entity_id, entity_type, total_value_usd, eth_value_usd, stablecoin_value_usd, snapshot_at)
                                VALUES (%s, 'cluster', %s, %s, %s, NOW())
                                """,
                                (
                                    cluster_id,
                                    float(result["total_value_usd"] or 0),
                                    float(result["eth_value_usd"] or 0),
                                    float(result["stablecoin_value_usd"] or 0)
                                )
                            )
                        except Exception as hist_e:
                            if getattr(hist_e, "args", [None])[0] != 1146:
                                print(f"Warning: cluster portfolio_history insert failed: {hist_e}")
                        
                        await conn.commit()
                        print(f"✓ Aggregated portfolio for cluster {cluster_id}: ${result['total_value_usd']:.2f}")
        
        except Exception as e:
            print(f"Error aggregating cluster portfolio: {e}")
    
    async def record_address_portfolio_snapshot(self, address: str, balances: List[Dict]):
        """Append a point-in-time row for address-level charts (best-effort)."""
        pool = get_pool()
        if not pool or not balances:
            return
        total = sum(float(b["balance_usd"]) for b in balances)
        eth_v = sum(
            float(b["balance_usd"])
            for b in balances
            if b["token_symbol"] in ("ETH", "WETH")
        )
        st_v = sum(
            float(b["balance_usd"])
            for b in balances
            if b["token_symbol"] in STABLECOINS
        )
        try:
            async with pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO portfolio_history
                        (entity_id, entity_type, total_value_usd, eth_value_usd, stablecoin_value_usd, snapshot_at)
                        VALUES (%s, 'address', %s, %s, %s, NOW())
                        """,
                        (address.lower(), total, eth_v, st_v),
                    )
                await conn.commit()
        except Exception as e:
            if getattr(e, "args", [None])[0] == 1146:
                print("portfolio_history table missing; restart backend to run ensure_mva_schema")
            else:
                print(f"Warning: address portfolio_history insert failed: {e}")

    async def update_address(self, address: str):
        """Update balances for a single address."""
        print(f"\n📊 Updating balances for {address}")
        balances = await self.fetch_address_balances(address)
        await self.save_balances_to_db(balances)
        await self.record_address_portfolio_snapshot(address, balances)
        
        # Show summary
        total_usd = sum(float(b['balance_usd']) for b in balances)
        print(f"✓ Updated balances for {address}: ${total_usd:.2f} total value")
    
    async def update_cluster(self, cluster_id: str, addresses: List[str]):
        """Update balances for all addresses in a cluster and aggregate."""
        # Update individual addresses
        tasks = [self.update_address(addr) for addr in addresses]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Aggregate cluster portfolio
        await self.aggregate_cluster_portfolio(cluster_id, addresses)


# Singleton instance
_aggregator = None

def get_aggregator() -> BalanceAggregator:
    """Get or create the balance aggregator singleton."""
    global _aggregator
    if _aggregator is None:
        _aggregator = BalanceAggregator()
    return _aggregator
