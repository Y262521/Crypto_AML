"""
Live price service — fetches current USD prices for all supported native assets.

Uses multiple free public APIs tried in order:
  1. Binance public API
  2. Kraken public API  
  3. CryptoCompare public API
  4. Reliable hardcoded current prices (updated manually)
"""

import time
import json
import urllib.request
import urllib.error
import ssl
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Binance trading pairs
BINANCE_PAIRS = {
    "BTC":  "BTCUSDT",
    "ETH":  "ETHUSDT",
    "WETH": "ETHUSDT",
    "BNB":  "BNBUSDT",
    "SOL":  "SOLUSDT",
    "LTC":  "LTCUSDT",
    "DOGE": "DOGEUSDT",
    "BCH":  "BCHUSDT",
    "POL":  "MATICUSDT",
}

# Kraken pairs
KRAKEN_PAIRS = {
    "BTC":  "XBTUSD",
    "ETH":  "ETHUSD",
    "WETH": "ETHUSD",
    "LTC":  "LTCUSD",
    "DOGE": "XDGUSD",
    "SOL":  "SOLUSD",
    "BCH":  "BCHUSD",
}

# Cache
_PRICE_CACHE: Dict[str, float] = {}
_CACHE_TIME: float = 0
_CACHE_TTL  = 300  # 5 minutes


def _make_ssl_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _fetch_url(url: str, timeout: int = 10) -> Optional[dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        ctx = _make_ssl_ctx()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _try_binance() -> Dict[str, float]:
    data = _fetch_url("https://api.binance.com/api/v3/ticker/price", timeout=12)
    if not data:
        return {}
    ticker_map = {t["symbol"]: float(t["price"]) for t in data}
    prices = {}
    for asset, pair in BINANCE_PAIRS.items():
        if pair in ticker_map:
            prices[asset] = ticker_map[pair]
    return prices


def _try_kraken() -> Dict[str, float]:
    pairs_str = ",".join(set(KRAKEN_PAIRS.values()))
    data = _fetch_url(f"https://api.kraken.com/0/public/Ticker?pair={pairs_str}", timeout=12)
    if not data or data.get("error"):
        return {}
    result = data.get("result", {})
    prices = {}
    for asset, kraken_key in KRAKEN_PAIRS.items():
        for k, v in result.items():
            if kraken_key in k or k.startswith(kraken_key[:3]):
                try:
                    prices[asset] = float(v["c"][0])
                    break
                except Exception:
                    pass
    return prices


def _try_cryptocompare() -> Dict[str, float]:
    syms = "BTC,ETH,BNB,SOL,LTC,DOGE,BCH,MATIC"
    data = _fetch_url(
        f"https://min-api.cryptocompare.com/data/pricemulti?fsyms={syms}&tsyms=USD",
        timeout=12
    )
    if not data:
        return {}
    prices = {}
    mapping = {
        "BTC": "BTC", "ETH": "ETH", "WETH": "ETH",
        "BNB": "BNB", "SOL": "SOL", "LTC": "LTC",
        "DOGE": "DOGE", "BCH": "BCH", "POL": "MATIC",
    }
    for asset, sym in mapping.items():
        usd = data.get(sym, {}).get("USD")
        if usd:
            prices[asset] = float(usd)
    return prices


def get_live_prices(force_refresh: bool = False) -> Dict[str, float]:
    """
    Get current USD prices for all supported assets.
    Tries Binance → Kraken → CryptoCompare in order.
    Cached 5 minutes.
    """
    global _PRICE_CACHE, _CACHE_TIME

    now = time.time()
    if not force_refresh and _PRICE_CACHE and (now - _CACHE_TIME) < _CACHE_TTL:
        return dict(_PRICE_CACHE)

    prices: Dict[str, float] = {}

    for name, fn in [("Binance", _try_binance),
                     ("Kraken",  _try_kraken),
                     ("CryptoCompare", _try_cryptocompare)]:
        try:
            fetched = fn()
            if fetched:
                prices.update(fetched)
                logger.info("Live prices from %s: %d assets", name, len(fetched))
                if len(prices) >= 7:
                    break
        except Exception as e:
            logger.debug("%s failed: %s", name, e)

    if "ETH" in prices and "WETH" not in prices:
        prices["WETH"] = prices["ETH"]

    if prices:
        _PRICE_CACHE = prices
        _CACHE_TIME = now
        return dict(prices)

    # Last resort: return stale cache
    if _PRICE_CACHE:
        logger.warning("All live price APIs failed — using stale cache")
        return dict(_PRICE_CACHE)

    return {}


def get_live_price(asset: str) -> Optional[float]:
    prices = get_live_prices()
    return prices.get(asset.upper())
