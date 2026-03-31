"""Factory helpers to resolve the correct chain extractor."""

from .base import BaseExtractor
from .bsc import BscExtractor
from .btc import BitcoinExtractor
from .eth import EthereumExtractor
from .tron import TronExtractor


def get_extractor(chain: str, cfg=None) -> BaseExtractor:
    """Return a chain-specific extractor instance."""
    chain = chain.lower()
    if chain in {"ethereum", "eth"}:
        return EthereumExtractor(cfg)
    if chain in {"bitcoin", "btc"}:
        return BitcoinExtractor(cfg)
    if chain in {"bsc", "binance", "binance-smart-chain"}:
        return BscExtractor(cfg)
    if chain in {"tron", "trx"}:
        return TronExtractor(cfg)
    raise ValueError(f"Unsupported chain: {chain}")
