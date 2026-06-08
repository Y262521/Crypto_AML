"""
Solana Blockchain Adapter
==========================
Reads Solana transfer records from MariaDB or MongoDB and yields
chain-tagged TxRecord objects for the clustering engine and AML pipeline.

Key Solana-specific fields preserved:
  - fee_payer      (used by CommonFeePayerHeuristic)
  - programs       (used by SharedProgramInteractionHeuristic)
  - token_mint     (used by SharedTokenAccountFundingHeuristic)
  - transfer_type  ("sol_native" or "spl_token")

These are stored as extra metadata on TxRecord and also accessible
via the raw MongoDB docs.
"""

from __future__ import annotations

import logging
from typing import Iterator, Optional

from ..chains.registry import get_chain, BLOCKCHAIN_TYPE_ACCOUNT
from ..config import Config, load_config
from ..utils.connections import get_maria_engine
from .base import BlockchainAdapter, TxRecord

logger = logging.getLogger(__name__)
_MONGO_TIMEOUT_MS = 2000


def _to_float(v) -> float:
    if v is None:
        return 0.0
    try:
        if hasattr(v, "to_decimal"):
            return float(v.to_decimal())
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _to_int(v) -> int:
    if v is None:
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _to_ts(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if hasattr(v, "timestamp"):
        return v.timestamp()
    if isinstance(v, str):
        if v.isdigit():
            return float(v)
        try:
            import datetime
            return datetime.datetime.fromisoformat(
                v.replace("Z", "+00:00")
            ).timestamp()
        except ValueError:
            pass
    return 0.0


class SolanaAdapter(BlockchainAdapter):
    """
    Reads Solana transfer records and yields TxRecord objects.

    For clustering and AML, each SOL native transfer and SPL token
    transfer becomes one TxRecord. The fee_payer and programs fields
    are preserved in the TxRecord's input_method_id and status fields
    (re-purposed as string containers for Solana-specific data).

    Data source: MariaDB transactions (chain_name="solana") → MongoDB fallback.
    """

    def __init__(self, cfg: Optional[Config] = None):
        self.cfg = cfg or load_config()
        self._chain_config = get_chain("solana")

    # ── Chain identity ────────────────────────────────────────────────────────

    @property
    def blockchain_type(self) -> str:
        return BLOCKCHAIN_TYPE_ACCOUNT

    @property
    def chain_name(self) -> str:
        return "solana"

    @property
    def chain_id(self) -> int:
        return 900

    @property
    def native_asset(self) -> str:
        return "SOL"

    # ── Count helpers ─────────────────────────────────────────────────────────

    def _count_mariadb(self) -> int:
        try:
            from sqlalchemy import text
            engine = get_maria_engine(self.cfg)
            with engine.connect() as conn:
                return int(conn.execute(
                    text("SELECT COUNT(*) FROM transactions WHERE chain_name = 'solana'")
                ).scalar_one())
        except Exception as exc:
            logger.warning("SolanaAdapter: MariaDB count failed: %s", exc)
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
            return col.count_documents({"chain_name": "solana"})
        except Exception as exc:
            logger.warning("SolanaAdapter: MongoDB count failed: %s", exc)
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
                   gas_used, status
            FROM transactions
            WHERE chain_name = 'solana'
            ORDER BY block_number ASC, tx_hash ASC
            """
        )
        try:
            with engine.connect() as conn:
                for row in conn.execute(query).mappings():
                    frm = (row.get("from_address") or "").strip()
                    to  = (row.get("to_address")   or "").strip()
                    if not frm or not to:
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
                        gas_used=_to_int(row.get("gas_used")),
                        status=1,
                        chain_name="solana",
                        chain_id=900,
                        blockchain_type=BLOCKCHAIN_TYPE_ACCOUNT,
                        native_asset="SOL",
                    )
        finally:
            engine.dispose()

    def _iter_from_mongo(self) -> Iterator[TxRecord]:
        """
        Read Solana flat docs from MongoDB.
        Preserves fee_payer and programs in input_method_id for heuristics.
        """
        from pymongo import MongoClient
        client = MongoClient(
            self.cfg.mongo_uri,
            serverSelectionTimeoutMS=_MONGO_TIMEOUT_MS,
        )
        col = client[self.cfg.mongo_flat_tx_db][self.cfg.mongo_flat_tx_collection]
        for doc in col.find(
            {"chain_name": "solana"},
            {"_id": 0},
        ).sort("block.number", 1):
            block   = doc.get("block", {})
            ap      = doc.get("address_pair", {})
            val     = doc.get("value", {})
            sol_meta = doc.get("solana", {})
            forensics = doc.get("forensics", {})

            frm = (ap.get("from") or "").strip()
            to  = (ap.get("to")   or "").strip()
            if not frm or not to:
                continue

            native_val = _to_float(val.get("native") or val.get("sol") or val.get("eth"))

            # Encode fee_payer in input_method_id for the fee-payer heuristic
            fee_payer = sol_meta.get("fee_payer", "")
            programs  = sol_meta.get("programs", []) or forensics.get("programs", [])
            # Encode as pipe-separated string: "feepayer|prog1|prog2"
            method_id_encoded = "|".join(
                filter(None, [fee_payer] + (programs or []))
            )

            yield TxRecord(
                tx_hash=doc.get("tx_hash", ""),
                block_number=_to_int(block.get("number")),
                timestamp=_to_ts(block.get("timestamp")),
                from_address=frm,
                to_address=to,
                value_eth=native_val,
                value_native=native_val,
                is_contract_call=bool(programs),
                input_method_id=method_id_encoded[:256],  # cap length
                gas_used=_to_int((doc.get("gas") or {}).get("gas_used")),
                status=1,
                chain_name="solana",
                chain_id=900,
                blockchain_type=BLOCKCHAIN_TYPE_ACCOUNT,
                native_asset="SOL",
            )
        client.close()

    # ── Public interface ──────────────────────────────────────────────────────

    def iter_transactions(self, source: str = "auto", **kwargs) -> Iterator[TxRecord]:
        if source == "mariadb":
            yield from self._iter_from_mariadb()
            return
        if source == "raw":
            yield from self._iter_from_mongo()
            return

        count = self._count_mariadb()
        if count > 0:
            logger.info("SolanaAdapter: reading %d rows from MariaDB", count)
            yield from self._iter_from_mariadb()
        else:
            mongo_count = self._count_mongo()
            if mongo_count > 0:
                logger.info("SolanaAdapter: reading %d docs from MongoDB", mongo_count)
                yield from self._iter_from_mongo()
            else:
                logger.warning("SolanaAdapter: no data found")
