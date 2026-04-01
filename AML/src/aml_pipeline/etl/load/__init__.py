"""Load stage helpers for MongoDB backup, MariaDB, and Neo4j."""

from __future__ import annotations

import logging

from ...config import Config
from .mariadb_loader import (
    create_tables_if_not_exist,
    load_to_mariadb,
    test_small_load,
)
from .mongodb_loader import (
    load_processed_to_mongo_backup,
    verify_raw_count,
)
from .neo4j_loader import (
    clear_graph,
    create_constraints,
    load_to_neo4j,
    mysql_to_neo4j_sync,
    test_small_graph_load,
)

logger = logging.getLogger(__name__)


def load_transactions_to_mariadb(cfg: Config, df_clean=None) -> int:
    """Run the MariaDB loader and return the number of rows processed this run."""
    summary = load_to_mariadb(cfg=cfg)
    return int(summary["transactions_loaded"])


def load_alerts_to_mariadb(cfg: Config, df_alerts=None) -> int:
    """Alerts are not part of the current transformed CSV load stage."""
    return 0


def load_relationships_to_neo4j(cfg: Config, df_clean=None) -> int:
    """Run the Neo4j loader and return the number of edges processed this run."""
    summary = load_to_neo4j(cfg=cfg)
    return int(summary["rows_loaded"])


def run_load_stage(
    cfg: Config,
    *,
    skip_mongo_backup: bool = False,
    skip_mariadb: bool = False,
    skip_neo4j: bool = False,
    strict_neo4j: bool = False,
) -> dict:
    """Run the full load stage with graceful Neo4j failure handling by default."""
    summary = {
        "mongo_backup": None,
        "mariadb": None,
        "neo4j": None,
    }

    if not skip_mongo_backup:
        summary["mongo_backup"] = load_processed_to_mongo_backup(cfg=cfg)

    if not skip_mariadb:
        summary["mariadb"] = load_to_mariadb(cfg=cfg)

    if not skip_neo4j:
        try:
            summary["neo4j"] = load_to_neo4j(cfg=cfg)
        except Exception as exc:  # noqa: BLE001
            if strict_neo4j:
                raise
            message = str(exc)
            logger.warning("Neo4j load skipped after error: %s", message)
            summary["neo4j"] = {
                "rows_loaded": 0,
                "rows_skipped": 0,
                "error": message,
            }

    return summary


__all__ = [
    "clear_graph",
    "create_constraints",
    "create_tables_if_not_exist",
    "load_processed_to_mongo_backup",
    "load_to_mariadb",
    "load_to_neo4j",
    "mysql_to_neo4j_sync",
    "load_alerts_to_mariadb",
    "load_relationships_to_neo4j",
    "load_transactions_to_mariadb",
    "run_load_stage",
    "test_small_graph_load",
    "test_small_load",
    "verify_raw_count",
]
