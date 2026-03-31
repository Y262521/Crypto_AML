"""
CLI: Synchronize MySQL transactions → Neo4j graph.

Usage:
    # Incremental sync (only new transactions not yet in Neo4j)
    python -m aml_pipeline.pipelines.run_sync

    # Full sync (re-upsert everything — safe, idempotent)
    python -m aml_pipeline.pipelines.run_sync --full

    # Verify counts in both databases
    python -m aml_pipeline.pipelines.run_sync --verify
"""

from __future__ import annotations

import argparse
import logging

from ..config import load_config
from ..logging_config import setup_logging
from ..etl.load.neo4j_loader import mysql_to_neo4j_sync
from ..utils.connections import get_maria_engine, get_neo4j_driver


def _verify(cfg):
    """Print row counts from MySQL and Neo4j side by side."""
    from sqlalchemy import text

    engine = get_maria_engine(cfg)
    with engine.connect() as conn:
        mysql_tx   = conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar()
        mysql_addr = conn.execute(text("SELECT COUNT(*) FROM addresses")).scalar()
        mysql_edge = conn.execute(text("SELECT COUNT(*) FROM graph_edges")).scalar()
    engine.dispose()

    driver = get_neo4j_driver(cfg)
    driver.verify_connectivity()
    with driver.session(database=cfg.neo4j_database) as session:
        neo4j_tx   = session.run("MATCH ()-[r:TRANSFER]->() RETURN count(r) AS c").single()["c"]
        neo4j_addr = session.run("MATCH (a:Address) RETURN count(a) AS c").single()["c"]
    driver.close()

    print("\n── Database Sync Verification ──────────────────────────")
    print(f"  MySQL  transactions : {mysql_tx:>8}")
    print(f"  Neo4j  TRANSFER rels: {neo4j_tx:>8}  {'✅ in sync' if mysql_tx == neo4j_tx else '⚠️  out of sync'}")
    print(f"  MySQL  addresses    : {mysql_addr:>8}")
    print(f"  Neo4j  Address nodes: {neo4j_addr:>8}  {'✅ in sync' if mysql_addr == neo4j_addr else '⚠️  out of sync'}")
    print(f"  MySQL  graph_edges  : {mysql_edge:>8}")
    print("────────────────────────────────────────────────────────\n")


def main():
    parser = argparse.ArgumentParser(description="Sync MySQL transactions → Neo4j")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Full sync: re-upsert all transactions (default: incremental)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Print row counts from MySQL and Neo4j and exit",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Rows per batch (default: NEO4J_BATCH_SIZE from .env)",
    )
    args = parser.parse_args()

    cfg = load_config()
    setup_logging(cfg.log_level)
    logger = logging.getLogger(__name__)

    if args.verify:
        _verify(cfg)
        return

    sync_new_only = not args.full
    mode = "incremental" if sync_new_only else "full"
    logger.info("Starting MySQL → Neo4j sync (mode=%s)", mode)

    summary = mysql_to_neo4j_sync(
        cfg=cfg,
        batch_size=args.batch_size,
        sync_new_only=sync_new_only,
    )

    print(f"\n── MySQL → Neo4j Sync Complete ({mode}) ──────────────────")
    print(f"  Rows synced          : {summary['rows_synced']}")
    print(f"  Already in Neo4j     : {summary['rows_already_in_neo4j']}")
    print(f"  Total in Neo4j graph : {summary.get('graph_total', '?')}")
    print("────────────────────────────────────────────────────────\n")


if __name__ == "__main__":
    main()
