"""
Multi-chain database migrations (Phase 1).

Adds chain identity columns to every table that stores blockchain data.
All migrations are idempotent — safe to run multiple times.

Tables migrated:
  transactions              → chain_name, chain_id, blockchain_type, native_asset
  addresses                 → chain_name, chain_id, blockchain_type
  wallet_clusters           → chain_name, blockchain_type
  cluster_evidence          → chain_name
  owner_list_addresses      → (already has blockchain_network; we add chain_name alias)
  placement_entities        → chain_name
  placement_entity_addresses→ chain_name
  placement_detections      → chain_name
  placement_behaviors       → chain_name
  layering_entities         → chain_name
  layering_entity_addresses → chain_name
  layering_alerts           → chain_name
  layering_detector_hits    → chain_name
  integration_alerts        → chain_name

Neo4j schema migration:
  Address nodes get chain_name, chain_id, blockchain_type properties
  TRANSFER edges get chain_name, chain_id, native_asset properties
"""

from __future__ import annotations

import logging
from typing import Set

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


# ── Column definitions per table ──────────────────────────────────────────────

_CHAIN_COLUMNS = {
    "chain_name":       "VARCHAR(32) NOT NULL DEFAULT 'ethereum' COMMENT 'canonical chain name'",
    "chain_id":         "INT NOT NULL DEFAULT 1 COMMENT 'numeric chain ID'",
    "blockchain_type":  "VARCHAR(16) NOT NULL DEFAULT 'EVM' COMMENT 'EVM | UTXO | ACCOUNT_BASED'",
    "native_asset":     "VARCHAR(16) NOT NULL DEFAULT 'ETH' COMMENT 'native token symbol'",
}

_TABLE_COLUMN_MAP: dict[str, list[str]] = {
    # Core data tables
    "transactions":               ["chain_name", "chain_id", "blockchain_type", "native_asset"],
    "addresses":                  ["chain_name", "chain_id", "blockchain_type"],
    "wallet_clusters":            ["chain_name", "blockchain_type"],
    "cluster_evidence":           ["chain_name"],
    # Placement tables
    "placement_entities":         ["chain_name"],
    "placement_entity_addresses": ["chain_name"],
    "placement_detections":       ["chain_name"],
    "placement_behaviors":        ["chain_name"],
    "placement_traces":           ["chain_name"],
    "placement_labels":           ["chain_name"],
    # Layering tables
    "layering_entities":          ["chain_name"],
    "layering_entity_addresses":  ["chain_name"],
    "layering_alerts":            ["chain_name"],
    "layering_detector_hits":     ["chain_name"],
    "layering_evidence":          ["chain_name"],
    "layering_bridge_pairs":      ["chain_name"],
    # Integration tables
    "integration_alerts":         ["chain_name"],
}

# Indexes to create after column additions
_TABLE_INDEXES: dict[str, list[tuple[str, str]]] = {
    "transactions": [
        ("idx_transactions_chain_name", "chain_name"),
    ],
    "addresses": [
        ("idx_addresses_chain_name", "chain_name"),
    ],
    "wallet_clusters": [
        ("idx_wallet_clusters_chain_name", "chain_name"),
    ],
}


def _get_existing_columns(engine: Engine, db: str, table: str) -> Set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT COLUMN_NAME
                FROM information_schema.columns
                WHERE table_schema = :db AND table_name = :table
                """
            ),
            {"db": db, "table": table},
        ).all()
    return {row[0] for row in rows}


def _table_exists(engine: Engine, db: str, table: str) -> bool:
    with engine.connect() as conn:
        val = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = :db AND table_name = :table
                """
            ),
            {"db": db, "table": table},
        ).scalar_one()
    return bool(val)


def _get_existing_indexes(engine: Engine, db: str, table: str) -> Set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT index_name
                FROM information_schema.statistics
                WHERE table_schema = :db AND table_name = :table
                """
            ),
            {"db": db, "table": table},
        ).all()
    return {row[0] for row in rows}


def run_mariadb_chain_migrations(engine: Engine, db_name: str) -> dict:
    """
    Add chain identity columns to all AML tables.

    Returns a summary dict with counts of columns added and tables skipped.
    """
    summary = {"columns_added": 0, "tables_skipped": 0, "tables_migrated": 0}

    for table, columns in _TABLE_COLUMN_MAP.items():
        if not _table_exists(engine, db_name, table):
            logger.debug("Skipping migration for missing table: %s", table)
            summary["tables_skipped"] += 1
            continue

        existing = _get_existing_columns(engine, db_name, table)
        added = 0
        for col in columns:
            if col in existing:
                continue
            ddl = _CHAIN_COLUMNS[col]
            try:
                with engine.begin() as conn:
                    conn.exec_driver_sql(
                        f"ALTER TABLE `{table}` ADD COLUMN `{col}` {ddl}"
                    )
                logger.info("Added column %s.%s", table, col)
                added += 1
            except Exception as exc:
                logger.warning("Could not add column %s.%s: %s", table, col, exc)

        # Add indexes for key tables
        if table in _TABLE_INDEXES:
            existing_idx = _get_existing_indexes(engine, db_name, table)
            for idx_name, col_name in _TABLE_INDEXES[table]:
                if idx_name in existing_idx:
                    continue
                if col_name not in _get_existing_columns(engine, db_name, table):
                    continue
                try:
                    with engine.begin() as conn:
                        conn.exec_driver_sql(
                            f"ALTER TABLE `{table}` ADD KEY `{idx_name}` (`{col_name}`)"
                        )
                    logger.info("Added index %s on %s.%s", idx_name, table, col_name)
                except Exception as exc:
                    logger.warning("Could not add index %s: %s", idx_name, exc)

        summary["columns_added"] += added
        if added > 0:
            summary["tables_migrated"] += 1

    logger.info(
        "Chain migrations complete: %d columns added across %d tables (%d skipped)",
        summary["columns_added"],
        summary["tables_migrated"],
        summary["tables_skipped"],
    )
    return summary


def run_neo4j_chain_migrations(driver, database: str = "neo4j") -> dict:
    """
    Add chain identity indexes to Neo4j Address nodes and TRANSFER edges.

    This creates indexes only — existing nodes/edges are NOT back-filled here
    (that happens during the next ETL sync run via the loader).
    """
    summary = {"indexes_created": 0, "errors": 0}

    # Index chain_name on Address nodes
    address_chain_index = """
    CREATE INDEX address_chain_name IF NOT EXISTS
    FOR (a:Address)
    ON (a.chain_name)
    """
    # Index chain_name on TRANSFER edges
    transfer_chain_index = """
    CREATE INDEX transfer_chain_name IF NOT EXISTS
    FOR ()-[r:TRANSFER]-()
    ON (r.chain_name)
    """
    # Composite index: address + chain_name (for multi-chain address lookups)
    address_chain_composite = """
    CREATE INDEX address_chain_composite IF NOT EXISTS
    FOR (a:Address)
    ON (a.address, a.chain_name)
    """

    statements = [
        ("address_chain_name", address_chain_index),
        ("transfer_chain_name", transfer_chain_index),
        ("address_chain_composite", address_chain_composite),
    ]

    try:
        with driver.session(database=database) as session:
            for name, stmt in statements:
                try:
                    session.run(stmt).consume()
                    summary["indexes_created"] += 1
                    logger.info("Neo4j index created: %s", name)
                except Exception as exc:
                    logger.warning("Neo4j index %s skipped: %s", name, exc)
                    summary["errors"] += 1
    except Exception as exc:
        logger.warning("Neo4j chain migration failed (non-fatal): %s", exc)
        summary["errors"] += 1

    return summary
