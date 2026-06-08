"""
Generic EVM Blockchain Adapter
================================
Reads transactions for any EVM chain from MariaDB (or MongoDB fallback)
and yields chain-tagged TxRecord objects.

Reuses all existing EthereumAdapter logic — the only difference is which
chain_name filter is applied when reading from MariaDB.

Usage:
    from aml_pipeline.clustering.evm_adapter import EVMAdapter
    adapter = EVMAdapter(cfg, chain_name="bnb")
    for tx in adapter.iter_transactions():
        ...

Supports:
    ethereum, bnb, polygon, arbitrum, base
    (any chain whose transactions are stored in the MariaDB transactions table)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator, Optional

import pandas as pd
from sqlalchemy import text

from ..chains.registry import ChainConfig, get_chain, BLOCKCHAIN_TYPE_EVM
from ..config import Config, load_config
from ..utils.connections import get_maria_engine
from .base import BlockchainAdapter, TxRecord
from .eth_adapter import (
    EthereumAdapter,
    _to_float,
    _to_int,
    _to_ts,
)

logger = logging.getLogger(__name__)

_MONGO_TIMEOUT_MS = 2000


class EVMAdapter(BlockchainAdapter):
    """
    Generic adapter for any EVM chain.

    For Ethereum it is functionally identical to EthereumAdapter.
    For other EVM chains it reads transactions filtered by chain_name
    from the shared MariaDB transactions table.

    Falls back to MongoDB raw_transactions (chain_name filter applied)
    if MariaDB is unavailable or empty for this chain.
    """

    def __init__(
        self,
        cfg: Optional[Config] = None,
        chain_name: str = "ethereum",
        chain_config: Optional[ChainConfig] = None,
    ):
        self.cfg = cfg or load_config()
        self._chain_config = chain_config or get_chain(chain_name)

        if self._chain_config.blockchain_type != BLOCKCHAIN_TYPE_EVM:
            raise ValueError(
                f"EVMAdapter requires an EVM chain, got: "
                f"{self._chain_config.chain_name} ({self._chain_config.blockchain_type})"
            )

    # ── Chain identity ────────────────────────────────────────────────────────

    @property
    def blockchain_type(self) -> str:
        return BLOCKCHAIN_TYPE_EVM

    @property
    def chain_name(self) -> str:
        return self._chain_config.chain_name

    @property
    def chain_id(self) -> int:
        return self._chain_config.chain_id

    @property
    def native_asset(self) -> str:
        return self._chain_config.native_asset

    # ── Count helpers ─────────────────────────────────────────────────────────

    def _count_mariadb_transactions(self) -> int:
        try:
            engine = get_maria_engine(self.cfg)
            with engine.connect() as conn:
                # For ethereum, also count rows with NULL chain_name (legacy data)
                if self.chain_name == "ethereum":
                    return int(conn.execute(
                        text(
                            "SELECT COUNT(*) FROM transactions "
                            "WHERE chain_name = :chain OR chain_name IS NULL"
                        ),
                        {"chain": self.chain_name},
                    ).scalar_one())
                return int(conn.execute(
                    text("SELECT COUNT(*) FROM transactions WHERE chain_name = :chain"),
                    {"chain": self.chain_name},
                ).scalar_one())
        except Exception as exc:
            logger.warning("EVMAdapter[%s]: MariaDB unavailable: %s", self.chain_name, exc)
            return 0
        finally:
            if "engine" in locals():
                engine.dispose()

    def _count_raw_mongo_transactions(self) -> int:
        """Count flat MongoDB transaction docs for this chain."""
        try:
            from pymongo import MongoClient
            client = MongoClient(
                self.cfg.mongo_uri,
                serverSelectionTimeoutMS=_MONGO_TIMEOUT_MS,
                connectTimeoutMS=_MONGO_TIMEOUT_MS,
            )
            col = client[self.cfg.mongo_flat_tx_db][self.cfg.mongo_flat_tx_collection]
            query = {"chain_name": self.chain_name}
            if self.chain_name == "ethereum":
                # Legacy docs may not have chain_name field
                query = {
                    "$or": [
                        {"chain_name": self.chain_name},
                        {"chain_name": {"$exists": False}},
                    ]
                }
            return col.estimated_document_count() if self.chain_name == "ethereum" \
                else col.count_documents({"chain_name": self.chain_name})
        except Exception as exc:
            logger.warning("EVMAdapter[%s]: MongoDB unavailable: %s", self.chain_name, exc)
            return 0
        finally:
            if "client" in locals():
                client.close()

    # ── Readers ───────────────────────────────────────────────────────────────

    def _iter_from_mariadb(self) -> Iterator[TxRecord]:
        engine = get_maria_engine(self.cfg)

        # For ethereum, include legacy rows with NULL chain_name
        if self.chain_name == "ethereum":
            where_clause = "(chain_name = :chain OR chain_name IS NULL)"
        else:
            where_clause = "chain_name = :chain"

        query = text(
            f"""
            SELECT tx_hash, block_number, timestamp,
                   from_address, to_address, value_eth,
                   is_contract_call, gas_used, status,
                   COALESCE(chain_name, 'ethereum') AS chain_name
            FROM transactions
            WHERE {where_clause}
            ORDER BY block_number ASC, tx_hash ASC
            """
        )
        try:
            with engine.connect() as conn:
                for row in conn.execute(query, {"chain": self.chain_name}).mappings():
                    frm = (row.get("from_address") or "").lower().strip()
                    to  = (row.get("to_address")   or "").lower().strip()
                    if not frm and not to:
                        continue
                    val = _to_float(row.get("value_eth"))
                    yield TxRecord(
                        tx_hash=row.get("tx_hash", ""),
                        block_number=_to_int(row.get("block_number")),
                        timestamp=_to_ts(row.get("timestamp")),
                        from_address=frm,
                        to_address=to,
                        value_eth=val,
                        value_native=val,
                        is_contract_call=bool(row.get("is_contract_call")),
                        gas_used=_to_int(row.get("gas_used")),
                        status=_to_int(row.get("status")),
                        chain_name=self.chain_name,
                        chain_id=self.chain_id,
                        blockchain_type=self.blockchain_type,
                        native_asset=self.native_asset,
                    )
        finally:
            engine.dispose()

    def _iter_from_raw_mongo(self) -> Iterator[TxRecord]:
        from pymongo import MongoClient
        client = MongoClient(
            self.cfg.mongo_uri,
            serverSelectionTimeoutMS=_MONGO_TIMEOUT_MS,
        )
        col = client[self.cfg.mongo_flat_tx_db][self.cfg.mongo_flat_tx_collection]

        if self.chain_name == "ethereum":
            query_filter = {
                "$or": [
                    {"chain_name": self.chain_name},
                    {"chain_name": {"$exists": False}},
                ]
            }
        else:
            query_filter = {"chain_name": self.chain_name}

        for doc in col.find(query_filter, {"_id": 0}).sort("block.number", 1):
            block     = doc.get("block", {})
            ap        = doc.get("address_pair", {})
            val       = doc.get("value", {})
            forensics = doc.get("forensics", {})
            frm = (ap.get("from") or "").lower().strip()
            to  = (ap.get("to")   or "").lower().strip()
            if not frm and not to:
                continue
            eth_val = _to_float(val.get("eth"))
            yield TxRecord(
                tx_hash=doc.get("tx_hash", ""),
                block_number=_to_int(block.get("number")),
                timestamp=_to_ts(block.get("timestamp")),
                from_address=frm,
                to_address=to,
                value_eth=eth_val,
                value_native=eth_val,
                is_contract_call=bool(forensics.get("is_contract")),
                input_method_id=str(forensics.get("method_id") or "").lower().strip(),
                gas_used=_to_int(doc.get("gas", {}).get("gas_used")),
                chain_name=self.chain_name,
                chain_id=self.chain_id,
                blockchain_type=self.blockchain_type,
                native_asset=self.native_asset,
            )
        client.close()

    # ── Public interface ──────────────────────────────────────────────────────

    def iter_transactions(
        self,
        source: str = "auto",
        **kwargs,
    ) -> Iterator[TxRecord]:
        """
        Yield TxRecord objects for this EVM chain.

        source: 'auto' | 'mariadb' | 'raw'
          auto → tries mariadb → mongo fallback
        """
        if source in {"mariadb", "processed"}:
            yield from self._iter_from_mariadb()
            return
        if source == "raw":
            yield from self._iter_from_raw_mongo()
            return

        # auto: prefer MariaDB, fall back to MongoDB
        count = self._count_mariadb_transactions()
        if count > 0:
            logger.info(
                "EVMAdapter[%s]: reading %d transactions from MariaDB",
                self.chain_name, count,
            )
            yield from self._iter_from_mariadb()
        else:
            raw_count = self._count_raw_mongo_transactions()
            if raw_count > 0:
                logger.info(
                    "EVMAdapter[%s]: reading from MongoDB raw (%d docs)",
                    self.chain_name, raw_count,
                )
                yield from self._iter_from_raw_mongo()
            else:
                logger.warning(
                    "EVMAdapter[%s]: no transactions found in MariaDB or MongoDB",
                    self.chain_name,
                )


# ── Factory function ──────────────────────────────────────────────────────────

def get_evm_adapter(
    chain_name: str = "ethereum",
    cfg: Optional[Config] = None,
) -> EVMAdapter:
    """
    Get an EVMAdapter for any supported EVM chain.

    Examples:
        eth_adapter  = get_evm_adapter("ethereum")
        bnb_adapter  = get_evm_adapter("bnb")
        poly_adapter = get_evm_adapter("polygon")
        arb_adapter  = get_evm_adapter("arbitrum")
        base_adapter = get_evm_adapter("base")
    """
    return EVMAdapter(cfg=cfg, chain_name=chain_name)
