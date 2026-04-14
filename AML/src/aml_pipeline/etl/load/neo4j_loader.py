"""Load processed transactions into Neo4j for graph exploration."""

from __future__ import annotations

import logging
from typing import Iterable

from sqlalchemy import text

from ...config import Config, load_config
from ...utils.connections import get_maria_engine, get_neo4j_driver

logger = logging.getLogger(__name__)


def _build_transactions_query(min_block: int | None = None) -> tuple[str, dict]:
    query = """
        SELECT tx_hash, from_address, to_address, value_eth, block_number, timestamp,
               is_contract_call, gas_used, status
        FROM transactions
        WHERE from_address IS NOT NULL
          AND to_address IS NOT NULL
          AND from_address <> ''
          AND to_address <> ''
    """
    params: dict[str, int] = {}
    if min_block is not None:
        query += " AND block_number > :min_block"
        params["min_block"] = min_block
    query += " ORDER BY block_number ASC, tx_hash ASC"
    return query, params


def create_constraints(cfg: Config) -> None:
    driver = get_neo4j_driver(cfg)
    query = """
    CREATE CONSTRAINT address_unique IF NOT EXISTS
    FOR (a:Address)
    REQUIRE a.address IS UNIQUE
    """
    index_tx = """
    CREATE INDEX transfer_tx_hash IF NOT EXISTS
    FOR ()-[r:TRANSFER]-()
    ON (r.tx_hash)
    """
    index_block = """
    CREATE INDEX transfer_block_number IF NOT EXISTS
    FOR ()-[r:TRANSFER]-()
    ON (r.block_number)
    """
    try:
        with driver.session(database=cfg.neo4j_database) as session:
            session.run(query).consume()
            session.run(index_tx).consume()
            session.run(index_block).consume()
    finally:
        driver.close()


def clear_graph(cfg: Config) -> None:
    driver = get_neo4j_driver(cfg)
    try:
        with driver.session(database=cfg.neo4j_database) as session:
            session.run("MATCH (n) DETACH DELETE n").consume()
    finally:
        driver.close()


def _iter_transactions(cfg: Config, min_block: int | None = None, batch_size: int = 5000):
    engine = get_maria_engine(cfg)
    query, params = _build_transactions_query(min_block=min_block)

    try:
        with engine.connect() as conn:
            result = conn.execution_options(stream_results=True).execute(text(query), params)
            while True:
                rows = result.mappings().fetchmany(batch_size)
                if not rows:
                    break
                yield rows
    finally:
        engine.dispose()


def load_to_neo4j(
    cfg: Config | None = None,
    min_block: int | None = None,
    batch_size: int | None = None,
) -> dict:
    cfg = cfg or load_config()
    create_constraints(cfg)

    driver = get_neo4j_driver(cfg)
    rows_loaded = 0
    rows_skipped = 0

    query = """
    UNWIND $rows AS row
    MERGE (s:Address {address: row.from_address})
    MERGE (t:Address {address: row.to_address})
    MERGE (s)-[r:TRANSFER {tx_hash: row.tx_hash}]->(t)
    SET r.value_eth = row.value_eth,
        r.block_number = row.block_number,
        r.timestamp = row.timestamp,
        r.is_contract_call = row.is_contract_call,
        r.gas_used = row.gas_used,
        r.status = row.status
    """

    try:
        with driver.session(database=cfg.neo4j_database) as session:
            effective_batch = batch_size or cfg.neo4j_batch_size
            for batch in _iter_transactions(cfg, min_block=min_block, batch_size=effective_batch):
                formatted = []
                for row in batch:
                    if not row.get("from_address") or not row.get("to_address"):
                        rows_skipped += 1
                        continue
                    formatted.append({
                        "tx_hash": row.get("tx_hash"),
                        "from_address": row.get("from_address"),
                        "to_address": row.get("to_address"),
                        "value_eth": float(row.get("value_eth") or 0.0),
                        "block_number": int(row.get("block_number") or 0),
                        "timestamp": row.get("timestamp").isoformat() if row.get("timestamp") else None,
                        "is_contract_call": bool(row.get("is_contract_call")),
                        "gas_used": row.get("gas_used"),
                        "status": row.get("status"),
                    })
                if not formatted:
                    continue
                session.run(query, rows=formatted).consume()
                rows_loaded += len(formatted)
    finally:
        driver.close()

    logger.info("Neo4j load complete: %s rows", rows_loaded)
    return {"rows_loaded": rows_loaded, "rows_skipped": rows_skipped}


def _query_neo4j_graph_stats(cfg: Config) -> tuple[int, int | None]:
    """Return (total_transfer_rels, max_block_number) from the Neo4j graph."""
    driver = get_neo4j_driver(cfg)
    try:
        with driver.session(database=cfg.neo4j_database) as session:
            row = session.run(
                "MATCH ()-[r:TRANSFER]->() RETURN count(r) AS total_rels, max(r.block_number) AS max_block"
            ).single()
            if not row:
                return 0, None
            total_rels = int(row.get("total_rels") or 0)
            max_block = row.get("max_block")
            return total_rels, int(max_block) if max_block is not None else None
    finally:
        driver.close()


def mysql_to_neo4j_sync(
    cfg: Config | None = None,
    sync_new_only: bool = True,
    batch_size: int | None = None,
) -> dict:
    cfg = cfg or load_config()
    min_block = None
    rows_already_in_neo4j = 0
    graph_total = None
    existing_total_rels, existing_max_block = _query_neo4j_graph_stats(cfg)

    if sync_new_only and existing_max_block is not None:
        min_block = existing_max_block
        engine = get_maria_engine(cfg)
        try:
            with engine.connect() as conn:
                rows_already_in_neo4j = int(
                    conn.execute(
                        text(
                            "SELECT COUNT(*) FROM transactions WHERE block_number <= :max_block"
                        ),
                        {"max_block": existing_max_block},
                    ).scalar_one() or 0
                )
        finally:
            engine.dispose()
    elif not sync_new_only:
        rows_already_in_neo4j = existing_total_rels

    summary = load_to_neo4j(cfg=cfg, min_block=min_block, batch_size=batch_size)
    graph_total, _ = _query_neo4j_graph_stats(cfg)

    return {
        "rows_synced": summary.get("rows_loaded", 0),
        "rows_already_in_neo4j": rows_already_in_neo4j,
        "graph_total": graph_total,
    }


def test_small_graph_load(cfg: Config | None = None) -> dict:
    cfg = cfg or load_config()
    return load_to_neo4j(cfg=cfg, min_block=None)
