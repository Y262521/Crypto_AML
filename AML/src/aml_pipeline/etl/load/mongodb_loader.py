"""Back up processed transaction rows into MongoDB."""

from __future__ import annotations

import logging
from typing import Iterable

import pandas as pd
from pymongo import ReplaceOne

from ...config import Config, load_config
from .mariadb_loader import TRANSACTION_COLUMNS
from ...utils.connections import get_mongo_client

logger = logging.getLogger(__name__)


def _prepare_datetime(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce", utc=True).dt.tz_localize(None)
    return parsed.apply(lambda value: value.to_pydatetime() if pd.notna(value) else None)


def _replace_nan_with_none(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.astype(object).where(pd.notna(df), None)


def _prepare_chunk(chunk: pd.DataFrame) -> tuple[list[dict], int]:
    missing_columns = [column for column in TRANSACTION_COLUMNS if column not in chunk.columns]
    if missing_columns:
        raise ValueError(f"transactions.csv is missing columns: {missing_columns}")

    df = chunk[TRANSACTION_COLUMNS].copy()
    df.loc[:, "timestamp"] = _prepare_datetime(df["timestamp"])
    df.loc[:, "fetched_at"] = _prepare_datetime(df["fetched_at"])

    valid_mask = df["tx_hash"].notna() & (df["tx_hash"].astype(str).str.strip() != "")
    skipped = int((~valid_mask).sum())
    df = df.loc[valid_mask].drop_duplicates(subset=["tx_hash"], keep="last")
    df = _replace_nan_with_none(df)
    return df.to_dict(orient="records"), skipped


def _bulk_upsert(collection, rows: Iterable[dict]) -> int:
    operations = [ReplaceOne({"tx_hash": row["tx_hash"]}, row, upsert=True) for row in rows]
    if not operations:
        return 0
    collection.bulk_write(operations, ordered=False)
    return len(operations)


def verify_raw_count(cfg: Config | None = None) -> int:
    """Return the count of raw block documents already stored in MongoDB."""
    cfg = cfg or load_config()
    client = get_mongo_client(cfg)
    try:
        raw_collection = client[cfg.mongo_raw_db][cfg.mongo_raw_collection]
        count = raw_collection.count_documents({})
    finally:
        client.close()

    logger.info("Raw MongoDB collection %s has %s documents", cfg.mongo_raw_collection, count)
    return count


def load_processed_to_mongo_backup(
    cfg: Config | None = None,
    chunk_size: int | None = None,
    limit: int | None = None,
) -> dict:
    """Back up processed transaction rows into MongoDB as JSON-like documents."""
    cfg = cfg or load_config()
    chunk_size = chunk_size or cfg.batch_size
    transactions_path = cfg.processed_dir / "transactions.csv"
    if not transactions_path.exists():
        raise FileNotFoundError(f"Processed CSV not found: {transactions_path}")

    summary = {"rows_loaded": 0, "rows_skipped": 0}
    client = get_mongo_client(cfg)
    try:
        collection = client[cfg.mongo_processed_db][cfg.mongo_processed_collection]
        collection.create_index("tx_hash", unique=True)

        rows_remaining = limit
        for chunk in pd.read_csv(transactions_path, chunksize=chunk_size):
            if rows_remaining is not None:
                chunk = chunk.head(rows_remaining)
            if chunk.empty:
                break
            rows, skipped = _prepare_chunk(chunk)
            summary["rows_skipped"] += skipped
            summary["rows_loaded"] += _bulk_upsert(collection, rows)
            if rows_remaining is not None:
                rows_remaining -= len(chunk)
                if rows_remaining <= 0:
                    break

        summary["collection_total"] = collection.count_documents({})
    finally:
        client.close()

    logger.info(
        "Backed up %s processed transactions to MongoDB | skipped %s rows",
        summary["rows_loaded"],
        summary["rows_skipped"],
    )
    return summary
