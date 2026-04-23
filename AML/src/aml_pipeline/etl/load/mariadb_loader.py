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
]
BOOLEAN_COLUMNS = [
    "is_contract_call",
]
UTF8MB4_COLLATION = "utf8mb4_unicode_ci"
UTF8MB4_TABLES = (
    "owner_list",
    "owner_list_addresses",
    "wallet_clusters",
    "transactions",
    "addresses",
    "cluster_evidence",
    "placement_runs",
    "placement_entities",
    "placement_entity_addresses",
    "placement_behaviors",
    "placement_traces",
    "placement_detections",
    "placement_labels",
    "layering_runs",
    "layering_entities",
    "layering_entity_addresses",
    "layering_detector_hits",
    "layering_evidence",
    "layering_bridge_pairs",
    "layering_alerts",
)


def _schema_path(cfg: Config) -> Path:
    return cfg.base_dir / "schemas" / "mariadb_tables.sql"


def _transactions_csv_path(cfg: Config) -> Path:
    return cfg.processed_dir / "transactions.csv"


def _run_sql_file(engine: Engine, sql_path: Path) -> None:
    """
    Execute a SQL schema file statement by statement.

    Splits on semicolons that appear at the end of a line (not inside
    CREATE TABLE blocks) to avoid splitting on KEY definitions.
    Uses IF NOT EXISTS so re-runs are safe.
    """
    raw = sql_path.read_text(encoding="utf-8")
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
            conn.exec_driver_sql(
                f"ALTER DATABASE `{cfg.mysql_db}` "
                f"CHARACTER SET utf8mb4 COLLATE {UTF8MB4_COLLATION}"
            )
    finally:
        engine.dispose()


def _ensure_utf8mb4_tables(engine: Engine, cfg: Config) -> None:
    table_names = ", ".join(f"'{table}'" for table in UTF8MB4_TABLES)
    query = text(
        f"""
        SELECT table_name, table_collation
        FROM information_schema.tables
        WHERE table_schema = :db
          AND table_name IN ({table_names})
        """
    )

    with engine.connect() as conn:
        rows = conn.execute(query, {"db": cfg.mysql_db}).mappings().all()

    collations = {
        {k.lower(): v for k, v in dict(row).items()}["table_name"]:
        {k.lower(): v for k, v in dict(row).items()}.get("table_collation")
        for row in rows
    }

    for table_name, table_collation in collations.items():
        if (table_collation or "").startswith("utf8mb4_"):
            continue
        try:
            with engine.begin() as conn:
                conn.exec_driver_sql(
                    f"ALTER TABLE `{table_name}` "
                    f"CONVERT TO CHARACTER SET utf8mb4 COLLATE {UTF8MB4_COLLATION}"
                )
            logger.info(
                "Migrated %s to utf8mb4 (%s)",
                table_name,
                UTF8MB4_COLLATION,
            )
        except Exception as exc:
            message = str(exc)
            if "used in a foreign key constraint" in message:
                logger.debug(
                    "Deferred utf8mb4 migration for %s because of foreign keys: %s",
                    table_name,
                    exc,
                )
                continue
            logger.warning(
                "Skipped utf8mb4 migration for %s: %s",
                table_name,
                exc,
            )


def _table_exists(engine: Engine, cfg: Config, table_name: str) -> bool:
    with engine.connect() as conn:
        value = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = :db
                  AND table_name = :table_name
                """
            ),
            {"db": cfg.mysql_db, "table_name": table_name},
        ).scalar_one()
    return bool(value)


def _ensure_owner_registry_columns(engine: Engine, cfg: Config) -> None:
    """Add missing columns to owner-list tables on legacy databases."""
    owner_list_required = {
        "full_name": "VARCHAR(255) NOT NULL",
        "entity_type": "VARCHAR(64) NOT NULL DEFAULT 'individual'",
        "list_category": "VARCHAR(64) NOT NULL DEFAULT 'watchlist'",
        "specifics": "VARCHAR(255) NULL",
        "street_address": "VARCHAR(255) NULL",
        "locality": "VARCHAR(128) NULL",
        "city": "VARCHAR(128) NOT NULL",
        "administrative_area": "VARCHAR(128) NULL",
        "postal_code": "VARCHAR(32) NULL",
        "country": "VARCHAR(128) NOT NULL",
        "source_reference": "VARCHAR(255) NULL",
        "notes": "TEXT NULL",
        "updated_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
    }
    owner_address_required = {
        "owner_list_id": "BIGINT NOT NULL",
        "blockchain_network": "VARCHAR(64) NOT NULL DEFAULT 'ethereum'",
        "address": "VARCHAR(64) NOT NULL",
        "is_primary": "TINYINT(1) NOT NULL DEFAULT 0",
        "created_at": "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
    }

    with engine.begin() as conn:
        owner_rows = conn.execute(
            text(
                """
                SELECT COLUMN_NAME
                FROM information_schema.columns
                WHERE table_schema = :db
                  AND table_name = 'owner_list'
                """
            ),
            {"db": cfg.mysql_db},
        ).all()
        owner_existing = {row[0] for row in owner_rows}
        for column, definition in owner_list_required.items():
            if column in owner_existing:
                continue
            conn.exec_driver_sql(
                f"ALTER TABLE `owner_list` ADD COLUMN `{column}` {definition}"
            )

        address_rows = conn.execute(
            text(
                """
                SELECT COLUMN_NAME
                FROM information_schema.columns
                WHERE table_schema = :db
                  AND table_name = 'owner_list_addresses'
                """
            ),
            {"db": cfg.mysql_db},
        ).all()
        address_existing = {row[0] for row in address_rows}
        for column, definition in owner_address_required.items():
            if column in address_existing:
                continue
            conn.exec_driver_sql(
                f"ALTER TABLE `owner_list_addresses` ADD COLUMN `{column}` {definition}"
            )


def _ensure_owner_address_indexes(engine: Engine, cfg: Config) -> None:
    with engine.begin() as conn:
        indexes = conn.execute(
            text(
                """
                SELECT index_name
                FROM information_schema.statistics
                WHERE table_schema = :db
                  AND table_name = 'owner_list_addresses'
                """
            ),
            {"db": cfg.mysql_db},
        ).scalars().all()
        index_names = set(indexes)

        if "uq_owner_list_addresses_address" not in index_names:
            conn.exec_driver_sql(
                """
                ALTER TABLE `owner_list_addresses`
                ADD UNIQUE KEY `uq_owner_list_addresses_address` (`address`)
                """
            )
        if "idx_owner_list_addresses_owner_id" not in index_names:
            conn.exec_driver_sql(
                """
                ALTER TABLE `owner_list_addresses`
                ADD KEY `idx_owner_list_addresses_owner_id` (`owner_list_id`)
                """
            )
        if "idx_owner_list_addresses_network" not in index_names:
            conn.exec_driver_sql(
                """
                ALTER TABLE `owner_list_addresses`
                ADD KEY `idx_owner_list_addresses_network` (`blockchain_network`)
                """
            )


def _ensure_wallet_cluster_label_columns(engine: Engine, cfg: Config) -> None:
    required = {
        "label_status": "VARCHAR(32) NOT NULL DEFAULT 'unlabeled'",
        "matched_owner_address": "VARCHAR(64) NULL",
        "last_labeled_at": "DATETIME NULL",
    }

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT COLUMN_NAME
                FROM information_schema.columns
                WHERE table_schema = :db
                  AND table_name = 'wallet_clusters'
                """
            ),
            {"db": cfg.mysql_db},
        ).all()
        existing = {row[0] for row in rows}

        for column, definition in required.items():
            if column in existing:
                continue
            conn.exec_driver_sql(
                f"ALTER TABLE `wallet_clusters` ADD COLUMN `{column}` {definition}"
            )

        indexes = conn.execute(
            text(
                """
                SELECT index_name
                FROM information_schema.statistics
                WHERE table_schema = :db
                  AND table_name = 'wallet_clusters'
                """
            ),
            {"db": cfg.mysql_db},
        ).scalars().all()
        if "idx_wallet_clusters_label_status" not in set(indexes):
            conn.exec_driver_sql(
                """
                ALTER TABLE `wallet_clusters`
                ADD KEY `idx_wallet_clusters_label_status` (`label_status`)
                """
            )


def _drop_legacy_wallet_cluster_owner_foreign_keys(engine: Engine, cfg: Config) -> bool:
    """Drop owner_id foreign keys that still point at the legacy owners table."""
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT constraint_name, referenced_table_name
                FROM information_schema.key_column_usage
                WHERE table_schema = :db
                  AND table_name = 'wallet_clusters'
                  AND column_name = 'owner_id'
                  AND referenced_table_name IS NOT NULL
                """
            ),
            {"db": cfg.mysql_db},
        ).mappings().all()

        legacy_found = False
        for row in rows:
            r = {k.lower(): v for k, v in dict(row).items()}
            if r.get("referenced_table_name") == "owner_list":
                continue
            legacy_found = True
            conn.exec_driver_sql(
                f"ALTER TABLE `wallet_clusters` DROP FOREIGN KEY `{r['constraint_name']}`"
            )
        return legacy_found


def _ensure_wallet_cluster_owner_fk(engine: Engine, cfg: Config) -> None:
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT constraint_name, referenced_table_name
                FROM information_schema.key_column_usage
                WHERE table_schema = :db
                  AND table_name = 'wallet_clusters'
                  AND column_name = 'owner_id'
                  AND referenced_table_name IS NOT NULL
                """
            ),
            {"db": cfg.mysql_db},
        ).mappings().all()
        if any({k.lower(): v for k, v in dict(row).items()}.get("referenced_table_name") == "owner_list" for row in rows):
            return

        conn.exec_driver_sql(
            """
            ALTER TABLE `wallet_clusters`
            ADD CONSTRAINT `fk_wallet_clusters_owner`
            FOREIGN KEY (`owner_id`) REFERENCES `owner_list`(`id`)
            ON DELETE SET NULL
            """
        )


def _ensure_owner_list_address_fk(engine: Engine, cfg: Config) -> None:
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT constraint_name
                FROM information_schema.key_column_usage
                WHERE table_schema = :db
                  AND table_name = 'owner_list_addresses'
                  AND column_name = 'owner_list_id'
                  AND referenced_table_name = 'owner_list'
                """
            ),
            {"db": cfg.mysql_db},
        ).mappings().all()
        if rows:
            return
        conn.exec_driver_sql(
            """
            ALTER TABLE `owner_list_addresses`
            ADD CONSTRAINT `fk_owner_list_addresses_owner`
            FOREIGN KEY (`owner_list_id`) REFERENCES `owner_list`(`id`)
            ON DELETE CASCADE
            """
        )


def _migrate_legacy_owner_schema(engine: Engine, cfg: Config) -> None:
    """Remove legacy fake-owner links and swap cluster ownership to owner_list."""
    legacy_fk_found = _drop_legacy_wallet_cluster_owner_foreign_keys(engine, cfg)

    with engine.begin() as conn:
        if legacy_fk_found:
            conn.execute(
                text(
                    """
                    UPDATE wallet_clusters
                    SET owner_id = NULL,
                        label_status = 'unlabeled',
                        matched_owner_address = NULL,
                        last_labeled_at = NULL
                    """
                )
            )

        if _table_exists(engine, cfg, "owners"):
            conn.exec_driver_sql("DROP TABLE `owners`")

    _ensure_owner_list_address_fk(engine, cfg)
    _ensure_wallet_cluster_owner_fk(engine, cfg)


def _drop_legacy_placement_poi_table(engine: Engine, cfg: Config) -> None:
    if not _table_exists(engine, cfg, "placement_pois"):
        return
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE `placement_pois`")
    logger.info("Dropped legacy placement_pois table")


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
        _ensure_owner_registry_columns(engine, cfg)
        _ensure_owner_address_indexes(engine, cfg)
        _ensure_wallet_cluster_label_columns(engine, cfg)
        _migrate_legacy_owner_schema(engine, cfg)
        _drop_legacy_placement_poi_table(engine, cfg)
        _ensure_utf8mb4_tables(engine, cfg)
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

    df = chunk[TRANSACTION_COLUMNS].copy().astype(object)
    df.loc[:, "timestamp"] = _prepare_datetime(df["timestamp"])
    for column in BOOLEAN_COLUMNS:
        df.loc[:, column] = pd.to_numeric(df[column], errors="coerce").fillna(0).astype(int)

    # FIX: convert scientific notation (e.g. 2.385e-11) to fixed decimal string
    # MySQL DECIMAL(38,18) rejects scientific notation
    df.loc[:, "value_eth"] = pd.to_numeric(df["value_eth"], errors="coerce").fillna(0)
    df.loc[:, "value_eth"] = df["value_eth"].apply(lambda x: f"{x:.18f}")

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


def _ensure_address_columns(engine: Engine, cfg: Config) -> None:
    """Add missing columns to legacy addresses tables (safe migration)."""
    required = {
        "is_contract": "TINYINT(1) NOT NULL DEFAULT 0",
        "first_seen": "DATETIME NULL",
        "last_seen": "DATETIME NULL",
        "total_in": "DECIMAL(38,18) NOT NULL DEFAULT 0",
        "total_out": "DECIMAL(38,18) NOT NULL DEFAULT 0",
        "tx_count": "BIGINT NOT NULL DEFAULT 0",
        "cluster_id": "VARCHAR(64) NULL",
    }

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT COLUMN_NAME
                FROM information_schema.columns
                WHERE table_schema = :db
                  AND table_name = 'addresses'
                """
            ),
            {"db": cfg.mysql_db},
        ).all()
        existing = {row[0] for row in rows}

        for column, ddl in required.items():
            if column in existing:
                continue
            conn.exec_driver_sql(f"ALTER TABLE addresses ADD COLUMN {column} {ddl}")


def _refresh_addresses(engine: Engine, cfg: Config) -> None:
    """
    Rebuild the addresses table from the transactions table using upsert.

    FIX: original used TRUNCATE + INSERT which wiped all address history
    on every load. Now uses INSERT ... ON DUPLICATE KEY UPDATE so existing
    address records are updated incrementally without data loss.
    """
    upsert_sql = """
    INSERT INTO addresses (
        address,
        is_contract,
        first_seen,
        last_seen,
        total_in,
        total_out,
        tx_count
    )
    SELECT
        address,
        MAX(is_contract)                       AS is_contract,
        MIN(first_seen)                        AS first_seen,
        MAX(last_seen)                         AS last_seen,
        SUM(total_in)                          AS total_in,
        SUM(total_out)                         AS total_out,
        SUM(tx_count)                          AS tx_count
    FROM (
        SELECT
            from_address AS address,
            0 AS is_contract,
            MIN(timestamp) AS first_seen,
            MAX(timestamp) AS last_seen,
            0 AS total_in,
            SUM(value_eth) AS total_out,
            COUNT(*) AS tx_count
        FROM transactions
        WHERE from_address IS NOT NULL AND from_address <> ''
        GROUP BY from_address
        UNION ALL
        SELECT
            to_address AS address,
            MAX(CASE WHEN is_contract_call = 1 THEN 1 ELSE 0 END) AS is_contract,
            MIN(timestamp) AS first_seen,
            MAX(timestamp) AS last_seen,
            SUM(value_eth) AS total_in,
            0 AS total_out,
            COUNT(*) AS tx_count
        FROM transactions
        WHERE to_address IS NOT NULL AND to_address <> ''
        GROUP BY to_address
    ) AS flows
    GROUP BY address
    ON DUPLICATE KEY UPDATE
        is_contract = GREATEST(is_contract, VALUES(is_contract)),
        first_seen  = LEAST(first_seen, VALUES(first_seen)),
        last_seen   = GREATEST(last_seen, VALUES(last_seen)),
        total_in    = VALUES(total_in),
        total_out   = VALUES(total_out),
        tx_count    = VALUES(tx_count)
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
    _ensure_csv_exists(transactions_path)

    chunk_size = chunk_size or cfg.batch_size
    engine = get_maria_engine(cfg)
    summary = {
        "transactions_loaded": 0,
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

        _ensure_address_columns(engine, cfg)
        _refresh_addresses(engine, cfg)
        summary["transactions_total"] = _count_rows(engine, "transactions")
        summary["addresses_total"] = _count_rows(engine, "addresses")
    finally:
        engine.dispose()

    logger.info(
        "Loaded %s transactions to MariaDB | skipped %s rows",
        summary["transactions_loaded"],
        summary["rows_skipped"],
    )
    return summary


def test_small_load(cfg: Config | None = None) -> dict:
    """Load a small sample into MariaDB for smoke testing."""
    return load_to_mariadb(cfg=cfg, limit=50)
