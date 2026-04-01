"""Load processed graph edges into Neo4j for AML graph analysis.

Fixes applied vs original:
  - execute_write lambda closure bug: rows captured by reference → fixed with default arg
  - _count_transfers reused the already-closed driver → now uses the same driver session
  - Added mysql_to_neo4j_sync(): reads directly from MariaDB transactions table and
    pushes to Neo4j, keeping both databases in sync
  - Added sync_new_only flag: skips tx_hashes already present in Neo4j (no duplicates)
  - Improved error messages with actionable hints
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
from neo4j.exceptions import AuthError, ClientError, ServiceUnavailable

from ...config import Config, load_config
from ...utils.connections import get_neo4j_driver, get_maria_engine

logger = logging.getLogger(__name__)

# ── Cypher queries ────────────────────────────────────────────────────────────

GRAPH_LOAD_QUERY = """
UNWIND $rows AS row
MERGE (src:Address {address: row.from_address})
MERGE (dst:Address {address: row.to_address})
MERGE (src)-[transfer:TRANSFER {tx_hash: row.tx_hash}]->(dst)
SET transfer.value_eth    = row.value_eth,
    transfer.block_number = row.block_number,
    transfer.timestamp    = CASE
        WHEN row.timestamp IS NULL OR row.timestamp = '' THEN NULL
        ELSE datetime(row.timestamp)
    END,
    transfer.is_contract_call = row.is_contract_call,
    transfer.risk_flag_high_value = row.risk_flag_high_value,
    transfer.tx_type      = row.tx_type
"""

# Used by sync to check which tx_hashes are already in Neo4j
EXISTING_TX_HASHES_QUERY = """
MATCH ()-[r:TRANSFER]->()
RETURN r.tx_hash AS tx_hash
"""

CONSTRAINT_QUERIES = [
    "CREATE CONSTRAINT address_unique IF NOT EXISTS FOR (a:Address) REQUIRE a.address IS UNIQUE",
    "CREATE INDEX transfer_tx_hash IF NOT EXISTS FOR ()-[r:TRANSFER]-() ON (r.tx_hash)",
    "CREATE INDEX transfer_block_number IF NOT EXISTS FOR ()-[r:TRANSFER]-() ON (r.block_number)",
]

# ── helpers ───────────────────────────────────────────────────────────────────

def _prepare_datetime(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce", utc=True)
    return parsed.dt.strftime("%Y-%m-%dT%H:%M:%SZ").where(parsed.notna(), None)


def _replace_nan_with_none(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.astype(object).where(pd.notna(df), None)


def _raise_connection_error(cfg: Config, exc: Exception) -> None:
    error_code = getattr(exc, "code", "")
    if isinstance(exc, AuthError) or (
        isinstance(exc, ClientError)
        and (
            "Neo.ClientError.Security.Unauthorized" in error_code
            or "Neo.ClientError.Security.AuthenticationRateLimit" in error_code
        )
    ):
        raise RuntimeError(
            f"Neo4j authentication failed for {cfg.neo4j_user}@{cfg.neo4j_uri}. "
            "Check NEO4J_USER/NEO4J_PASSWORD in AML/.env."
        ) from exc
    if isinstance(exc, ServiceUnavailable):
        raise RuntimeError(
            f"Neo4j Bolt unavailable at {cfg.neo4j_uri}. "
            "Start Neo4j: brew services start neo4j  OR  neo4j start"
        ) from exc
    raise RuntimeError(f"Neo4j connection failed: {exc}") from exc


def _get_verified_driver(cfg: Config):
    driver = get_neo4j_driver(cfg)
    try:
        driver.verify_connectivity()
    except (AuthError, ServiceUnavailable, ClientError) as exc:
        driver.close()
        _raise_connection_error(cfg, exc)
    return driver


def _resolve_database(driver, cfg: Config) -> str:
    preferred = cfg.neo4j_database or "neo4j"
    for db in ([preferred] if preferred == "neo4j" else [preferred, "neo4j"]):
        try:
            with driver.session(database=db) as session:
                session.run("RETURN 1").consume()
            if db != preferred:
                logger.warning("Neo4j database '%s' unavailable; using '%s'", preferred, db)
            return db
        except ClientError as exc:
            if "DatabaseNotFound" in getattr(exc, "code", ""):
                continue
            raise RuntimeError(f"Neo4j query failed selecting database: {exc}") from exc
    raise RuntimeError(
        f"Neo4j database '{preferred}' not found. "
        "Set NEO4J_DATABASE in AML/.env to an existing database (e.g. neo4j)."
    )


def _prepare_chunk(chunk: pd.DataFrame) -> tuple[list[dict], int]:
    required = ["from_address", "to_address", "value_eth", "block_number", "tx_hash", "timestamp"]
    missing = [c for c in required if c not in chunk.columns]
    if missing:
        raise ValueError(f"graph_edges.csv missing columns: {missing}")

    df = chunk[required].copy()
    # Add optional enrichment columns if present
    for col, default in [
        ("is_contract_call", False),
        ("risk_flag_high_value", False),
        ("tx_type", "ETH Transfer"),
    ]:
        df[col] = chunk[col] if col in chunk.columns else default

    df["timestamp"] = _prepare_datetime(df["timestamp"])

    valid = (
        df["tx_hash"].notna() & (df["tx_hash"].astype(str).str.strip() != "")
        & df["from_address"].notna() & (df["from_address"].astype(str).str.strip() != "")
        & df["to_address"].notna() & (df["to_address"].astype(str).str.strip() != "")
    )
    skipped = int((~valid).sum())
    df = df.loc[valid].drop_duplicates(subset=["tx_hash"], keep="last")
    return _replace_nan_with_none(df).to_dict(orient="records"), skipped


# ── public API ────────────────────────────────────────────────────────────────

def create_constraints(cfg: Config | None = None) -> None:
    """Create Neo4j constraints and indexes."""
    cfg = cfg or load_config()
    driver = _get_verified_driver(cfg)
    try:
        db = _resolve_database(driver, cfg)
        with driver.session(database=db) as session:
            for q in CONSTRAINT_QUERIES:
                session.run(q).consume()
        logger.info("Neo4j constraints/indexes created")
    finally:
        driver.close()


def clear_graph(cfg: Config | None = None) -> None:
    """Delete all nodes and relationships. Use only for full reloads."""
    cfg = cfg or load_config()
    driver = _get_verified_driver(cfg)
    try:
        db = _resolve_database(driver, cfg)
        with driver.session(database=db) as session:
            session.run("MATCH (n) DETACH DELETE n").consume()
        logger.info("Neo4j graph cleared")
    finally:
        driver.close()


def load_to_neo4j(
    cfg: Config | None = None,
    batch_size: int | None = None,
    limit: int | None = None,
) -> dict:
    """
    Load processed graph_edges.csv into Neo4j in batches.

    Uses MERGE to avoid duplicates. Safe to re-run.
    """
    cfg = cfg or load_config()
    batch_size = batch_size or cfg.neo4j_batch_size
    graph_edges_path = cfg.processed_dir / "graph_edges.csv"
    if not graph_edges_path.exists():
        raise FileNotFoundError(
            f"graph_edges.csv not found at {graph_edges_path}. "
            "Run the transform stage first: python -m aml_pipeline.pipelines.run_etl"
        )

    driver = _get_verified_driver(cfg)
    summary = {"rows_loaded": 0, "rows_skipped": 0}
    rows_remaining = limit

    try:
        db = _resolve_database(driver, cfg)
        with driver.session(database=db) as session:
            # Ensure constraints exist
            for q in CONSTRAINT_QUERIES:
                session.run(q).consume()

            for chunk in pd.read_csv(graph_edges_path, chunksize=batch_size):
                if rows_remaining is not None:
                    chunk = chunk.head(rows_remaining)
                if chunk.empty:
                    break

                rows, skipped = _prepare_chunk(chunk)
                summary["rows_skipped"] += skipped

                if rows:
                    # FIX: capture rows in default arg to avoid closure bug
                    def _write(tx, batch=rows):
                        tx.run(GRAPH_LOAD_QUERY, rows=batch).consume()

                    session.execute_write(_write)
                    summary["rows_loaded"] += len(rows)
                    logger.debug("Loaded batch of %d rows to Neo4j", len(rows))

                if rows_remaining is not None:
                    rows_remaining -= len(chunk)
                    if rows_remaining <= 0:
                        break

            # Count total transfers using the same open session (no second driver)
            result = session.run("MATCH ()-[r:TRANSFER]->() RETURN count(r) AS cnt").single()
            summary["graph_total"] = int(result["cnt"]) if result else 0

        summary["database"] = db
    finally:
        driver.close()

    logger.info(
        "Neo4j load complete: %d edges loaded, %d skipped, %d total in graph",
        summary["rows_loaded"], summary["rows_skipped"], summary.get("graph_total", 0),
    )
    return summary


def mysql_to_neo4j_sync(
    cfg: Config | None = None,
    batch_size: int | None = None,
    sync_new_only: bool = True,
) -> dict:
    """
    Synchronize MySQL transactions table → Neo4j graph.

    Reads directly from MariaDB (not CSV) so it always reflects the
    current state of the relational database.

    Args:
        sync_new_only: if True, fetch existing tx_hashes from Neo4j first
                       and skip any already present (incremental sync).
                       if False, upsert everything (full sync, safe but slower).
    """
    cfg = cfg or load_config()
    batch_size = batch_size or cfg.neo4j_batch_size

    # ── Step 1: connect to both databases ────────────────────────────────────
    maria_engine = get_maria_engine(cfg)
    neo4j_driver = _get_verified_driver(cfg)
    summary = {"rows_synced": 0, "rows_skipped": 0, "rows_already_in_neo4j": 0}

    try:
        db = _resolve_database(neo4j_driver, cfg)

        with neo4j_driver.session(database=db) as session:
            # Ensure constraints exist
            for q in CONSTRAINT_QUERIES:
                session.run(q).consume()

            # ── Step 2: get existing tx_hashes from Neo4j (for incremental sync) ──
            existing_hashes: set[str] = set()
            if sync_new_only:
                logger.info("Fetching existing tx_hashes from Neo4j for incremental sync...")
                result = session.run(EXISTING_TX_HASHES_QUERY)
                existing_hashes = {r["tx_hash"] for r in result if r["tx_hash"]}
                logger.info("Found %d existing transactions in Neo4j", len(existing_hashes))

            # ── Step 3: stream from MySQL in batches ──────────────────────────────
            sql = """
                SELECT
                    tx_hash,
                    from_address,
                    to_address,
                    CAST(value_eth AS CHAR)  AS value_eth,
                    block_number,
                    timestamp,
                    is_contract_call,
                    risk_flag_high_value,
                    tx_type
                FROM transactions
                WHERE from_address IS NOT NULL
                  AND from_address <> ''
                  AND to_address IS NOT NULL
                  AND to_address <> ''
                ORDER BY block_number ASC
            """

            offset = 0
            while True:
                paginated = f"{sql} LIMIT {batch_size} OFFSET {offset}"
                chunk = pd.read_sql(paginated, maria_engine)

                if chunk.empty:
                    break

                # Filter out already-synced rows
                if sync_new_only and existing_hashes:
                    before = len(chunk)
                    chunk = chunk[~chunk["tx_hash"].isin(existing_hashes)]
                    summary["rows_already_in_neo4j"] += before - len(chunk)

                if chunk.empty:
                    offset += batch_size
                    continue

                # Prepare timestamps for Neo4j datetime()
                chunk["timestamp"] = _prepare_datetime(chunk["timestamp"])
                chunk = _replace_nan_with_none(chunk)
                rows = chunk.to_dict(orient="records")

                def _write(tx, batch=rows):
                    tx.run(GRAPH_LOAD_QUERY, rows=batch).consume()

                session.execute_write(_write)
                summary["rows_synced"] += len(rows)
                logger.info(
                    "Synced batch: offset=%d, rows=%d, total_synced=%d",
                    offset, len(rows), summary["rows_synced"],
                )

                offset += batch_size

            # Final count
            result = session.run("MATCH ()-[r:TRANSFER]->() RETURN count(r) AS cnt").single()
            summary["graph_total"] = int(result["cnt"]) if result else 0

        summary["database"] = db

    finally:
        neo4j_driver.close()
        maria_engine.dispose()

    logger.info(
        "MySQL→Neo4j sync complete: %d synced, %d already existed, %d total in graph",
        summary["rows_synced"],
        summary["rows_already_in_neo4j"],
        summary.get("graph_total", 0),
    )
    return summary


def test_small_graph_load(cfg: Config | None = None) -> dict:
    """Load a small sample into Neo4j for smoke testing."""
    return load_to_neo4j(cfg=cfg, limit=20)
