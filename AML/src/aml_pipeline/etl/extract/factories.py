"""
Factory helpers to resolve the correct chain extractor.

EVM chains (ethereum, bnb, polygon, arbitrum, base):
    → EVMExtractor (generic, configurable)

UTXO chains (bitcoin, litecoin, dogecoin, bitcoin_cash):
    → UTXOExtractor (Phase 3)

Account-based chains (solana):
    → SolanaExtractor (Phase 4)
"""

from __future__ import annotations

from typing import Optional

from ...chains.registry import (
    EVM_CHAIN_NAMES,
    UTXO_CHAIN_NAMES,
    ACCOUNT_CHAIN_NAMES,
    get_chain,
)
from ...config import Config
from .base import BaseExtractor


def get_extractor(chain: str, cfg: Optional[Config] = None) -> BaseExtractor:
    """
    Return a chain-specific extractor instance by chain name.

    Supported EVM chains (all use EVMExtractor):
        ethereum, bnb, polygon, arbitrum, base

    UTXO chains (Phase 3):
        bitcoin, litecoin, dogecoin, bitcoin_cash

    Account-based (Phase 4):
        solana

    Raises ValueError for unknown chains.
    """
    chain = chain.lower().strip()

    # ── EVM chains ────────────────────────────────────────────────────────────
    if chain in EVM_CHAIN_NAMES or chain in {"eth", "binance", "bsc", "matic", "pol"}:
        # Normalize aliases
        _alias_map = {
            "eth":     "ethereum",
            "bsc":     "bnb",
            "binance": "bnb",
            "matic":   "polygon",
            "pol":     "polygon",
        }
        canonical = _alias_map.get(chain, chain)
        from .evm import EVMExtractor
        return EVMExtractor(cfg=cfg, chain=canonical)

    # ── UTXO chains ───────────────────────────────────────────────────────────
    if chain in UTXO_CHAIN_NAMES or chain in {"btc", "ltc", "doge", "bch"}:
        _alias_map = {
            "btc":  "bitcoin",
            "ltc":  "litecoin",
            "doge": "dogecoin",
            "bch":  "bitcoin_cash",
        }
        canonical = _alias_map.get(chain, chain)
        try:
            from .utxo import UTXOExtractor
            return UTXOExtractor(cfg=cfg, chain=canonical)
        except ImportError:
            raise NotImplementedError(
                f"UTXO extractor for {canonical!r} will be available in Phase 3. "
                "Install Phase 3 first."
            )

    # ── Account-based non-EVM ─────────────────────────────────────────────────
    if chain in ACCOUNT_CHAIN_NAMES or chain == "sol":
        canonical = "solana" if chain == "sol" else chain
        try:
            from .solana import SolanaExtractor
            return SolanaExtractor(cfg=cfg)
        except ImportError:
            raise NotImplementedError(
                f"Solana extractor requires Phase 4."
            )

    # ── Unknown ───────────────────────────────────────────────────────────────
    supported = sorted(
        list(EVM_CHAIN_NAMES) + list(UTXO_CHAIN_NAMES) + list(ACCOUNT_CHAIN_NAMES)
    )
    raise ValueError(
        f"Unsupported chain: {chain!r}. Supported: {supported}"
    )


def get_adapter(chain: str, cfg: Optional[Config] = None):
    """
    Return a clustering adapter for any supported chain.

    Used by the ClusteringEngine and AML analytics engines to read
    normalized TxRecord objects regardless of chain type.
    """
    chain = chain.lower().strip()

    _alias_map = {
        "eth":     "ethereum",
        "bsc":     "bnb",
        "binance": "bnb",
        "matic":   "polygon",
        "pol":     "polygon",
        "btc":     "bitcoin",
        "ltc":     "litecoin",
        "doge":    "dogecoin",
        "bch":     "bitcoin_cash",
        "sol":     "solana",
    }
    canonical = _alias_map.get(chain, chain)

    if canonical in EVM_CHAIN_NAMES:
        from ...clustering.evm_adapter import EVMAdapter
        return EVMAdapter(cfg=cfg, chain_name=canonical)

    if canonical in UTXO_CHAIN_NAMES:
        try:
            from ...clustering.utxo_adapter import UTXOAdapter
            return UTXOAdapter(cfg=cfg, chain_name=canonical)
        except ImportError:
            raise NotImplementedError(
                f"UTXO adapter for {canonical!r} requires Phase 3."
            )

    if canonical in ACCOUNT_CHAIN_NAMES:
        from ...clustering.solana_adapter import SolanaAdapter
        return SolanaAdapter(cfg=cfg)

    supported = sorted(
        list(EVM_CHAIN_NAMES) + list(UTXO_CHAIN_NAMES) + list(ACCOUNT_CHAIN_NAMES)
    )
    raise ValueError(f"Unsupported chain: {canonical!r}. Supported: {supported}")
