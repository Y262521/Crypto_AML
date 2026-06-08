"""
Chain Registry
==============
Single source of truth for every supported blockchain.

All chain metadata is defined here. No other module should hardcode
chain names, IDs, or types. Import from this module instead.

Supported chains:
  EVM    : ethereum, bnb, polygon, arbitrum, base
  UTXO   : bitcoin, litecoin, dogecoin, bitcoin_cash
  ACCOUNT: solana
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ── Blockchain type constants ─────────────────────────────────────────────────
BLOCKCHAIN_TYPE_EVM     = "EVM"
BLOCKCHAIN_TYPE_UTXO    = "UTXO"
BLOCKCHAIN_TYPE_ACCOUNT = "ACCOUNT_BASED"


@dataclass(frozen=True)
class ChainConfig:
    """Immutable metadata for a single blockchain."""

    # Unique short identifier used throughout the codebase
    chain_name: str

    # EIP-155 chain ID for EVM chains; canonical numeric ID for others
    chain_id: int

    # Human-readable display name
    display_name: str

    # Native asset symbol (used in value_native column labelling)
    native_asset: str

    # One of BLOCKCHAIN_TYPE_* constants
    blockchain_type: str

    # Alchemy network slug (used to build RPC URLs)
    alchemy_network: str

    # Default Alchemy RPC URL template (fill in your key)
    rpc_url_template: str

    # Whether this chain supports ERC-20 / token transfers
    supports_tokens: bool = True

    # Whether this chain has smart contracts
    supports_contracts: bool = True

    # High-value threshold in native asset units (for AML detection)
    high_value_threshold_native: float = 10.0

    # Extra metadata for chain-specific behaviour
    extra: Dict[str, object] = field(default_factory=dict)

    @property
    def is_evm(self) -> bool:
        return self.blockchain_type == BLOCKCHAIN_TYPE_EVM

    @property
    def is_utxo(self) -> bool:
        return self.blockchain_type == BLOCKCHAIN_TYPE_UTXO

    @property
    def is_account_based(self) -> bool:
        return self.blockchain_type == BLOCKCHAIN_TYPE_ACCOUNT

    def rpc_url(self, api_key: str) -> str:
        """Return the full Alchemy RPC URL with the provided API key."""
        return self.rpc_url_template.format(api_key=api_key)


# ── Chain definitions ─────────────────────────────────────────────────────────

_CHAIN_LIST: List[ChainConfig] = [
    # ── EVM chains ────────────────────────────────────────────────────────────
    ChainConfig(
        chain_name="ethereum",
        chain_id=1,
        display_name="Ethereum",
        native_asset="ETH",
        blockchain_type=BLOCKCHAIN_TYPE_EVM,
        alchemy_network="eth-mainnet",
        rpc_url_template="https://eth-mainnet.g.alchemy.com/v2/{api_key}",
        high_value_threshold_native=10.0,
    ),
    ChainConfig(
        chain_name="bnb",
        chain_id=56,
        display_name="BNB Chain",
        native_asset="BNB",
        blockchain_type=BLOCKCHAIN_TYPE_EVM,
        alchemy_network="bnb-mainnet",
        rpc_url_template="https://bnb-mainnet.g.alchemy.com/v2/{api_key}",
        high_value_threshold_native=30.0,  # ~10 ETH equivalent
    ),
    ChainConfig(
        chain_name="polygon",
        chain_id=137,
        display_name="Polygon",
        native_asset="POL",
        blockchain_type=BLOCKCHAIN_TYPE_EVM,
        alchemy_network="polygon-mainnet",
        rpc_url_template="https://polygon-mainnet.g.alchemy.com/v2/{api_key}",
        high_value_threshold_native=10000.0,
    ),
    ChainConfig(
        chain_name="arbitrum",
        chain_id=42161,
        display_name="Arbitrum",
        native_asset="ETH",
        blockchain_type=BLOCKCHAIN_TYPE_EVM,
        alchemy_network="arb-mainnet",
        rpc_url_template="https://arb-mainnet.g.alchemy.com/v2/{api_key}",
        high_value_threshold_native=10.0,
    ),
    ChainConfig(
        chain_name="base",
        chain_id=8453,
        display_name="Base",
        native_asset="ETH",
        blockchain_type=BLOCKCHAIN_TYPE_EVM,
        alchemy_network="base-mainnet",
        rpc_url_template="https://base-mainnet.g.alchemy.com/v2/{api_key}",
        high_value_threshold_native=10.0,
    ),
    # ── UTXO chains ───────────────────────────────────────────────────────────
    ChainConfig(
        chain_name="bitcoin",
        chain_id=0,          # BTC has no EIP-155 chain ID; use 0 by convention
        display_name="Bitcoin",
        native_asset="BTC",
        blockchain_type=BLOCKCHAIN_TYPE_UTXO,
        alchemy_network="btc-mainnet",
        rpc_url_template="https://btc-mainnet.g.alchemy.com/v2/{api_key}",
        supports_contracts=False,
        high_value_threshold_native=0.5,   # ~10 ETH equivalent
    ),
    ChainConfig(
        chain_name="litecoin",
        chain_id=2,
        display_name="Litecoin",
        native_asset="LTC",
        blockchain_type=BLOCKCHAIN_TYPE_UTXO,
        alchemy_network="ltc-mainnet",
        rpc_url_template="https://ltc-mainnet.g.alchemy.com/v2/{api_key}",
        supports_contracts=False,
        high_value_threshold_native=500.0,
    ),
    ChainConfig(
        chain_name="dogecoin",
        chain_id=3,
        display_name="Dogecoin",
        native_asset="DOGE",
        blockchain_type=BLOCKCHAIN_TYPE_UTXO,
        alchemy_network="doge-mainnet",
        rpc_url_template="https://doge-mainnet.g.alchemy.com/v2/{api_key}",
        supports_contracts=False,
        high_value_threshold_native=50000.0,
    ),
    ChainConfig(
        chain_name="bitcoin_cash",
        chain_id=145,
        display_name="Bitcoin Cash",
        native_asset="BCH",
        blockchain_type=BLOCKCHAIN_TYPE_UTXO,
        alchemy_network="bch-mainnet",
        rpc_url_template="https://bch-mainnet.g.alchemy.com/v2/{api_key}",
        supports_contracts=False,
        high_value_threshold_native=50.0,
    ),
    # ── Account-based non-EVM ─────────────────────────────────────────────────
    ChainConfig(
        chain_name="solana",
        chain_id=900,        # Unofficial; Solana has no EVM chain ID
        display_name="Solana",
        native_asset="SOL",
        blockchain_type=BLOCKCHAIN_TYPE_ACCOUNT,
        alchemy_network="solana-mainnet",
        rpc_url_template="https://solana-mainnet.g.alchemy.com/v2/{api_key}",
        high_value_threshold_native=150.0,  # ~10 ETH equivalent
    ),
]


# ── Registry class ────────────────────────────────────────────────────────────

class ChainRegistry:
    """
    Immutable registry of all supported chains.

    Access patterns:
        registry = get_registry()
        eth = registry.get("ethereum")
        all_evm = registry.evm_chains()
        all_utxo = registry.utxo_chains()
    """

    def __init__(self, chains: List[ChainConfig]) -> None:
        self._by_name: Dict[str, ChainConfig] = {c.chain_name: c for c in chains}
        self._by_chain_id: Dict[int, ChainConfig] = {c.chain_id: c for c in chains}

    def get(self, chain_name: str) -> Optional[ChainConfig]:
        """Return chain config by name (case-insensitive), or None."""
        return self._by_name.get(chain_name.lower().strip())

    def require(self, chain_name: str) -> ChainConfig:
        """Return chain config or raise ValueError if unknown."""
        cfg = self.get(chain_name)
        if cfg is None:
            supported = sorted(self._by_name.keys())
            raise ValueError(
                f"Unknown chain: {chain_name!r}. "
                f"Supported chains: {supported}"
            )
        return cfg

    def get_by_chain_id(self, chain_id: int) -> Optional[ChainConfig]:
        return self._by_chain_id.get(chain_id)

    def all_chains(self) -> List[ChainConfig]:
        return list(self._by_name.values())

    def evm_chains(self) -> List[ChainConfig]:
        return [c for c in self._by_name.values() if c.is_evm]

    def utxo_chains(self) -> List[ChainConfig]:
        return [c for c in self._by_name.values() if c.is_utxo]

    def account_based_chains(self) -> List[ChainConfig]:
        return [c for c in self._by_name.values() if c.is_account_based]

    def chain_names(self) -> List[str]:
        return sorted(self._by_name.keys())

    def chain_ids(self) -> Dict[str, int]:
        """Return {chain_name: chain_id} mapping."""
        return {name: cfg.chain_id for name, cfg in self._by_name.items()}

    def __contains__(self, chain_name: str) -> bool:
        return chain_name.lower().strip() in self._by_name

    def __repr__(self) -> str:
        return f"ChainRegistry({self.chain_names()})"


# ── Module-level singleton ────────────────────────────────────────────────────

_REGISTRY: Optional[ChainRegistry] = None


def get_registry() -> ChainRegistry:
    """Return the global ChainRegistry singleton."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = ChainRegistry(_CHAIN_LIST)
    return _REGISTRY


def get_chain(chain_name: str) -> ChainConfig:
    """Convenience shortcut: get a ChainConfig by name or raise."""
    return get_registry().require(chain_name)


# ── Convenience sets used throughout the codebase ────────────────────────────

EVM_CHAIN_NAMES = frozenset(c.chain_name for c in _CHAIN_LIST if c.blockchain_type == BLOCKCHAIN_TYPE_EVM)
UTXO_CHAIN_NAMES = frozenset(c.chain_name for c in _CHAIN_LIST if c.blockchain_type == BLOCKCHAIN_TYPE_UTXO)
ACCOUNT_CHAIN_NAMES = frozenset(c.chain_name for c in _CHAIN_LIST if c.blockchain_type == BLOCKCHAIN_TYPE_ACCOUNT)
ALL_CHAIN_NAMES = frozenset(c.chain_name for c in _CHAIN_LIST)
