"""
Ethereum blockchain adapter.

Reads from the AML pipeline's MongoDB collections in priority order:
  1. processed_transactions  (richest data, post-transform)
  2. raw_transactions        (flat pre-transform docs)
Falls back to the processed CSV on disk when MongoDB is unavailable.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator, Optional

import pandas as pd
from pymongo import MongoClient

from ..config import Config, load_config
from .base import BlockchainAdapter, TxRecord

logger = logging.getLogger(__name__)

# ERC-20 transfer / transferFrom method IDs
_ERC20_METHOD_IDS = {"0xa9059cbb", "0x23b872dd"}


def _to_float(value) -> float:
    if value is None:
        return 0.0
    try:
        # Handle pymongo Decimal128
        if hasattr(value, "to_decimal"):
            return float(value.to_decimal())
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value) -> int:
    if value is None:
        return 0
    try:
        if isinstance(value, str) and value.startswith("0x"):
            return int(value, 16)
        return int(value)
    except (TypeError, ValueError):
        return 0


def _to_ts(value) -> float:
    """Convert any timestamp representation to a unix float."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if hasattr(value, "timestamp"):          # datetime
        return value.timestamp()
    if isinstance(value, str):
        if value.isdigit():
            return float(value)
        try:
            import datetime
            return datetime.datetime.fromisoformat(
                value.replace("Z", "+00:00")
            ).timestamp()
        except ValueError:
            pass
    return 0.0


class EthereumAdapter(BlockchainAdapter):
    """Reads Ethereum transactions from MongoDB and yields TxRecord objects."""

    def __init__(self, cfg: Optional[Config] = None):
        self.cfg = cfg or load_config()

    @property
    def blockchain_type(self) -> str:
        return "account"

    # ── internal readers ────────────────────────────────────────────────────

    def _iter_from_processed_mongo(self) -> Iterator[TxRecord]:
        client = MongoClient(self.cfg.mongo_uri)
        col = client[self.cfg.mongo_processed_db][self.cfg.mongo_processed_collection]
        for doc in col.find({}, {"_id": 0}).sort("block_number", 1):
            frm = (doc.get("from_address") or "").lower().strip()
            to = (doc.get("to_address") or "").lower().strip()
            if not frm and not to:
                continue
            inp = (doc.get("input_data") or "")
            method_id = inp[:10] if inp.startswith("0x") and len(inp) >= 10 else ""
            yield TxRecord(
                tx_hash=doc.get("tx_hash", ""),
                block_number=_to_int(doc.get("block_number")),
                timestamp=_to_ts(doc.get("timestamp")),
                from_address=frm,
                to_address=to,
                value_eth=_to_float(doc.get("value_eth")),
                is_contract_call=bool(doc.get("is_contract_call")),
                input_method_id=method_id,
                gas_used=_to_int(doc.get("gas_used")),
            )
        client.close()

    def _iter_from_raw_mongo(self) -> Iterator[TxRecord]:
        client = MongoClient(self.cfg.mongo_uri)
        col = client[self.cfg.mongo_flat_tx_db][self.cfg.mongo_flat_tx_collection]
        for doc in col.find({}, {"_id": 0}).sort("block.number", 1):
            block = doc.get("block", {})
            ap = doc.get("address_pair", {})
            val = doc.get("value", {})
            forensics = doc.get("forensics", {})
            frm = (ap.get("from") or "").lower().strip()
            to = (ap.get("to") or "").lower().strip()
            if not frm and not to:
                continue
            inp = (forensics.get("input_data") or "")
            method_id = inp[:10] if inp.startswith("0x") and len(inp) >= 10 else ""
            yield TxRecord(
                tx_hash=doc.get("tx_hash", ""),
                block_number=_to_int(block.get("number")),
                timestamp=_to_ts(block.get("timestamp")),
                from_address=frm,
                to_address=to,
                value_eth=_to_float(val.get("eth")),
                is_contract_call=bool(forensics.get("is_contract")),
                input_method_id=method_id,
                gas_used=_to_int(doc.get("gas", {}).get("gas_used")),
            )
        client.close()

    def _iter_from_csv(self) -> Iterator[TxRecord]:
        csv_path: Path = self.cfg.processed_dir / "transactions.csv"
        if not csv_path.exists():
            logger.warning("transactions.csv not found at %s", csv_path)
            return
        # FIX: use itertuples() instead of iterrows() — ~10x faster for large CSVs
        for chunk in pd.read_csv(csv_path, chunksize=5000):
            for row in chunk.itertuples(index=False):
                frm = str(getattr(row, "from_address", "") or "").lower().strip()
                to = str(getattr(row, "to_address", "") or "").lower().strip()
                if not frm and not to:
                    continue
                inp = str(getattr(row, "input_data", "") or "")
                method_id = inp[:10] if inp.startswith("0x") and len(inp) >= 10 else ""
                yield TxRecord(
                    tx_hash=str(getattr(row, "tx_hash", "")),
                    block_number=int(getattr(row, "block_number", 0) or 0),
                    timestamp=_to_ts(getattr(row, "timestamp", None)),
                    from_address=frm,
                    to_address=to,
                    value_eth=_to_float(getattr(row, "value_eth", 0.0)),
                    is_contract_call=bool(getattr(row, "is_contract_call", False)),
                    input_method_id=method_id,
                    gas_used=int(getattr(row, "gas_used", 0) or 0),
                )

    # ── public interface ─────────────────────────────────────────────────────

    def iter_transactions(self, source: str = "auto", **kwargs) -> Iterator[TxRecord]:
        """
        Yield TxRecord objects.

        source: 'auto' | 'processed' | 'raw' | 'csv'
          auto → tries processed_mongo → raw_mongo → csv
        """
        if source == "processed":
            yield from self._iter_from_processed_mongo()
            return
        if source == "raw":
            yield from self._iter_from_raw_mongo()
            return
        if source == "csv":
            yield from self._iter_from_csv()
            return

        # auto: try each source in order, fall back on empty
        client = MongoClient(self.cfg.mongo_uri)
        try:
            processed_count = client[self.cfg.mongo_processed_db][
                self.cfg.mongo_processed_collection
            ].estimated_document_count()
            raw_count = client[self.cfg.mongo_flat_tx_db][
                self.cfg.mongo_flat_tx_collection
            ].estimated_document_count()
        finally:
            client.close()

        if processed_count > 0:
            logger.info("EthereumAdapter: reading %d processed transactions", processed_count)
            yield from self._iter_from_processed_mongo()
        elif raw_count > 0:
            logger.info("EthereumAdapter: reading %d raw transactions", raw_count)
            yield from self._iter_from_raw_mongo()
        else:
            logger.info("EthereumAdapter: falling back to CSV")
            yield from self._iter_from_csv()
