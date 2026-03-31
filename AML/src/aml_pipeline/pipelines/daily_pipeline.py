"""Daily Extract -> Transform -> Load pipeline."""

import logging

from ..config import Config, load_config
from ..etl.extract import fetch_and_store_raw
from ..etl.transform.transformer import transform_raw_to_aml
from ..etl.load import (
    run_load_stage,
)
from ..logging_config import setup_logging

logger = logging.getLogger(__name__)


def run_daily_extract(start_block=None, batch=None):
    """Run a single Ethereum extract batch."""
    return fetch_and_store_raw(start_block=start_block, batch=batch)


def run_daily_pipeline(
    start_block=None,
    batch=None,
    skip_mongo_backup: bool = False,
    skip_neo4j: bool = False,
    strict_neo4j: bool = False,
    run_clustering: bool = True,
    cfg: Config | None = None,
) -> dict:
    """Run extract, transform, load, and clustering for the daily pipeline."""
    cfg = cfg or load_config()
    setup_logging(cfg.log_level)

    extract_summary = fetch_and_store_raw(start_block=start_block, batch=batch, cfg=cfg)
    transform_summary = transform_raw_to_aml(cfg=cfg)
    if transform_summary["transactions_created"] == 0:
        logger.info("No transformed transactions were produced. Load stage skipped.")
        return {
            "extract": extract_summary,
            "transform": transform_summary,
            "mongo_backup": None,
            "mariadb": None,
            "neo4j": None,
            "clustering": None,
        }

    load_summary = run_load_stage(
        cfg,
        skip_mongo_backup=skip_mongo_backup,
        skip_neo4j=skip_neo4j,
        strict_neo4j=strict_neo4j,
    )
    mongo_summary = load_summary["mongo_backup"]
    mariadb_summary = load_summary["mariadb"]
    neo4j_summary = load_summary["neo4j"]

    clustering_summary = None
    if run_clustering:
        try:
            from ..clustering.engine import ClusteringEngine
            engine = ClusteringEngine(cfg=cfg)
            results = engine.run(persist=True)
            clustering_summary = {
                "clusters_found": len(results),
                "high_risk": sum(1 for r in results if r.risk_score >= 70),
                "medium_risk": sum(1 for r in results if 40 <= r.risk_score < 70),
            }
            logger.info(
                "Clustering complete: %d clusters (%d high-risk)",
                clustering_summary["clusters_found"],
                clustering_summary["high_risk"],
            )
        except Exception as exc:
            logger.warning("Clustering stage failed (non-fatal): %s", exc)
            clustering_summary = {"error": str(exc)}

    logger.info(
        "Load stage complete | MariaDB transactions: %s | Neo4j edges: %s | Mongo backup: %s",
        0 if mariadb_summary is None else mariadb_summary["transactions_loaded"],
        0 if neo4j_summary is None else neo4j_summary["rows_loaded"],
        0 if mongo_summary is None else mongo_summary["rows_loaded"],
    )
    return {
        "extract": extract_summary,
        "transform": transform_summary,
        "mongo_backup": mongo_summary,
        "mariadb": mariadb_summary,
        "neo4j": neo4j_summary,
        "clustering": clustering_summary,
    }
