"""
Abstraction layer for blockchain-type-specific clustering.

Designed so UTXO-based chains (Bitcoin) and account-based non-EVM chains
(Solana) can be plugged in without touching the clustering engine or
heuristics. Every record carries chain identity so the system can run
multi-chain analysis without mixing data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class TxRecord:
    """
    Normalised transaction record — same shape for all supported chains.

    Chain identity fields:
        chain_name      : canonical chain identifier (e.g. "ethereum", "bitcoin")
        chain_id        : numeric chain ID (EIP-155 for EVM; canonical for others)
        blockchain_type : "EVM" | "UTXO" | "ACCOUNT_BASED"
        native_asset    : native token symbol (e.g. "ETH", "BTC", "SOL")

    Value is always stored in native asset units in value_native.
    value_eth is kept for backward-compatibility but equals value_native
    for non-ETH chains (callers should use value_native going forward).
    """
    tx_hash: str
    block_number: int
    timestamp: float          # unix epoch seconds
    from_address: str         # empty string for coinbase / UTXO inputs with no sender
    to_address: str           # empty string for OP_RETURN / unspendable outputs
    value_eth: float          # kept for backward-compat; equals value_native
    value_native: float = 0.0 # value in chain's native asset
    is_contract_call: bool = False
    input_method_id: str = ""  # first 4 bytes of calldata, e.g. "0xa9059cbb"
    gas_used: int = 0
    status: int = 0
    # ── chain identity ────────────────────────────────────────────────────────
    chain_name: str = "ethereum"
    chain_id: int = 1
    blockchain_type: str = "EVM"
    native_asset: str = "ETH"

    def __post_init__(self) -> None:
        # Ensure value_native is always populated
        if self.value_native == 0.0 and self.value_eth != 0.0:
            self.value_native = self.value_eth


@dataclass
class AddressNode:
    """Lightweight address metadata used by the graph builder."""
    address: str
    blockchain: str = "ethereum"
    chain_id: int = 1
    blockchain_type: str = "EVM"
    native_asset: str = "ETH"
    extra: dict = field(default_factory=dict)


class BlockchainAdapter(ABC):
    """
    Interface every blockchain type must implement.

    Ethereum: reads from MariaDB processed transactions or MongoDB raw transactions.
    Bitcoin:  reads from UTXO set / raw block store.
    Solana:   reads from Solana account transaction history.

    Every adapter must declare which chain it serves via chain_name,
    chain_id, blockchain_type, and native_asset properties.
    """

    @property
    @abstractmethod
    def blockchain_type(self) -> str:
        """Return 'EVM', 'UTXO', or 'ACCOUNT_BASED'."""

    @property
    def chain_name(self) -> str:
        """Return the canonical chain name (e.g. 'ethereum')."""
        return "ethereum"

    @property
    def chain_id(self) -> int:
        """Return the numeric chain ID."""
        return 1

    @property
    def native_asset(self) -> str:
        """Return the native asset symbol (e.g. 'ETH')."""
        return "ETH"

    @abstractmethod
    def iter_transactions(self, **kwargs) -> Iterator[TxRecord]:
        """Yield normalised TxRecord objects from the data source."""
