"""
CLI: Load processed CSVs → MySQL → Neo4j

Usage:
    # Load CSVs into MySQL only
    python -m aml_pipeline.pipelines.run_load

    # Load MySQL → Neo4j sync after
    python -m aml_pipeline.pipelines.run_load --sync-neo4j

    # Load CSVs into MySQL + sync to Neo4j + run clustering
    python -m aml_pipeline.pipelines.run_load --sync-neo4j --cluster

    # Skip MySQL, only sync Neo4j from existing MySQL data
    python -m aml_pipeline.pipelines.run_load --neo4j-only

    # Verify counts in all three databases
    python -m aml_pipeline.pipelines.run_load --verify
"""

from __future__ import annotations

import argparse
import logging

from ..config import load_config
from ..logging_config import setup_logging
from ..etl.load.mariadb_loader import load_to_mariadb
from ..etl.load.neo4j_loader import mysql_to_neo4j_sync


def _verify(cfg):
    from sqlalchemy import text
    from ..utils.connections import get_maria_engine, get_neo4j_driver
    from pymongo import MongoClient

    # MySQL
    engine = get_maria_engine(cfg)
    with engine.connect() as conn:
        mysql_tx   = conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar()
        mysql_addr = conn.execute(text("SELECT COUNT(*) FROM addresses")).scalar()
        mysql_edge = conn.execute(text("SELECT COUNT(*) FROM graph_edges")).scalar()
    engine.dispose()

    # MongoDB
    client = MongoClient(cfg.mongo_uri)
    mongo_raw   = client[cfg.mongo_raw_db][cfg.mongo_raw_collection].count_documents({})
    mongo_flat  = client[cfg.mongo_flat_tx_db][cfg.mongo_flat_tx_collection].count_documents({})
    mongo_proc  = client[cfg.mongo_processed_db][cfg.mongo_processed_collection].count_documents({})
    client.close()

    # Neo4j
    neo4j_tx = neo4j_addr = "N/A"
    try:
        driver = get_neo4j_driver(cfg)
        driver.verify_connectivity()
        with driver.session(database=cfg.neo4j_database) as session:
            neo4j_tx   = session.run("MATCH ()-[r:TRANSFER]->() RETURN count(r) AS c").single()["c"]
            neo4j_addr = session.run("MATCH (a:Address) RETURN count(a) AS c").single()["c"]
        driver.close()
    except Exception as e:
        neo4j_tx = neo4j_addr = f"ERROR: {e}"

    print("\n── Database Verification ────────────────────────────────")
    print(f"  MongoDB  raw_blocks          : {mongo_raw:>8}")
    print(f"  MongoDB  raw_transactions    : {mongo_flat:>8}")
    print(f"  MongoDB  processed_tx        : {mongo_proc:>8}")
    print(f"  MySQL    transactions        : {mysql_tx:>8}")
    print(f"  MySQL    graph_edges         : {mysql_edge:>8}")
    print(f"  MySQL    addresses           : {mysql_addr:>8}")
    print(f"  Neo4j    TRANSFER rels       : {str(neo4j_tx):>8}")
    print(f"  Neo4j    Address nodes       : {str(neo4j_addr):>8}")
    print("─────────────────────────────────────────────────────────\n")


def main():
    parser = argparse.ArgumentParser(description="Load processed data into MySQL and Neo4j")
    parser.add_argument("--sync-neo4j", action="store_true",
                        help="After MySQL load, sync MySQL → Neo4j")
    parser.add_argument("--neo4j-only", action="store_true",
                        help="Skip MySQL load, only sync Neo4j from existing MySQL data")
    parser.add_argument("--full-neo4j", action="store_true",
                        help="Full Neo4j sync (re-upsert all, not just new)")
    parser.add_argument("--cluster", action="store_true",
                        help="Run clustering after load")
    parser.add_argument("--verify", action="store_true",
                        help="Print row counts from all databases and exit")
    args = parser.parse_args()

    cfg = load_config()
    setup_logging(cfg.log_level)
    logger = logging.getLogger(__name__)

    if args.verify:
        _verify(cfg)
        return

    # ── Step 1: MySQL load ────────────────────────────────────────────────────
    if not args.neo4j_only:
        logger.info("Loading processed CSVs into MySQL...")
        try:
            summary = load_to_mariadb(cfg=cfg)
            print("\n── MySQL Load Complete ──────────────────────────────────")
            print(f"  Transactions loaded : {summary['transactions_loaded']}")
            print(f"  Graph edges loaded  : {summary['graph_edges_loaded']}")
            print(f"  Rows skipped        : {summary['rows_skipped']}")
            print(f"  Total transactions  : {summary.get('transactions_total', '?')}")
            print(f"  Total graph edges   : {summary.get('graph_edges_total', '?')}")
            print(f"  Total addresses     : {summary.get('addresses_total', '?')}")
            print("─────────────────────────────────────────────────────────\n")
        except Exception as e:
            logger.error("MySQL load failed: %s", e)
            raise

    # ── Step 2: Neo4j sync ────────────────────────────────────────────────────
    if args.sync_neo4j or args.neo4j_only:
        sync_new_only = not args.full_neo4j
        mode = "incremental" if sync_new_only else "full"
        logger.info("Syncing MySQL → Neo4j (%s)...", mode)
        try:
            neo4j_summary = mysql_to_neo4j_sync(cfg=cfg, sync_new_only=sync_new_only)
            print(f"\n── Neo4j Sync Complete ({mode}) ──────────────────────────")
            print(f"  Rows synced          : {neo4j_summary['rows_synced']}")
            print(f"  Already in Neo4j     : {neo4j_summary['rows_already_in_neo4j']}")
            print(f"  Total in Neo4j graph : {neo4j_summary.get('graph_total', '?')}")
            print("─────────────────────────────────────────────────────────\n")
        except Exception as e:
            logger.warning("Neo4j sync failed (non-fatal): %s", e)

    # ── Step 3: Clustering ────────────────────────────────────────────────────
    if args.cluster:
        logger.info("Running clustering engine...")
        try:
            from ..clustering.engine import ClusteringEngine
            engine = ClusteringEngine(cfg=cfg)
            results = engine.run(persist=True)
            high = sum(1 for r in results if r.risk_score >= 70)
            med  = sum(1 for r in results if 40 <= r.risk_score < 70)
            print(f"\n── Clustering Complete ──────────────────────────────────")
            print(f"  Total clusters  : {len(results)}")
            print(f"  High risk (≥70) : {high}")
            print(f"  Medium risk     : {med}")
            print("─────────────────────────────────────────────────────────\n")
        except Exception as e:
            logger.warning("Clustering failed (non-fatal): %s", e)


if __name__ == "__main__":
    main()
