"""Extractor package entrypoint and compatibility helpers."""

from datetime import datetime, timezone
from typing import Optional, Tuple

import pandas as pd

from ...config import Config
from ...db.mongo import fetch_transactions
from .eth import (
    EthereumExtractor,
    backfill_flat_transactions_from_raw_blocks,
    test_connection,
)
from .factories import get_extractor


def fetch_and_store_raw(
    start_block: Optional[int] = None,
    batch: Optional[int] = None,
    chain: str = "ethereum",
    cfg: Optional[Config] = None,
) -> Tuple[int, int]:
    """Fetch raw blocks and flattened raw transactions for the selected chain."""
    extractor = get_extractor(chain, cfg)
    return extractor.fetch_and_store_raw(start_block=start_block, batch=batch)


def get_latest_saved_block(cfg: Optional[Config] = None) -> Optional[int]:
    """Return the latest saved Ethereum block number from MongoDB."""
    extractor = EthereumExtractor(cfg)
    return extractor.get_latest_saved_block()


def save_to_local_backup(raw_data: dict, block_number: int, cfg: Optional[Config] = None) -> str:
    """Persist a raw block JSON backup to the local data/raw folder."""
    extractor = EthereumExtractor(cfg)
    return extractor.save_to_local_backup(raw_data, block_number)


# Legacy helper for the old Mongo->DataFrame flow.
def extract_raw_transactions(
    cfg: Config,
    since_dt: Optional[datetime] = None,
) -> Tuple[pd.DataFrame, Optional[str]]:
    """Legacy helper: load flattened raw transaction docs into a DataFrame snapshot."""
    docs = list(fetch_transactions(cfg, since_dt=since_dt))
    if not docs:
        return pd.DataFrame(), None

    df_raw = pd.DataFrame(docs)
    cfg.raw_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_path = cfg.raw_dir / f"raw_{timestamp}.jsonl"
    df_raw.to_json(raw_path, orient="records", lines=True, date_format="iso")
    return df_raw, str(raw_path)


__all__ = [
    "EthereumExtractor",
    "backfill_flat_transactions_from_raw_blocks",
    "fetch_and_store_raw",
    "get_extractor",
    "test_connection",
    "get_latest_saved_block",
    "save_to_local_backup",
    "extract_raw_transactions",
]
