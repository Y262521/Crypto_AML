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
    skip_mongo_backup: bool = True,
    skip_neo4j: bool = False,
    strict_neo4j: bool = False,
    run_clustering: bool = True,
    run_placement: bool = True,
    cfg: Config | None = None,
) -> dict:
    """Run extract, transform, load, clustering, and placement analytics."""
    cfg = cfg or load_config()
    setup_logging(cfg.log_level)

    extract_summary = fetch_and_store_raw(start_block=start_block, batch=batch, cfg=cfg)
    extract_start_block, extract_end_block = extract_summary
    transform_summary = transform_raw_to_aml(
        start_block=extract_start_block,
        end_block=extract_end_block,
        cfg=cfg,
    )
    if transform_summary["transactions_created"] == 0:
        logger.info("No transformed transactions were produced. Load stage skipped.")
        return {
            "extract": extract_summary,
            "transform": transform_summary,
            "mongo_backup": None,
            "mariadb": None,
            "neo4j": None,
            "clustering": None,
            "placement": None,
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
            results = engine.run(
                persist=True,
                min_cluster_size=cfg.clustering_min_cluster_size,
            )
            clustering_summary = {
                "clusters_found": len(results),
            }
            logger.info(
                "Clustering complete: %d clusters",
                clustering_summary["clusters_found"],
            )
        except Exception as exc:
            logger.warning("Clustering stage failed (non-fatal): %s", exc)
            clustering_summary = {"error": str(exc)}

    placement_summary = None
    if run_placement:
        try:
            from ..analytics.placement import PlacementAnalysisEngine

            placement_engine = PlacementAnalysisEngine(cfg=cfg)
            placement_result = placement_engine.run(
                source="mariadb",
                persist=True,
            )
            placement_summary = {
                "run_id": placement_result.run_id,
                "placements_found": len(placement_result.placements),
                "behavior_hits": sum(placement_result.summary.get("behaviors", {}).values()),
            }
            logger.info(
                "Placement analytics complete: %d placements, %d behavior hits",
                placement_summary["placements_found"],
                placement_summary["behavior_hits"],
            )
        except Exception as exc:
            logger.warning("Placement stage failed (non-fatal): %s", exc)
            placement_summary = {"error": str(exc)}

    logger.info(
        "Load stage complete | MariaDB transactions: %s | Neo4j edges: %s | Mongo backup: %s",
        0 if mariadb_summary is None else mariadb_summary["transactions_loaded"],
        0 if neo4j_summary is None else neo4j_summary["rows_loaded"],
        0 if mongo_summary is None else mongo_summary.get("rows_loaded", 0),
    )
    return {
        "extract": extract_summary,
        "transform": transform_summary,
        "mongo_backup": mongo_summary,
        "mariadb": mariadb_summary,
        "neo4j": neo4j_summary,
        "clustering": clustering_summary,
        "placement": placement_summary,
    }
