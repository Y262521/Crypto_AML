"""Daily Extract -> Transform -> Load pipeline — multi-chain aware."""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from ..config import Config, load_config
from ..etl.extract import fetch_and_store_raw
from ..etl.transform.transformer import transform_raw_to_aml
from ..etl.load import run_load_stage
from ..logging_config import setup_logging

logger = logging.getLogger(__name__)

# ── Active EVM chains (Phase 2) ───────────────────────────────────────────────
# Add chain names here to enable ingestion.
# Ethereum is always active (legacy pipeline).
# Others require their RPC URLs set in .env.
EVM_CHAINS = ["ethereum", "bnb", "polygon", "arbitrum", "base"]

# UTXO chains (Phase 3) — add RPC URLs in .env to enable
UTXO_CHAINS = ["bitcoin", "litecoin", "dogecoin", "bitcoin_cash"]


def _generate_etl_run_id(started_at: datetime) -> str:
    """Generate a stable unique run ID from pipeline start timestamp."""
    seed = started_at.isoformat()
    digest = hashlib.sha1(seed.encode()).hexdigest()[:8].upper()
    return f"ETL-{started_at.strftime('%Y%m%d%H%M%S')}-{digest}"


def _persist_etl_run_record(
    *,
    cfg: Config,
    run_id: str,
    started_at: datetime,
    summary_json: dict,
    status: str,
    completed_at: Optional[datetime] = None,
) -> None:
    """
    Insert or update a placement_runs row that tracks the full ETL pipeline run.

    On first call (status='running') an INSERT is performed.
    On the final call (status='completed' or 'failed') an UPDATE replaces
    the row with the definitive timestamps and summary.
    """
    try:
        from sqlalchemy import text
        from ..etl.load.mariadb_loader import create_tables_if_not_exist
        from ..utils.connections import get_maria_engine

        create_tables_if_not_exist(cfg)
        engine = get_maria_engine(cfg)
        # Strip timezone info — MariaDB DATETIME columns don't store TZ
        started_naive = started_at.replace(tzinfo=None)
        completed_naive = (
            completed_at.replace(tzinfo=None) if completed_at else None
        )
        summary_str = json.dumps(summary_json, sort_keys=True, default=str)

        with engine.begin() as conn:
            if status == "running":
                conn.execute(
                    text(
                        """
                        INSERT INTO placement_runs
                            (id, source, chain_name, status, started_at, completed_at, summary_json)
                        VALUES
                            (:id, 'pipeline', 'ethereum', 'running', :started_at, NULL, :summary_json)
                        ON DUPLICATE KEY UPDATE
                            status       = 'running',
                            started_at   = :started_at,
                            summary_json = :summary_json
                        """
                    ),
                    {"id": run_id, "started_at": started_naive, "summary_json": summary_str},
                )
            else:
                conn.execute(
                    text(
                        """
                        INSERT INTO placement_runs
                            (id, source, chain_name, status, started_at, completed_at, summary_json)
                        VALUES
                            (:id, 'pipeline', 'ethereum', :status,
                             :started_at, :completed_at, :summary_json)
                        ON DUPLICATE KEY UPDATE
                            status       = :status,
                            completed_at = :completed_at,
                            summary_json = :summary_json
                        """
                    ),
                    {
                        "id": run_id,
                        "status": status,
                        "started_at": started_naive,
                        "completed_at": completed_naive,
                        "summary_json": summary_str,
                    },
                )
        logger.debug("ETL run record persisted: id=%s status=%s", run_id, status)
    except Exception as exc:
        # Non-fatal — never let persistence errors abort the pipeline
        logger.warning("_persist_etl_run_record failed (non-fatal): %s", exc)


def run_daily_extract(start_block=None, batch=None):
    """Run a single Ethereum extract batch (legacy compat)."""
    return fetch_and_store_raw(start_block=start_block, batch=batch)


def _run_evm_extract(chain_name: str, cfg: Config, start_block=None, batch=None) -> Optional[tuple]:
    """
    Extract one batch of blocks for the given EVM chain.
    Returns (from_block, to_block) or None on failure / not configured.
    """
    import os
    chain_upper = chain_name.upper().replace("-", "_")

    if chain_name != "ethereum":
        has_rpc = any([
            os.getenv(f"{chain_upper}_RPC", "").strip(),
            os.getenv(f"{chain_upper}_RPC_URL", "").strip(),
            os.getenv("ALCHEMY_API_KEY", "").strip(),
            "/v2/" in os.getenv("ALCHEMY_RPC", ""),
        ])
        if not has_rpc:
            logger.info(
                "Skipping %s extract: no RPC URL configured "
                "(set %s_RPC or ALCHEMY_API_KEY in .env)",
                chain_name, chain_upper,
            )
            return None

    try:
        from ..etl.extract.evm import EVMExtractor
        extractor = EVMExtractor(cfg=cfg, chain=chain_name)
        result = extractor.fetch_and_store_raw(start_block=start_block, batch=batch)
        logger.info("[%s] Extract complete: blocks %s -> %s", chain_name, *result)
        return result
    except Exception as exc:
        logger.warning("[%s] Extract failed (non-fatal): %s", chain_name, exc)
        return None


def _run_solana_extract(cfg: Config) -> Optional[tuple]:
    """Extract one batch of Solana slots. Returns (from_slot, to_slot) or None."""
    import os
    has_rpc = any([
        os.getenv("SOLANA_RPC", "").strip(),
        os.getenv("SOL_RPC", "").strip(),
        os.getenv("ALCHEMY_API_KEY", "").strip(),
        "/v2/" in os.getenv("ALCHEMY_RPC", ""),
    ])
    if not has_rpc:
        logger.info("Skipping Solana extract: no RPC configured (set SOLANA_RPC or ALCHEMY_API_KEY)")
        return None
    try:
        from ..etl.extract.solana import SolanaExtractor
        extractor = SolanaExtractor(cfg=cfg)
        result = extractor.fetch_and_store_raw()
        logger.info("[solana] Extract complete: slots %s → %s", *result)
        return result
    except Exception as exc:
        logger.warning("[solana] Extract failed (non-fatal): %s", exc)
        return None


def _run_utxo_extract(chain_name: str, cfg: Config) -> Optional[tuple]:
    """
    Extract one batch of UTXO blocks for the given chain.
    Returns (from_block, to_block) or None if not configured / failed.
    """
    import os
    chain_upper = chain_name.upper().replace("_", "")

    has_rpc = any([
        os.getenv(f"{chain_upper}_RPC", "").strip(),
        os.getenv(f"{chain_upper}_API_URL", "").strip(),
        os.getenv("ALCHEMY_API_KEY", "").strip(),
        "/v2/" in os.getenv("ALCHEMY_RPC", ""),
    ])
    if not has_rpc:
        logger.info(
            "Skipping %s UTXO extract: no RPC configured (set %s_RPC or ALCHEMY_API_KEY)",
            chain_name, chain_upper,
        )
        return None

    try:
        from ..etl.extract.utxo import UTXOExtractor
        extractor = UTXOExtractor(cfg=cfg, chain=chain_name)
        result = extractor.fetch_and_store_raw()
        logger.info("[%s] UTXO extract complete: blocks %s -> %s", chain_name, *result)
        return result
    except Exception as exc:
        logger.warning("[%s] UTXO extract failed (non-fatal): %s", chain_name, exc)
        return None


def run_daily_pipeline(
    start_block=None,
    batch=None,
    skip_mongo_backup: bool = True,
    skip_neo4j: bool = False,
    strict_neo4j: bool = False,
    run_clustering: bool = True,
    run_placement: bool = True,
    run_layering: bool = True,
    run_integration: bool = True,
    chains: Optional[list] = None,
    utxo_chains: Optional[list] = None,
    cfg: Config | None = None,
) -> dict:
    """
    Run extract, transform, load, clustering, and AML analytics.

    chains:       EVM chain names to extract (default: all configured EVM chains)
    utxo_chains:  UTXO chain names to extract (default: all configured UTXO chains)
    """
    cfg = cfg or load_config()
    setup_logging(cfg.log_level)

    # Capture pipeline start time for accurate duration tracking
    pipeline_started_at = datetime.now(timezone.utc)

    active_evm_chains  = chains       or EVM_CHAINS
    active_utxo_chains = utxo_chains  or UTXO_CHAINS

    # ── Phase 2: Multi-chain EVM extract ─────────────────────────────────────
    extract_results = {}
    for chain_name in active_evm_chains:
        # All EVM chains use EVMExtractor (chain-aware get_latest_saved_block)
        # Pass start_block/batch only for ethereum (user-supplied via CLI)
        eth_start = start_block if chain_name == "ethereum" else None
        eth_batch = batch if chain_name == "ethereum" else None
        result = _run_evm_extract(chain_name, cfg, start_block=eth_start, batch=eth_batch)
        if result is not None:
            extract_results[chain_name] = result

    # ── Phase 3: UTXO extract + load ─────────────────────────────────────────
    utxo_extract_results = {}
    for chain_name in active_utxo_chains:
        result = _run_utxo_extract(chain_name, cfg)
        if result is not None:
            utxo_extract_results[chain_name] = result
            # Load UTXO pairs into MariaDB immediately after extraction
            try:
                from ..etl.load.mariadb_loader import load_utxo_pairs_to_mariadb
                load_utxo_pairs_to_mariadb(cfg=cfg, chain_name=chain_name)
            except Exception as exc:
                logger.warning("[%s] UTXO MariaDB load failed (non-fatal): %s", chain_name, exc)

    # ── Phase 4: Solana extract + load ───────────────────────────────────────
    solana_result = _run_solana_extract(cfg) if (
        active_evm_chains and "solana" not in active_evm_chains
        or utxo_chains is not None
    ) else _run_solana_extract(cfg)

    if solana_result is not None:
        utxo_extract_results["solana"] = solana_result
        try:
            from ..etl.load.mariadb_loader import load_utxo_pairs_to_mariadb
            load_utxo_pairs_to_mariadb(cfg=cfg, chain_name="solana")
        except Exception as exc:
            logger.warning("[solana] MariaDB load failed (non-fatal): %s", exc)

    # ── Transform (Ethereum raw blocks) ──────────────────────────────────────
    eth_result = extract_results.get("ethereum")
    eth_start  = eth_result[0] if eth_result else None
    eth_end    = eth_result[1] if eth_result else None

    transform_summary = transform_raw_to_aml(
        start_block=eth_start,
        end_block=eth_end,
        cfg=cfg,
    )

    # Derive extract block range for run record
    extract_start_block = eth_start
    extract_end_block   = eth_end

    any_new_txs = transform_summary["transactions_created"] > 0 or bool(utxo_extract_results)

    if not any_new_txs:
        logger.info("No transformed transactions. Load stage skipped.")
        return {
            "extract":      extract_results,
            "utxo_extract": utxo_extract_results,
            "transform":    transform_summary,
            "mongo_backup": None,
            "mariadb":      None,
            "neo4j":        None,
            "clustering":   None,
            "placement":    None,
            "layering":     None,
            "integration":  None,
        }

    # ── Load ──────────────────────────────────────────────────────────────────
    load_summary = run_load_stage(
        cfg,
        skip_mongo_backup=skip_mongo_backup,
        skip_neo4j=skip_neo4j,
        strict_neo4j=strict_neo4j,
    )
    mongo_summary   = load_summary["mongo_backup"]
    mariadb_summary = load_summary["mariadb"]
    neo4j_summary   = load_summary["neo4j"]

    # Generate ETL run ID and persist ETL metrics BEFORE analytics stages
    etl_run_id = _generate_etl_run_id(pipeline_started_at)
    blocks_extracted = (
        (extract_end_block - extract_start_block + 1)
        if extract_start_block is not None and extract_end_block is not None
        else 0
    )
    transactions_loaded = mariadb_summary.get("transactions_loaded", 0) if mariadb_summary else 0
    neo4j_edges         = neo4j_summary.get("rows_loaded", 0) if neo4j_summary else 0
    records_normalized  = transform_summary.get("transactions_created", 0)

    etl_summary_json = {
        "blocks_extracted":          blocks_extracted,
        "extract_start_block":       extract_start_block,
        "extract_end_block":         extract_end_block,
        "records_normalized":        records_normalized,
        "transactions_loaded":       transactions_loaded,
        "transactions_total_in_db":  transactions_loaded,
        "neo4j_edges":               neo4j_edges,
    }

    _persist_etl_run_record(
        cfg=cfg,
        run_id=etl_run_id,
        started_at=pipeline_started_at,
        summary_json=etl_summary_json,
        status="running",
    )

    # ── Clustering — run per chain type immediately after ETL ────────────────
    clustering_summary = None
    if run_clustering:
        clustering_summary = {"by_chain": {}, "total_clusters": 0}
        try:
            # EVM chains: use EVMAdapter per chain
            for chain_name in active_evm_chains:
                try:
                    from ..clustering.engine import ClusteringEngine
                    engine = ClusteringEngine(cfg=cfg, chain_name=chain_name)
                    results = engine.run(
                        persist=True,
                        min_cluster_size=cfg.clustering_min_cluster_size,
                    )
                    clustering_summary["by_chain"][chain_name] = len(results)
                    clustering_summary["total_clusters"] += len(results)
                    logger.info("[%s] Clustering: %d clusters", chain_name, len(results))
                except Exception as exc:
                    logger.warning("[%s] Clustering failed (non-fatal): %s", chain_name, exc)
                    clustering_summary["by_chain"][chain_name] = {"error": str(exc)[:60]}

            # UTXO chains: use UTXOClusteringEngine per chain
            for chain_name in active_utxo_chains:
                if chain_name not in utxo_extract_results:
                    continue   # no data for this chain yet
                try:
                    from ..clustering.utxo_engine import UTXOClusteringEngine
                    engine = UTXOClusteringEngine(cfg=cfg, chain_name=chain_name)
                    results = engine.run(
                        persist=True,
                        min_cluster_size=1,
                    )
                    clustering_summary["by_chain"][chain_name] = len(results)
                    clustering_summary["total_clusters"] += len(results)
                    logger.info("[%s] UTXO Clustering: %d clusters", chain_name, len(results))
                except Exception as exc:
                    logger.warning("[%s] UTXO Clustering failed (non-fatal): %s", chain_name, exc)
                    clustering_summary["by_chain"][chain_name] = {"error": str(exc)[:60]}

            # Solana: use SolanaClusteringEngine
            if "solana" in utxo_extract_results:
                try:
                    from ..clustering.solana_engine import SolanaClusteringEngine
                    sol_engine = SolanaClusteringEngine(cfg=cfg)
                    sol_results = sol_engine.run(persist=True, min_cluster_size=2)
                    clustering_summary["by_chain"]["solana"] = len(sol_results)
                    clustering_summary["total_clusters"] += len(sol_results)
                    logger.info("[solana] Clustering: %d clusters", len(sol_results))
                except Exception as exc:
                    logger.warning("[solana] Clustering failed (non-fatal): %s", exc)
                    clustering_summary["by_chain"]["solana"] = {"error": str(exc)[:60]}

            logger.info(
                "All clustering complete: %d total clusters across %d chains",
                clustering_summary["total_clusters"],
                len(clustering_summary["by_chain"]),
            )
        except Exception as exc:
            logger.warning("Clustering stage failed (non-fatal): %s", exc)
            clustering_summary = {"error": str(exc)}

    # ── Placement — run per chain ─────────────────────────────────────────────
    placement_summary = None
    placement_result  = None   # Keep last ETH result for layering seed reuse
    if run_placement:
        all_chains = (
            list(active_evm_chains)
            + list(active_utxo_chains)
            + (["solana"] if "solana" in utxo_extract_results else [])
        )
        placement_summary = {"by_chain": {}, "total_placements": 0}
        for chain_name in all_chains:
            try:
                from ..analytics.placement import PlacementAnalysisEngine
                p_engine = PlacementAnalysisEngine(cfg=cfg, chain_name=chain_name)
                p_result = p_engine.run(source="mariadb", persist=True)
                placement_summary["by_chain"][chain_name] = len(p_result.placements)
                placement_summary["total_placements"] += len(p_result.placements)
                if chain_name == "ethereum":
                    placement_result = p_result   # reuse for layering seeds
                logger.info("[%s] Placement: %d alerts", chain_name, len(p_result.placements))
            except Exception as exc:
                logger.warning("[%s] Placement failed (non-fatal): %s", chain_name, exc)
                placement_summary["by_chain"][chain_name] = {"error": str(exc)[:60]}

        etl_summary_json["placements_found"] = placement_summary["total_placements"]

    # ── Layering — run per chain ──────────────────────────────────────────────
    layering_summary = None
    layering_result  = None   # Keep last ETH result for integration seed reuse
    if run_layering:
        all_chains = (
            list(active_evm_chains)
            + list(active_utxo_chains)
            + (["solana"] if "solana" in utxo_extract_results else [])
        )
        layering_summary = {"by_chain": {}, "total_alerts": 0, "utxo_hits": {}, "solana_hits": {}}
        for chain_name in all_chains:
            try:
                from ..analytics.layering import LayeringAnalysisEngine
                l_engine = LayeringAnalysisEngine(cfg=cfg, chain_name=chain_name)
                # Pass ETH placement result as seeds for ETH only; others run standalone
                seed_result = placement_result if chain_name == "ethereum" else None
                l_result = l_engine.run(
                    source="mariadb",
                    persist=True,
                    placement_result=seed_result,
                )
                layering_summary["by_chain"][chain_name] = len(l_result.alerts)
                layering_summary["total_alerts"] += len(l_result.alerts)
                if chain_name == "ethereum":
                    layering_result = l_result
                logger.info("[%s] Layering: %d alerts", chain_name, len(l_result.alerts))
            except Exception as exc:
                logger.warning("[%s] Layering failed (non-fatal): %s", chain_name, exc)
                layering_summary["by_chain"][chain_name] = {"error": str(exc)[:60]}

        etl_summary_json["layering_alerts"] = layering_summary["total_alerts"]

        # UTXO-specific layering detectors (CoinJoin, Change-Peeling, Multi-Hop)
        try:
            from ..analytics.utxo_aml import UTXOAMLDetector
            from ..clustering.utxo_adapter import UTXOAdapter
            for chain_name in active_utxo_chains:
                if chain_name not in utxo_extract_results:
                    continue
                try:
                    adapter = UTXOAdapter(cfg=cfg, chain_name=chain_name)
                    txs = list(adapter.iter_transactions(source="mariadb"))
                    if txs:
                        utxo_result = UTXOAMLDetector(cfg=cfg, chain_name=chain_name).run(txs)
                        layering_summary["utxo_hits"][chain_name] = utxo_result["total_hits"]
                        logger.info("[%s] UTXO AML: %d hits", chain_name, utxo_result["total_hits"])
                except Exception as exc:
                    logger.warning("[%s] UTXO AML failed (non-fatal): %s", chain_name, exc)
        except Exception as exc:
            logger.warning("UTXO AML stage failed (non-fatal): %s", exc)

        # Solana-specific layering detectors
        if "solana" in utxo_extract_results:
            try:
                from ..analytics.solana_aml import SolanaAMLDetector
                from ..clustering.solana_adapter import SolanaAdapter
                adapter = SolanaAdapter(cfg=cfg)
                sol_txs = list(adapter.iter_transactions(source="mariadb"))
                if sol_txs:
                    sol_result = SolanaAMLDetector(cfg=cfg).run(sol_txs)
                    layering_summary["solana_hits"] = {
                        "total": sol_result["total_hits"],
                        "bridge_hopping": len(sol_result["bridge_hopping"]),
                        "mixer": len(sol_result["mixer"]),
                        "cross_protocol": len(sol_result["cross_protocol"]),
                    }
                    logger.info("[solana] AML: %d hits", sol_result["total_hits"])
            except Exception as exc:
                logger.warning("[solana] AML stage failed (non-fatal): %s", exc)

    # ── Integration — run per chain ───────────────────────────────────────────
    integration_summary = None
    if run_integration:
        all_chains = (
            list(active_evm_chains)
            + list(active_utxo_chains)
            + (["solana"] if "solana" in utxo_extract_results else [])
        )
        integration_summary = {"by_chain": {}, "total_alerts": 0}
        for chain_name in all_chains:
            try:
                from ..analytics.integration import IntegrationAnalysisEngine
                i_engine = IntegrationAnalysisEngine(cfg=cfg, chain_name=chain_name)
                seed_layering = layering_result if chain_name == "ethereum" else None
                i_result = i_engine.run(
                    source="mariadb",
                    persist=True,
                    layering_result=seed_layering,
                )
                integration_summary["by_chain"][chain_name] = len(i_result.alerts)
                integration_summary["total_alerts"] += len(i_result.alerts)
                logger.info("[%s] Integration: %d alerts", chain_name, len(i_result.alerts))
            except Exception as exc:
                logger.warning("[%s] Integration failed (non-fatal): %s", chain_name, exc)
                integration_summary["by_chain"][chain_name] = {"error": str(exc)[:60]}

        etl_summary_json["integration_alerts"] = integration_summary["total_alerts"]

    # ── Finalize run record ───────────────────────────────────────────────────
    pipeline_completed_at = datetime.now(timezone.utc)
    if clustering_summary and not clustering_summary.get("error"):
        etl_summary_json["clusters_found"] = clustering_summary.get("total_clusters", 0)

    _persist_etl_run_record(
        cfg=cfg,
        run_id=etl_run_id,
        started_at=pipeline_started_at,
        completed_at=pipeline_completed_at,
        summary_json=etl_summary_json,
        status="completed",
    )

    logger.info(
        "Load stage complete | MariaDB: %s | Neo4j: %s | Mongo: %s",
        0 if mariadb_summary is None else mariadb_summary.get("transactions_loaded", 0),
        0 if neo4j_summary   is None else neo4j_summary.get("rows_loaded", 0),
        0 if mongo_summary   is None else mongo_summary.get("rows_loaded", 0),
    )
    # Close any long-lived DB/drivers to allow process exit when run as CLI
    try:
        from ..utils.connections import get_maria_engine, get_neo4j_driver, get_mongo_client
        try:
            engine = get_maria_engine(cfg)
            engine.dispose()
        except Exception:
            pass
        try:
            driver = get_neo4j_driver(cfg)
            # neo4j driver may be None in some configs
            if driver:
                driver.close()
        except Exception:
            pass
        try:
            client = get_mongo_client(cfg)
            client.close()
        except Exception:
            pass
    except Exception:
        # Best-effort cleanup — do not fail the pipeline
        logger.debug("Cleanup of DB clients/drivers failed or not available")
    return {
        "extract":      extract_results,
        "utxo_extract": utxo_extract_results,
        "transform":    transform_summary,
        "mongo_backup": mongo_summary,
        "mariadb":      mariadb_summary,
        "neo4j":        neo4j_summary,
        "clustering":   clustering_summary,
        "placement":    placement_summary,
        "layering":     layering_summary,
        "integration":  integration_summary,
    }
