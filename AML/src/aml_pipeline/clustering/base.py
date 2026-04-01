"""
Abstraction layer for blockchain-type-specific clustering.

Designed so UTXO-based chains (Bitcoin) can be plugged in later
without touching the clustering engine or heuristics.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class TxRecord:
    """Normalised transaction record — same shape for ETH and future UTXO chains."""
    tx_hash: str
    block_number: int
    timestamp: float          # unix epoch seconds
    from_address: str         # empty string for coinbase / UTXO inputs with no sender
    to_address: str           # empty string for OP_RETURN / unspendable outputs
    value_eth: float
    is_contract_call: bool = False
    input_method_id: str = ""  # first 4 bytes of calldata, e.g. "0xa9059cbb"
    gas_used: int = 0


@dataclass
class AddressNode:
    """Lightweight address metadata used by the graph builder."""
    address: str
    blockchain: str = "ethereum"
    extra: dict = field(default_factory=dict)


class BlockchainAdapter(ABC):
    """
    Interface every blockchain type must implement.

    Ethereum: reads from MongoDB raw_transactions / processed_transactions.
    Bitcoin (future): reads from UTXO set / raw block store.
    """

    @property
    @abstractmethod
    def blockchain_type(self) -> str:
        """Return 'account' or 'utxo'."""

    @abstractmethod
    def iter_transactions(self, **kwargs) -> Iterator[TxRecord]:
        """Yield normalised TxRecord objects from the data source."""
