"""
UTXO Blockchain Adapter
========================
Reads UTXO input→output pairs from MongoDB (raw_transactions) or MariaDB
and yields chain-tagged TxRecord objects for the clustering engine and
AML analytics pipeline.

UTXO model:
  - from_address = input address (previous owner)
  - to_address   = output address (new owner)
  - value_eth    = value in native asset units (BTC, LTC, etc.)
  - value_native = same

Supports: bitcoin, litecoin, dogecoin, bitcoin_cash
"""

from __future__ import annotations

import logging
from typing import Iterator, Optional

from ..chains.registry import ChainConfig, get_chain, BLOCKCHAIN_TYPE_UTXO
from ..config import Config, load_config
from ..utils.connections import get_maria_engine
from .base import BlockchainAdapter, TxRecord

logger = logging.getLogger(__name__)
_MONGO_TIMEOUT_MS = 2000


def _to_float(value) -> float:
    if value is None:
        return 0.0
    try:
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
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if hasattr(value, "timestamp"):
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


class UTXOAdapter(BlockchainAdapter):
    """
    Reads UTXO input→output pairs and yields TxRecord objects.

    Data source priority (auto mode):
      1. MariaDB transactions table (chain_name filter)
      2. MongoDB raw_transactions (chain_name filter on flat UTXO docs)
    """

    def __init__(
        self,
        cfg: Optional[Config] = None,
        chain_name: str = "bitcoin",
        chain_config: Optional[ChainConfig] = None,
    ):
        self.cfg = cfg or load_config()
        self._chain_config = chain_config or get_chain(chain_name)

        if self._chain_config.blockchain_type != BLOCKCHAIN_TYPE_UTXO:
            raise ValueError(
                f"UTXOAdapter requires a UTXO chain, got: "
                f"{self._chain_config.chain_name} ({self._chain_config.blockchain_type})"
            )

    # ── Chain identity ────────────────────────────────────────────────────────

    @property
    def blockchain_type(self) -> str:
        return BLOCKCHAIN_TYPE_UTXO

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

    def _count_mariadb(self) -> int:
        try:
            from sqlalchemy import text
            engine = get_maria_engine(self.cfg)
            with engine.connect() as conn:
                return int(conn.execute(
                    text("SELECT COUNT(*) FROM transactions WHERE chain_name = :c"),
                    {"c": self.chain_name},
                ).scalar_one())
        except Exception as exc:
            logger.warning("UTXOAdapter[%s]: MariaDB count failed: %s", self.chain_name, exc)
            return 0
        finally:
            if "engine" in locals():
                engine.dispose()

    def _count_mongo(self) -> int:
        try:
            from pymongo import MongoClient
            client = MongoClient(
                self.cfg.mongo_uri,
                serverSelectionTimeoutMS=_MONGO_TIMEOUT_MS,
            )
            col = client[self.cfg.mongo_flat_tx_db][self.cfg.mongo_flat_tx_collection]
            return col.count_documents({"chain_name": self.chain_name})
        except Exception as exc:
            logger.warning("UTXOAdapter[%s]: MongoDB count failed: %s", self.chain_name, exc)
            return 0
        finally:
            if "client" in locals():
                client.close()

    # ── Readers ───────────────────────────────────────────────────────────────

    def _iter_from_mariadb(self) -> Iterator[TxRecord]:
        from sqlalchemy import text
        engine = get_maria_engine(self.cfg)
        query = text(
            """
            SELECT tx_hash, block_number, timestamp,
                   from_address, to_address, value_eth,
                   is_contract_call, gas_used, status,
                   COALESCE(chain_name, :chain) AS chain_name
            FROM transactions
            WHERE chain_name = :chain
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
                        is_contract_call=False,
                        gas_used=0,
                        status=1,
                        chain_name=self.chain_name,
                        chain_id=self.chain_id,
                        blockchain_type=BLOCKCHAIN_TYPE_UTXO,
                        native_asset=self.native_asset,
                    )
        finally:
            engine.dispose()

    def _iter_from_mongo(self) -> Iterator[TxRecord]:
        from pymongo import MongoClient
        client = MongoClient(
            self.cfg.mongo_uri,
            serverSelectionTimeoutMS=_MONGO_TIMEOUT_MS,
        )
        col = client[self.cfg.mongo_flat_tx_db][self.cfg.mongo_flat_tx_collection]
        for doc in col.find(
            {"chain_name": self.chain_name},
            {"_id": 0},
        ).sort("block.number", 1):
            block = doc.get("block", {})
            ap    = doc.get("address_pair", {})
            val   = doc.get("value", {})
            frm = (ap.get("from") or "").lower().strip()
            to  = (ap.get("to")   or "").lower().strip()
            if not frm or not to:
                continue
            # Use native value; fall back to eth alias
            native_val = _to_float(
                val.get("native") or val.get("eth")
            )
            yield TxRecord(
                tx_hash=doc.get("tx_hash", ""),
                block_number=_to_int(block.get("number")),
                timestamp=_to_ts(block.get("timestamp")),
                from_address=frm,
                to_address=to,
                value_eth=native_val,
                value_native=native_val,
                is_contract_call=False,
                gas_used=0,
                status=1,
                chain_name=self.chain_name,
                chain_id=self.chain_id,
                blockchain_type=BLOCKCHAIN_TYPE_UTXO,
                native_asset=self.native_asset,
            )
        client.close()

    # ── Public interface ──────────────────────────────────────────────────────

    def iter_transactions(
        self,
        source: str = "auto",
        **kwargs,
    ) -> Iterator[TxRecord]:
        if source == "mariadb":
            yield from self._iter_from_mariadb()
            return
        if source == "raw":
            yield from self._iter_from_mongo()
            return

        # auto
        count = self._count_mariadb()
        if count > 0:
            logger.info("UTXOAdapter[%s]: reading %d rows from MariaDB", self.chain_name, count)
            yield from self._iter_from_mariadb()
        else:
            mongo_count = self._count_mongo()
            if mongo_count > 0:
                logger.info("UTXOAdapter[%s]: reading %d docs from MongoDB", self.chain_name, mongo_count)
                yield from self._iter_from_mongo()
            else:
                logger.warning("UTXOAdapter[%s]: no data found", self.chain_name)


def get_utxo_adapter(
    chain_name: str = "bitcoin",
    cfg: Optional[Config] = None,
) -> UTXOAdapter:
    return UTXOAdapter(cfg=cfg, chain_name=chain_name)
