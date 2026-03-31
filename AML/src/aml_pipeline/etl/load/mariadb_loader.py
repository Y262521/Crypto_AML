"""Load processed CSV outputs into MariaDB tables."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from ...config import Config, load_config
from ...utils.connections import get_maria_engine

logger = logging.getLogger(__name__)

TRANSACTION_COLUMNS = [
    "tx_hash",
    "block_number",
    "timestamp",
    "from_address",
    "to_address",
    "value_eth",
    "gas_used",
    "status",
    "is_contract_call",
    "input_data",
    "risk_flag_high_value",
    "risk_flag_contract",
    "is_suspicious_basic",
    "tx_type",
    "fetched_at",
]
GRAPH_EDGE_COLUMNS = [
    "tx_hash",
    "from_address",
    "to_address",
    "value_eth",
    "block_number",
    "timestamp",
]
BOOLEAN_COLUMNS = [
    "is_contract_call",
    "risk_flag_high_value",
    "risk_flag_contract",
    "is_suspicious_basic",
]
ADDRESS_INSERT_SQL = """
INSERT INTO addresses (
    address,
    first_seen_block,
    last_seen_block,
    first_seen_at,
    last_seen_at,
    total_in_tx_count,
    total_out_tx_count
)
SELECT
    address,
    MIN(block_number) AS first_seen_block,
    MAX(block_number) AS last_seen_block,
    MIN(timestamp) AS first_seen_at,
    MAX(timestamp) AS last_seen_at,
    SUM(total_in_tx_count) AS total_in_tx_count,
    SUM(total_out_tx_count) AS total_out_tx_count
FROM (
    SELECT
        from_address AS address,
        block_number,
        timestamp,
        0 AS total_in_tx_count,
        1 AS total_out_tx_count
    FROM transactions
    WHERE from_address IS NOT NULL AND from_address <> ''
    UNION ALL
    SELECT
        to_address AS address,
        block_number,
        timestamp,
        1 AS total_in_tx_count,
        0 AS total_out_tx_count
    FROM transactions
    WHERE to_address IS NOT NULL AND to_address <> ''
) AS address_flows
GROUP BY address;
"""


def _schema_path(cfg: Config) -> Path:
    return cfg.base_dir / "schemas" / "mariadb_tables.sql"


def _transactions_csv_path(cfg: Config) -> Path:
    return cfg.processed_dir / "transactions.csv"


def _graph_edges_csv_path(cfg: Config) -> Path:
    return cfg.processed_dir / "graph_edges.csv"


def _run_sql_file(engine: Engine, sql_path: Path) -> None:
    """
    Execute a SQL schema file statement by statement.

    Splits on semicolons that appear at the end of a line (not inside
    CREATE TABLE blocks) to avoid splitting on KEY definitions.
    Uses IF NOT EXISTS so re-runs are safe.
    """
    raw = sql_path.read_text()
    # Split on semicolons followed by optional whitespace + newline
    # This correctly handles multi-line CREATE TABLE statements
    import re
    statements = re.split(r";\s*\n", raw)
    with engine.begin() as conn:
        for stmt in statements:
            stmt = stmt.strip()
            if stmt:
                try:
                    conn.exec_driver_sql(stmt)
                except Exception as exc:
                    # Log but don't abort — duplicate index errors are harmless
                    logger.debug("Schema statement skipped (%s): %.80s", exc, stmt)


def _ensure_database_exists(cfg: Config) -> None:
    engine = get_maria_engine(cfg, include_database=False)
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(f"CREATE DATABASE IF NOT EXISTS `{cfg.mysql_db}`")
    finally:
        engine.dispose()


def create_tables_if_not_exist(cfg: Config | None = None) -> None:
    """Create the MariaDB database and transformed-data tables."""
    cfg = cfg or load_config()
    _ensure_database_exists(cfg)

    schema_path = _schema_path(cfg)
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")

    engine = get_maria_engine(cfg)
    try:
        _run_sql_file(engine, schema_path)
    finally:
        engine.dispose()


def _ensure_csv_exists(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Processed CSV not found: {path}")


def _prepare_datetime(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce", utc=True)
    return parsed.dt.tz_localize(None)


def _replace_nan_with_none(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.astype(object).where(pd.notna(df), None)


def _trim_to_limit(chunk: pd.DataFrame, rows_remaining: int | None) -> pd.DataFrame:
    if rows_remaining is None:
        return chunk
    return chunk.head(rows_remaining)


def _prepare_transaction_chunk(chunk: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    missing_columns = [column for column in TRANSACTION_COLUMNS if column not in chunk.columns]
    if missing_columns:
        raise ValueError(f"transactions.csv is missing columns: {missing_columns}")

    df = chunk[TRANSACTION_COLUMNS].copy()
    df["timestamp"] = _prepare_datetime(df["timestamp"])
    df["fetched_at"] = _prepare_datetime(df["fetched_at"])
    for column in BOOLEAN_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0).astype(int)

    # FIX: convert scientific notation (e.g. 2.385e-11) to fixed decimal string
    # MySQL DECIMAL(38,18) rejects scientific notation
    df["value_eth"] = pd.to_numeric(df["value_eth"], errors="coerce").fillna(0)
    df["value_eth"] = df["value_eth"].apply(lambda x: f"{x:.18f}")

    valid_mask = df["tx_hash"].notna() & (df["tx_hash"].astype(str).str.strip() != "")
    skipped = int((~valid_mask).sum())
    df = df.loc[valid_mask].drop_duplicates(subset=["tx_hash"], keep="last")
    return _replace_nan_with_none(df), skipped


def _prepare_graph_edge_chunk(chunk: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    missing_columns = [column for column in GRAPH_EDGE_COLUMNS if column not in chunk.columns]
    if missing_columns:
        raise ValueError(f"graph_edges.csv is missing columns: {missing_columns}")

    df = chunk[GRAPH_EDGE_COLUMNS].copy()
    df["timestamp"] = _prepare_datetime(df["timestamp"])

    # FIX: same scientific notation fix for graph_edges
    df["value_eth"] = pd.to_numeric(df["value_eth"], errors="coerce").fillna(0)
    df["value_eth"] = df["value_eth"].apply(lambda x: f"{x:.18f}")

    valid_mask = df["tx_hash"].notna() & (df["tx_hash"].astype(str).str.strip() != "")
    skipped = int((~valid_mask).sum())
    df = df.loc[valid_mask].drop_duplicates(subset=["tx_hash"], keep="last")
    return _replace_nan_with_none(df), skipped


def _upsert_rows(table_name: str, engine: Engine, rows: Iterable[dict]) -> int:
    """
    Upsert rows using raw SQL INSERT ... ON DUPLICATE KEY UPDATE.
    Bypasses SQLAlchemy table reflection which fails when columns
    don't match exactly between the reflected schema and the data.
    """
    records = list(rows)
    if not records:
        return 0

    columns = list(records[0].keys())
    col_names = ", ".join(f"`{c}`" for c in columns)
    placeholders = ", ".join(f":{c}" for c in columns)
    updates = ", ".join(
        f"`{c}` = VALUES(`{c}`)"
        for c in columns
        if c not in ("tx_hash", "created_at")
    )
    sql = text(
        f"INSERT INTO `{table_name}` ({col_names}) VALUES ({placeholders})"
        + (f" ON DUPLICATE KEY UPDATE {updates}" if updates else "")
    )
    with engine.begin() as conn:
        conn.execute(sql, records)
    return len(records)


def _refresh_addresses(engine: Engine) -> None:
    """
    Rebuild the addresses table from the transactions table using upsert.

    FIX: original used TRUNCATE + INSERT which wiped all address history
    on every load. Now uses INSERT ... ON DUPLICATE KEY UPDATE so existing
    address records are updated incrementally without data loss.
    """
    upsert_sql = """
    INSERT INTO addresses (
        address,
        first_seen_block,
        last_seen_block,
        first_seen_at,
        last_seen_at,
        total_in_tx_count,
        total_out_tx_count
    )
    SELECT
        address,
        MIN(block_number)          AS first_seen_block,
        MAX(block_number)          AS last_seen_block,
        MIN(timestamp)             AS first_seen_at,
        MAX(timestamp)             AS last_seen_at,
        SUM(total_in_tx_count)     AS total_in_tx_count,
        SUM(total_out_tx_count)    AS total_out_tx_count
    FROM (
        SELECT from_address AS address, block_number, timestamp,
               0 AS total_in_tx_count, 1 AS total_out_tx_count
        FROM transactions
        WHERE from_address IS NOT NULL AND from_address <> ''
        UNION ALL
        SELECT to_address AS address, block_number, timestamp,
               1 AS total_in_tx_count, 0 AS total_out_tx_count
        FROM transactions
        WHERE to_address IS NOT NULL AND to_address <> ''
    ) AS flows
    GROUP BY address
    ON DUPLICATE KEY UPDATE
        first_seen_block    = LEAST(first_seen_block, VALUES(first_seen_block)),
        last_seen_block     = GREATEST(last_seen_block, VALUES(last_seen_block)),
        first_seen_at       = LEAST(first_seen_at, VALUES(first_seen_at)),
        last_seen_at        = GREATEST(last_seen_at, VALUES(last_seen_at)),
        total_in_tx_count   = VALUES(total_in_tx_count),
        total_out_tx_count  = VALUES(total_out_tx_count),
        updated_at          = CURRENT_TIMESTAMP
    """
    with engine.begin() as conn:
        conn.exec_driver_sql(upsert_sql)
    logger.info("Addresses table refreshed via upsert")


def _count_rows(engine: Engine, table_name: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one())


def load_to_mariadb(
    cfg: Config | None = None,
    chunk_size: int | None = None,
    limit: int | None = None,
) -> dict:
    """Load processed CSV files into MariaDB with idempotent upserts."""
    cfg = cfg or load_config()
    create_tables_if_not_exist(cfg)

    transactions_path = _transactions_csv_path(cfg)
    graph_edges_path = _graph_edges_csv_path(cfg)
    _ensure_csv_exists(transactions_path)
    _ensure_csv_exists(graph_edges_path)

    chunk_size = chunk_size or cfg.batch_size
    engine = get_maria_engine(cfg)
    summary = {
        "transactions_loaded": 0,
        "graph_edges_loaded": 0,
        "rows_skipped": 0,
    }

    try:
        tx_rows_remaining = limit
        for chunk in pd.read_csv(transactions_path, chunksize=chunk_size):
            chunk = _trim_to_limit(chunk, tx_rows_remaining)
            if chunk.empty:
                break
            prepared_chunk, skipped = _prepare_transaction_chunk(chunk)
            summary["rows_skipped"] += skipped
            summary["transactions_loaded"] += _upsert_rows(
                "transactions", engine, prepared_chunk.to_dict(orient="records")
            )
            if tx_rows_remaining is not None:
                tx_rows_remaining -= len(chunk)
                if tx_rows_remaining <= 0:
                    break

        edge_rows_remaining = limit
        for chunk in pd.read_csv(graph_edges_path, chunksize=chunk_size):
            chunk = _trim_to_limit(chunk, edge_rows_remaining)
            if chunk.empty:
                break
            prepared_chunk, skipped = _prepare_graph_edge_chunk(chunk)
            summary["rows_skipped"] += skipped
            summary["graph_edges_loaded"] += _upsert_rows(
                "graph_edges", engine, prepared_chunk.to_dict(orient="records")
            )
            if edge_rows_remaining is not None:
                edge_rows_remaining -= len(chunk)
                if edge_rows_remaining <= 0:
                    break

        _refresh_addresses(engine)
        summary["transactions_total"] = _count_rows(engine, "transactions")
        summary["graph_edges_total"] = _count_rows(engine, "graph_edges")
        summary["addresses_total"] = _count_rows(engine, "addresses")
    finally:
        engine.dispose()

    logger.info(
        "Loaded %s transactions to MariaDB | %s graph edges | skipped %s rows",
        summary["transactions_loaded"],
        summary["graph_edges_loaded"],
        summary["rows_skipped"],
    )
    return summary


def test_small_load(cfg: Config | None = None) -> dict:
    """Load a small sample into MariaDB for smoke testing."""
    return load_to_mariadb(cfg=cfg, limit=50)
