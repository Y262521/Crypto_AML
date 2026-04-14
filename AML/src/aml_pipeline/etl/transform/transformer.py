"""Transform raw Ethereum block docs into clean CSV outputs."""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import pandas as pd
from bson.decimal128 import Decimal128
from pymongo import ReplaceOne

from ...config import Config, load_config
from ...utils.connections import get_mongo_client
from ..extract.connections import get_flat_transaction_collection, prepare_flat_transaction_collection
from ..extract.utils import build_flat_transaction_documents, normalize_hex_data, normalize_hex_id

logger = logging.getLogger(__name__)


def _get_raw_collection(cfg: Config):
    """Return the MongoDB collection containing raw blocks."""
    client = get_mongo_client(cfg)
    return client[cfg.mongo_raw_db][cfg.mongo_raw_collection]


def _get_flat_transaction_collection(cfg: Config):
    """Return the MongoDB collection containing flattened raw transactions."""
    return get_flat_transaction_collection(cfg)


def _to_int(value) -> int:
    """Convert a raw value into an int, handling hex and string inputs."""
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if value.startswith("0x"):
            try:
                return int(value, 16)
            except ValueError:
                return 0
        try:
            return int(value)
        except ValueError:
            return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _to_datetime(value) -> Optional[datetime]:
    """Convert a raw timestamp into a timezone-aware datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    if isinstance(value, str):
        if value.isdigit():
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _normalize_address(value: Optional[str]) -> Optional[str]:
    """Normalize an Ethereum address to lowercase when present."""
    if not value:
        return None
    return value.lower()


def _decimal_to_float(value) -> float:
    """Convert Decimal128 and related numeric values to floats for CSV output."""
    if value is None:
        return 0.0
    if isinstance(value, Decimal128):
        return float(value.to_decimal())
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def load_raw_batch(from_block: int, to_block: int, cfg: Optional[Config] = None) -> List[dict]:
    """Load a batch of raw blocks from MongoDB by block range."""
    cfg = cfg or load_config()
    collection = _get_raw_collection(cfg)
    cursor = collection.find(
        {"block_number": {"$gte": from_block, "$lte": to_block}}
    ).sort("block_number", 1)
    return list(cursor)


def _load_pending_block_headers(
    collection,
    batch_size: int,
    start_block: Optional[int] = None,
    end_block: Optional[int] = None,
    include_transformed: bool = False,
    after_block: Optional[int] = None,
) -> List[dict]:
    """Load the next block batch without pulling the full block payload."""
    query = {} if include_transformed else {"transformed": {"$ne": True}}

    block_range = {}
    if start_block is not None:
        block_range["$gte"] = start_block
    if end_block is not None:
        block_range["$lte"] = end_block
    if after_block is not None:
        block_range["$gt"] = after_block
        block_range.pop("$gte", None)
    if block_range:
        query["block_number"] = block_range

    cursor = collection.find(
        query,
        {"block_number": 1, "fetched_at": 1, "transaction_count": 1},
    ).sort("block_number", 1).limit(batch_size)
    return list(cursor)


def _dedupe_raw_blocks(raw_blocks: List[dict]) -> Tuple[List[dict], int]:
    """Keep the newest raw document per block number and skip legacy duplicates."""
    latest_blocks: Dict[int, dict] = {}
    duplicate_docs = 0

    for raw_block in raw_blocks:
        block_number = raw_block.get("block_number")
        if block_number is None:
            continue

        current_key = (
            raw_block.get("fetched_at") or "",
            str(raw_block.get("_id", "")),
        )
        existing = latest_blocks.get(block_number)
        if existing is None:
            latest_blocks[block_number] = raw_block
            continue

        existing_key = (
            existing.get("fetched_at") or "",
            str(existing.get("_id", "")),
        )
        duplicate_docs += 1
        if current_key >= existing_key:
            latest_blocks[block_number] = raw_block

    ordered_blocks = [latest_blocks[block_number] for block_number in sorted(latest_blocks)]
    return ordered_blocks, duplicate_docs


def clean_single_tx(
    raw_tx: dict,
    block_timestamp: Optional[datetime],
    block_number: int,
    fetched_at: Optional[str],
    receipt: Optional[dict],
    cfg: Config,
) -> dict:
    """Clean a single raw transaction into a transaction row."""
    tx_hash = normalize_hex_id(raw_tx.get("hash"))
    from_address = _normalize_address(raw_tx.get("from"))
    to_address = _normalize_address(raw_tx.get("to"))

    value_wei = _to_int(raw_tx.get("value"))
    value_eth = value_wei / 1e18

    input_data = normalize_hex_data(raw_tx.get("input"))
    is_contract_call = bool(input_data and input_data != "0x") or to_address is None

    gas_used = None
    status = None
    if receipt:
        gas_used = _to_int(receipt.get("gasUsed"))
        status = receipt.get("status")

    return {
        "block_number": block_number,
        "timestamp": block_timestamp,
        "tx_hash": tx_hash,
        "from_address": from_address,
        "to_address": to_address,
        "value_eth": value_eth,
        "gas_used": gas_used,
        "status": status,
        "is_contract_call": is_contract_call,
    }


def clean_flat_tx(tx_doc: dict, cfg: Config) -> dict:
    """Convert a flattened raw transaction document into a transaction row."""
    block = tx_doc.get("block", {})
    address_pair = tx_doc.get("address_pair", {})
    value = tx_doc.get("value", {})
    gas = tx_doc.get("gas", {})
    forensics = tx_doc.get("forensics", {})
    metadata = tx_doc.get("metadata", {})

    tx_hash = normalize_hex_id(tx_doc.get("tx_hash") or tx_doc.get("_id"))
    from_address = _normalize_address(address_pair.get("from"))
    to_address = _normalize_address(address_pair.get("to"))
    input_data = normalize_hex_data(forensics.get("input_data"))
    is_contract_call = bool(forensics.get("is_contract")) or to_address is None
    value_eth = _decimal_to_float(value.get("eth"))

    return {
        "block_number": _to_int(block.get("number")),
        "timestamp": _to_datetime(block.get("timestamp")),
        "tx_hash": tx_hash,
        "from_address": from_address,
        "to_address": to_address,
        "value_eth": value_eth,
        "gas_used": _to_int(gas.get("gas_used")) if gas.get("gas_used") is not None else None,
        "status": _to_int(forensics.get("receipt_status")) if forensics.get("receipt_status") is not None else None,
        "is_contract_call": is_contract_call,
    }


def _backfill_flat_transactions(flat_collection, raw_blocks: List[dict], cfg: Config) -> int:
    """Populate flattened raw transaction docs for legacy raw blocks."""
    backfilled = 0
    for raw_block in raw_blocks:
        block_number = raw_block.get("block_number")
        flat_documents = build_flat_transaction_documents(raw_block, cfg.eth_network)
        tx_hashes = [document["_id"] for document in flat_documents]
        delete_query = {"block.number": block_number}
        if tx_hashes:
            delete_query["_id"] = {"$nin": tx_hashes}
        flat_collection.delete_many(delete_query)
        if not flat_documents:
            continue
        flat_collection.bulk_write(
            [ReplaceOne({"_id": document["_id"]}, document, upsert=True) for document in flat_documents],
            ordered=False,
        )
        backfilled += len(flat_documents)
    return backfilled


def _build_rows_from_raw_blocks(raw_blocks: List[dict], cfg: Config) -> List[dict]:
    """Transform raw block documents into transaction row dictionaries."""
    transactions_rows: List[dict] = []

    for raw_block in raw_blocks:
        block_number = raw_block.get("block_number")
        block = raw_block.get("block", {})
        block_timestamp = _to_datetime(block.get("timestamp"))
        fetched_at = raw_block.get("fetched_at")

        receipts_map = {}
        for receipt in raw_block.get("receipts", []):
            tx_hash = normalize_hex_id(receipt.get("transactionHash"))
            if tx_hash:
                receipts_map[tx_hash] = receipt

        seen_hashes = set()
        for raw_tx in raw_block.get("transactions", []):
            tx_hash = normalize_hex_id(raw_tx.get("hash"))
            if not tx_hash or tx_hash in seen_hashes:
                continue
            seen_hashes.add(tx_hash)

            receipt = receipts_map.get(tx_hash)
            tx_row = clean_single_tx(
                raw_tx,
                block_timestamp,
                block_number,
                fetched_at,
                receipt,
                cfg,
            )
            transactions_rows.append(tx_row)
    return transactions_rows


def _build_rows_from_flat_transactions(flat_transactions: List[dict], cfg: Config) -> List[dict]:
    """Transform flattened raw transaction documents into output rows."""
    transactions_rows: List[dict] = []
    for tx_doc in flat_transactions:
        tx_row = clean_flat_tx(tx_doc, cfg)
        transactions_rows.append(tx_row)
    return transactions_rows


def save_staging_and_processed(
    dfs: Dict[str, pd.DataFrame],
    batch_number: int,
    cfg: Optional[Config] = None,
) -> None:
    """Write batch dataframes to staging and append to this run's processed outputs."""
    cfg = cfg or load_config()
    cfg.staging_dir.mkdir(parents=True, exist_ok=True)
    cfg.processed_dir.mkdir(parents=True, exist_ok=True)

    for name, df in dfs.items():
        staging_path = cfg.staging_dir / f"{name}_batch_{batch_number}.csv"
        processed_path = cfg.processed_dir / f"{name}.csv"

        df.to_csv(staging_path, index=False)

        write_header = not processed_path.exists()
        df.to_csv(processed_path, mode="a", header=write_header, index=False)


def _reset_transform_outputs(cfg: Config) -> None:
    """Clear previous processed and staging CSVs before a new transform run."""
    cfg.staging_dir.mkdir(parents=True, exist_ok=True)
    cfg.processed_dir.mkdir(parents=True, exist_ok=True)

    for path in cfg.staging_dir.glob("*_batch_*.csv"):
        path.unlink(missing_ok=True)

    for path in (
        cfg.processed_dir / "transactions.csv",
    ):
        path.unlink(missing_ok=True)


def load_processed_to_mariadb(cfg: Optional[Config] = None) -> None:
    """Backward-compatible helper that delegates to the dedicated load stage."""
    from ..load.mariadb_loader import load_to_mariadb

    load_to_mariadb(cfg=cfg)


def transform_raw_to_aml(
    start_block: Optional[int] = None,
    end_block: Optional[int] = None,
    batch_size: Optional[int] = None,
    mark_transformed: bool = True,
    load_to_mariadb: bool = False,
    reset_outputs: bool = True,
    include_transformed: bool = False,
    cfg: Optional[Config] = None,
) -> dict:
    """Transform raw MongoDB blocks into clean CSV outputs."""
    cfg = cfg or load_config()
    raw_collection = _get_raw_collection(cfg)
    flat_collection = _get_flat_transaction_collection(cfg)
    prepare_flat_transaction_collection(cfg)
    batch_size = batch_size or cfg.batch_size_transform

    summary = {
        "batches": 0,
        "blocks_processed": 0,
        "transactions_created": 0,
        "duplicate_raw_blocks_skipped": 0,
        "flat_transactions_used": 0,
        "raw_transactions_used": 0,
        "flat_transactions_backfilled": 0,
    }

    batch_number = 0
    last_processed_block = None
    outputs_reset = False
    while True:
        block_headers = _load_pending_block_headers(
            raw_collection,
            batch_size,
            start_block,
            end_block,
            include_transformed=include_transformed,
            after_block=last_processed_block,
        )
        if not block_headers:
            logger.info("No raw blocks found for transformation")
            break

        if reset_outputs and not outputs_reset:
            _reset_transform_outputs(cfg)
            outputs_reset = True

        block_headers, duplicate_docs = _dedupe_raw_blocks(block_headers)
        if duplicate_docs > 0:
            summary["duplicate_raw_blocks_skipped"] += duplicate_docs
            logger.warning(
                "Skipped %s duplicate raw block documents during transform",
                duplicate_docs,
            )

        processed_block_numbers = [
            block_header.get("block_number")
            for block_header in block_headers
            if block_header.get("block_number") is not None
        ]
        if not processed_block_numbers:
            logger.info("No block numbers were found in the selected transform batch")
            break
        expected_tx_counts = {
            block_header.get("block_number"): block_header.get("transaction_count")
            for block_header in block_headers
            if block_header.get("block_number") is not None
        }

        flat_transactions = list(
            flat_collection.find(
                {"block.number": {"$in": processed_block_numbers}},
                sort=[("block.number", 1), ("forensics.transaction_index", 1)],
            )
        )
        flat_transaction_counts: Dict[int, int] = {}
        for tx_doc in flat_transactions:
            block_number = tx_doc.get("block", {}).get("number")
            if block_number is None:
                continue
            flat_transaction_counts[block_number] = flat_transaction_counts.get(block_number, 0) + 1

        missing_block_numbers = [
            block_number
            for block_number in processed_block_numbers
            if (
                flat_transaction_counts.get(block_number, 0) == 0
                if expected_tx_counts.get(block_number) is None
                else flat_transaction_counts.get(block_number, 0) != expected_tx_counts.get(block_number)
            )
        ]
        missing_block_set = set(missing_block_numbers)
        if missing_block_set:
            flat_transactions = [
                tx_doc
                for tx_doc in flat_transactions
                if tx_doc.get("block", {}).get("number") not in missing_block_set
            ]

        raw_blocks = []
        if missing_block_numbers:
            raw_blocks = list(
                raw_collection.find({"block_number": {"$in": missing_block_numbers}}).sort("block_number", 1)
            )
            raw_blocks, duplicate_docs = _dedupe_raw_blocks(raw_blocks)
            if duplicate_docs > 0:
                summary["duplicate_raw_blocks_skipped"] += duplicate_docs
                logger.warning(
                    "Skipped %s duplicate raw block documents during raw fallback transform",
                    duplicate_docs,
                )
            backfilled = _backfill_flat_transactions(flat_collection, raw_blocks, cfg)
            summary["flat_transactions_backfilled"] += backfilled
        else:
            backfilled = 0

        flat_transactions_rows = _build_rows_from_flat_transactions(flat_transactions, cfg)
        raw_transactions_rows = _build_rows_from_raw_blocks(raw_blocks, cfg)
        transactions_rows = flat_transactions_rows + raw_transactions_rows

        summary["flat_transactions_used"] += len(flat_transactions_rows)
        summary["raw_transactions_used"] += len(raw_transactions_rows)

        transactions_df = pd.DataFrame(transactions_rows)
        save_staging_and_processed(
            {"transactions": transactions_df},
            batch_number,
            cfg,
        )
        summary["batches"] += 1
        summary["blocks_processed"] += len(processed_block_numbers)
        summary["transactions_created"] += len(transactions_df)

        print(
            f"Transformed {len(processed_block_numbers)} blocks -> "
            f"created {len(transactions_df)} clean transactions"
        )
        logger.info(
            "Transformed %s blocks into %s transactions (%s from flat docs, %s from raw fallback, %s backfilled)",
            len(processed_block_numbers),
            len(transactions_df),
            len(flat_transactions_rows),
            len(raw_transactions_rows),
            backfilled,
        )

        if mark_transformed and processed_block_numbers:
            processed_at = datetime.now(timezone.utc)
            raw_collection.update_many(
                {"block_number": {"$in": processed_block_numbers}},
                {"$set": {"transformed": True, "transformed_at": processed_at}},
            )
            flat_collection.update_many(
                {"block.number": {"$in": processed_block_numbers}},
                {"$set": {"metadata.processed": True, "metadata.processed_at": processed_at}},
            )

        last_processed_block = processed_block_numbers[-1]
        batch_number += 1

    if load_to_mariadb and summary["transactions_created"] > 0:
        from ..load.mariadb_loader import load_to_mariadb as run_mariadb_load

        summary["mariadb"] = run_mariadb_load(cfg=cfg)

    return summary


def test_transform_small_batch(cfg: Optional[Config] = None) -> None:
    """Run a small transform test on the latest available raw block."""
    cfg = cfg or load_config()
    collection = _get_raw_collection(cfg)
    latest = collection.find_one(sort=[("block_number", -1)])
    if not latest:
        raise RuntimeError("No raw blocks found for test transform")

    block_number = latest.get("block_number")
    transform_raw_to_aml(
        start_block=block_number,
        end_block=block_number,
        batch_size=1,
        mark_transformed=False,
        cfg=cfg,
    )
