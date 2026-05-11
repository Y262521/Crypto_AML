from __future__ import annotations

from typing import Any

from blockchain_engine.indexer import SqliteIndexer
from blockchain_engine.models import NormalizedTransaction


class ExplorerService:
    def __init__(self, indexer: SqliteIndexer) -> None:
        self.indexer = indexer

    def get_address_transactions(self, chain: str, address: str, limit: int = 25) -> list[dict[str, Any]]:
        return self.indexer.read_by_address(chain=chain, address=address, limit=limit)

    def get_transaction(self, tx_hash: str) -> dict[str, Any] | None:
        return self.indexer.read_by_tx_hash(tx_hash)

    def summarize_address(self, chain: str, address: str, balance: float, transactions: list[dict[str, Any]]) -> dict[str, Any]:
        stats = self.indexer.get_address_stats(chain=chain, address=address)
        return {
            "balance": balance,
            "transaction_count": stats["transaction_count"],
            "incoming_total": stats["incoming_total"],
            "outgoing_total": stats["outgoing_total"],
            "transactions": transactions,
        }
