"""
ETL Control Center API routes.

Endpoints:
  GET /api/etl/status         — live pipeline state, scheduler context, and per-stage health
  GET /api/etl/history        — paginated historical run log
  GET /api/etl/errors         — pipeline error / failed-run records
  GET /api/etl/databases/health (also mirrored at /api/databases/health)

Design principle
────────────────
All metrics are derived from persistent MySQL run records as the primary source
of truth.  The in-memory ``pipeline_status`` dict from scheduler.py is used as a
real-time overlay only when the server has a live run in progress — it resets on
every restart so it CANNOT be the sole source for lifetime counts, last-run
timestamps, or historical metrics.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from db.mongo import get_db as get_mongo_db
from db.mysql import fetch_all, fetch_one, get_pool
from db.neo4j import get_driver
from scheduler import pipeline_status, get_next_run_time
from settings import get_env, get_mongo_db_name, get_processed_collection_name

router = APIRouter()
logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────

def _fmt_ts(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _decode_json(value: Any) -> dict:
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {}


def _mysql_ok() -> bool:
    return get_pool() is not None


def _neo4j_ok() -> bool:
    return get_driver() is not None


def _mongo_ok() -> bool:
    return get_mongo_db() is not None


# ── persistent aggregate helpers ──────────────────────────────────────────────

async def _db_total_runs() -> int:
    """Count all ETL pipeline runs ever persisted in MySQL."""
    if not _mysql_ok():
        return 0
    try:
        row = await fetch_one("SELECT COUNT(*) AS cnt FROM placement_runs")
        return int((row or {}).get("cnt", 0))
    except Exception as exc:
        logger.debug("_db_total_runs failed: %s", exc)
        return 0


async def _db_last_success() -> str | None:
    """Return ISO timestamp of the most recent successfully completed run."""
    if not _mysql_ok():
        return None
    try:
        row = await fetch_one(
            """
            SELECT completed_at FROM placement_runs
            WHERE status = 'completed'
              AND completed_at IS NOT NULL
            ORDER BY completed_at DESC
            LIMIT 1
            """
        )
        return _fmt_ts((row or {}).get("completed_at"))
    except Exception as exc:
        logger.debug("_db_last_success failed: %s", exc)
        return None


async def _db_latest_run() -> dict | None:
    """Return the most recent placement_run row regardless of status."""
    if not _mysql_ok():
        return None
    try:
        row = await fetch_one(
            """
            SELECT id, status, chain_name, started_at, completed_at, summary_json
            FROM placement_runs
            ORDER BY started_at DESC
            LIMIT 1
            """
        )
        return row
    except Exception as exc:
        logger.debug("_db_latest_run failed: %s", exc)
        return None


async def _db_last_failed() -> str | None:
    """Return ISO timestamp of the most recent failed run from DB."""
    if not _mysql_ok():
        return None
    try:
        row = await fetch_one(
            """
            SELECT started_at FROM placement_runs
            WHERE status NOT IN ('completed', 'running')
            ORDER BY started_at DESC
            LIMIT 1
            """
        )
        return _fmt_ts((row or {}).get("started_at"))
    except Exception as exc:
        logger.debug("_db_last_failed failed: %s", exc)
        return None


async def _db_latest_summary() -> dict:
    """
    Return the best available ETL run summary from persistent records.

    Priority:
      1. summary_json on the most recent completed placement_run — if it
         contains ETL fields (blocks_extracted, transactions_loaded) this
         is used as-is.
      2. If the stored summary_json only has analytics fields (older runs
         written before this fix), we augment it with live aggregate counts
         from the transactions and wallet_clusters tables.
      3. If no placement_run exists at all, return aggregate DB counts so
         the ingestion metrics section still shows real numbers.
    """
    if not _mysql_ok():
        return {}

    stored: dict = {}
    try:
        row = await fetch_one(
            """
            SELECT summary_json FROM placement_runs
            WHERE status = 'completed'
              AND summary_json IS NOT NULL
            ORDER BY completed_at DESC
            LIMIT 1
            """
        )
        if row:
            stored = _decode_json(row.get("summary_json"))
    except Exception as exc:
        logger.debug("_db_latest_summary stored read failed: %s", exc)

    # If the stored summary already has ETL fields, return it directly.
    if stored.get("transactions_loaded") or stored.get("blocks_extracted"):
        # Backfill records_normalized for older runs that predate this field
        if stored.get("records_normalized") is None and stored.get("transactions_loaded"):
            stored = dict(stored)
            stored["records_normalized"] = stored["transactions_loaded"]
        return stored

    # Fall back: augment with live aggregate counts from DB tables.
    augmented = dict(stored)  # preserve any analytics fields
    try:
        tx_row = await fetch_one(
            "SELECT COUNT(*) AS cnt, MAX(block_number) AS max_block, MIN(block_number) AS min_block "
            "FROM transactions"
        )
        if tx_row:
            tx_count = int(tx_row.get("cnt") or 0)
            max_blk  = tx_row.get("max_block")
            min_blk  = tx_row.get("min_block")
            if tx_count > 0:
                augmented["transactions_loaded"]      = tx_count
                augmented["records_normalized"]       = tx_count
                augmented["transactions_total_in_db"] = tx_count
                if max_blk is not None:
                    augmented["extract_end_block"] = int(max_blk)
                if min_blk is not None:
                    augmented["extract_start_block"] = int(min_blk)
                if max_blk is not None and min_blk is not None:
                    augmented["blocks_extracted"] = int(max_blk) - int(min_blk) + 1

        cluster_row = await fetch_one("SELECT COUNT(*) AS cnt FROM wallet_clusters")
        if cluster_row:
            c = int(cluster_row.get("cnt") or 0)
            if c > 0:
                augmented.setdefault("clusters_found", c)

        if not augmented.get("placements_found"):
            p_row = await fetch_one(
                "SELECT COUNT(*) AS cnt FROM placement_detections pd "
                "JOIN placement_runs pr ON pr.id = pd.run_id "
                "WHERE pr.status = 'completed'"
            )
            if p_row and p_row.get("cnt"):
                augmented["placements_found"] = int(p_row["cnt"])

        if not augmented.get("layering_alerts"):
            l_row = await fetch_one(
                "SELECT COUNT(*) AS cnt FROM layering_alerts la "
                "JOIN layering_runs lr ON lr.id = la.run_id "
                "WHERE lr.status = 'completed'"
            )
            if l_row and l_row.get("cnt"):
                augmented["layering_alerts"] = int(l_row["cnt"])

    except Exception as exc:
        logger.debug("_db_latest_summary augmentation failed: %s", exc)

    return augmented


async def _db_runs_today() -> int:
    """Count placement_runs started today (UTC)."""
    if not _mysql_ok():
        return 0
    try:
        row = await fetch_one(
            "SELECT COUNT(*) AS cnt FROM placement_runs WHERE DATE(started_at) = CURDATE()"
        )
        return int((row or {}).get("cnt", 0))
    except Exception as exc:
        logger.debug("_db_runs_today failed: %s", exc)
        return 0


# ── GET /api/etl/status ────────────────────────────────────────────────────────

@router.get("/status")
async def get_etl_status():
    """
    Returns live pipeline activity state, per-stage status, and scheduler
    temporal checkpoints.

    Source priority:
    1. In-memory pipeline_status for the CURRENT run (resets on restart).
    2. MySQL persistent records for all historical / aggregated values.
    """
    mem = pipeline_status

    # ── 1. Determine activity_state ──────────────────────────────────────────
    mem_status = mem.get("last_run_status", "never")

    if mem_status == "running":
        activity_state = "running"
    elif mem_status == "failed":
        activity_state = "failed"
    elif mem_status == "success":
        activity_state = "success"
    else:
        latest_run = await _db_latest_run()
        if latest_run is None:
            activity_state = "idle"
        else:
            db_status = (latest_run.get("status") or "").lower()
            if db_status == "completed":
                activity_state = "success"
            elif db_status == "running":
                activity_state = "running"
            else:
                activity_state = "failed" if db_status == "failed" else "idle"

    # ── 2. Last run summary — prefer in-memory, fall back to DB ──────────────
    mem_summary = mem.get("last_run_summary")
    if isinstance(mem_summary, dict) and mem_summary and not mem_summary.get("error"):
        last_run_summary = mem_summary
    else:
        last_run_summary = await _db_latest_summary()
        if isinstance(mem_summary, dict) and mem_summary.get("error") and not last_run_summary:
            last_run_summary = mem_summary

    # ── 3. Per-stage status ───────────────────────────────────────────────────
    stage_keys = ["extract", "normalize", "load", "store", "ready"]
    stage_names = {
        "extract":   "Extract",
        "normalize": "Normalize",
        "load":      "Load",
        "store":     "Store",
        "ready":     "Ready",
    }
    stages = {k: {"name": stage_names[k], "status": "idle", "detail": None} for k in stage_keys}

    if activity_state == "running":
        for k in stage_keys:
            stages[k]["status"] = "running"
    elif activity_state in ("success", "failed"):
        target_status = "success" if activity_state == "success" else "failed"
        for k in stage_keys:
            stages[k]["status"] = target_status

    if last_run_summary and not last_run_summary.get("error"):
        blocks     = last_run_summary.get("blocks_extracted")
        tx_loaded  = last_run_summary.get("transactions_loaded")
        neo4j_e    = last_run_summary.get("neo4j_edges")
        normalized = last_run_summary.get("records_normalized")
        clusters   = last_run_summary.get("clusters_found")
        placements = last_run_summary.get("placements_found")
        layering   = last_run_summary.get("layering_alerts")

        if blocks is not None:
            stages["extract"]["detail"] = {"blocks_extracted": blocks, "transactions_processed": tx_loaded}
        if normalized is not None or tx_loaded is not None:
            stages["normalize"]["detail"] = {"records_normalized": normalized if normalized is not None else tx_loaded}
        if tx_loaded is not None:
            stages["load"]["detail"] = {"records_loaded_to_mysql": tx_loaded, "neo4j_edges": neo4j_e}
        if clusters is not None or neo4j_e is not None:
            stages["store"]["detail"] = {"clusters_found": clusters, "neo4j_edges": neo4j_e}
        if placements is not None or layering is not None:
            stages["ready"]["detail"] = {"placement_alerts": placements, "layering_alerts": layering}

    # ── 4. Temporal checkpoints ───────────────────────────────────────────────
    last_success_at = await _db_last_success()
    if activity_state == "failed":
        last_failed_at = mem.get("last_run_at") or await _db_last_failed()
    else:
        last_failed_at = await _db_last_failed()

    last_run_at = mem.get("last_run_at")
    if not last_run_at:
        lr = await _db_latest_run()
        if lr:
            last_run_at = _fmt_ts(lr.get("started_at"))

    # ── 5. Lifetime / today counts — always from DB ───────────────────────────
    db_total = await _db_total_runs()
    db_today = await _db_runs_today()
    total_runs = max(db_total, mem.get("total_runs", 0))
    runs_today = max(db_today, mem.get("runs_today", 0))

    # ── 6. Active chain ───────────────────────────────────────────────────────
    active_chain = get_env("ACTIVE_CHAIN", "ETH_CHAIN", default=None) or "ethereum"

    return {
        "server_time":      datetime.now(timezone.utc).isoformat(),
        "activity_state":   activity_state,
        "active_chain":     active_chain,
        "last_success_at":  last_success_at,
        "last_failed_at":   last_failed_at,
        "next_run_at":      get_next_run_time(),
        "schedule":         get_env("PIPELINE_SCHEDULE_HOURS", default="8,20") + ":00 UTC daily",
        "total_runs":       total_runs,
        "runs_today":       runs_today,
        "last_run_at":      last_run_at,
        "last_run_summary": last_run_summary or None,
        "stages":           list(stages.values()),
        "mysql_available":  _mysql_ok(),
        "neo4j_available":  _neo4j_ok(),
        "mongo_available":  _mongo_ok(),
    }


# ── GET /api/etl/history ──────────────────────────────────────────────────────

@router.get("/history")
async def get_etl_history(
    limit:  int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    chain:  str | None = Query(None),
):
    """Paginated historical ETL run records, newest first."""
    if not _mysql_ok():
        return {"items": [], "total": 0, "note": "MySQL unavailable"}

    try:
        chain_clause = ""
        args: tuple = ()
        if chain:
            chain_clause = "WHERE COALESCE(pr.chain_name, 'ethereum') = %s"
            args = (chain,)

        rows = await fetch_all(
            f"""
            SELECT
                pr.id              AS run_id,
                COALESCE(pr.chain_name, 'ethereum') AS chain_name,
                pr.source,
                pr.started_at,
                pr.completed_at,
                pr.status,
                pr.summary_json
            FROM placement_runs pr
            {chain_clause}
            ORDER BY pr.started_at DESC
            LIMIT %s OFFSET %s
            """,
            args + (limit, offset),
        )

        items = []
        for row in rows:
            summary = _decode_json(row.get("summary_json"))

            started = row.get("started_at")
            ended   = row.get("completed_at")
            duration_s: float | None = None
            if started and ended:
                try:
                    s = started if isinstance(started, datetime) else datetime.fromisoformat(str(started))
                    e = ended   if isinstance(ended,   datetime) else datetime.fromisoformat(str(ended))
                    duration_s = max(0.0, (e - s).total_seconds())
                except Exception:
                    pass

            blocks_extracted = summary.get("blocks_extracted")
            tx_loaded        = summary.get("transactions_loaded")
            neo4j_edges      = summary.get("neo4j_edges")
            normalized       = summary.get("records_normalized")
            clusters_found   = summary.get("clusters_found")
            placements_found = summary.get("placements_found")
            layering_alerts  = summary.get("layering_alerts")

            # For completed rows missing ETL fields, query run-specific analytics
            # counts (placement/layering) which ARE tied to run_id, but do NOT
            # fall back to global aggregates for transactions/clusters/neo4j
            # since those tables have no run_id column and would show the same
            # misleading value for every historical row.
            run_id = row.get("run_id")
            if run_id and row.get("status") == "completed":
                # Placement detections — run-specific query
                if placements_found is None:
                    try:
                        pd_row = await fetch_one(
                            "SELECT COUNT(*) AS cnt FROM placement_detections WHERE run_id = %s",
                            (run_id,),
                        )
                        if pd_row and pd_row.get("cnt") is not None:
                            placements_found = int(pd_row["cnt"])
                    except Exception:
                        pass

                # Layering alerts — run-specific query
                if layering_alerts is None:
                    try:
                        la_row = await fetch_one(
                            "SELECT COUNT(*) AS cnt FROM layering_alerts la "
                            "JOIN layering_runs lr ON lr.id = la.run_id "
                            "AND lr.placement_run_id = %s",
                            (run_id,),
                        )
                        if la_row and la_row.get("cnt") is not None:
                            layering_alerts = int(la_row["cnt"])
                    except Exception:
                        pass

            # For older runs that have transactions_loaded but no records_normalized
            # (written before the records_normalized field was added), backfill
            # records_normalized = transactions_loaded only when the run's own
            # summary_json confirms the transactions_loaded value is run-specific
            # (i.e. the summary_json also has blocks_extracted, meaning it was
            # written by daily_pipeline.py, not the analytics-only placement.py path).
            if normalized is None and tx_loaded is not None and blocks_extracted is not None:
                normalized = tx_loaded

            items.append({
                "run_id":                   run_id,
                "chain_target":             row.get("chain_name") or "ethereum",
                "source":                   row.get("source"),
                "start_time":               _fmt_ts(started),
                "end_time":                 _fmt_ts(ended),
                "duration_seconds":         duration_s,
                "status":                   row.get("status"),
                "blocks_processed":         blocks_extracted,
                "transactions_processed":   tx_loaded,
                "normalized_record_count":  normalized,
                "loaded_records_count":     tx_loaded,
                "neo4j_edges":              neo4j_edges,
                "clusters_found":           clusters_found,
                "placements_found":         placements_found,
                "layering_alerts":          layering_alerts,
                "raw_summary":              summary,
            })

        count_row = await fetch_one(
            f"SELECT COUNT(*) AS cnt FROM placement_runs {chain_clause}",
            args or None,
        )
        total = int((count_row or {}).get("cnt", 0))

        return {"items": items, "total": total}

    except Exception as exc:
        logger.error("etl/history query failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")


# ── GET /api/etl/errors ────────────────────────────────────────────────────────

@router.get("/errors")
async def get_etl_errors(
    limit:  int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    Returns pipeline exception / failure records.

    Sources:
      1. In-memory scheduler failure state (most recent, resets on restart)
      2. placement_runs rows where status is not 'completed'
      3. Stage-level errors from completed runs stored in summary_json
    """
    errors: list[dict] = []

    # Source 1: in-memory failure
    mem = pipeline_status
    if mem.get("last_run_status") == "failed":
        err_summary = mem.get("last_run_summary") or {}
        errors.append({
            "error_id":       "scheduler:last_failed",
            "timestamp":      mem.get("last_run_at"),
            "chain":          get_env("ACTIVE_CHAIN", default="ethereum"),
            "phase":          "pipeline_execution",
            "message":        err_summary.get("error") or "Pipeline run failed — see server logs for details",
            "severity":       "critical",
            "recovery_state": "awaiting_next_scheduled_run",
            "source":         "scheduler",
        })

    if _mysql_ok():
        # Source 2: persistent failed / non-completed runs
        try:
            failed_rows = await fetch_all(
                """
                SELECT id, chain_name, started_at, completed_at, status, summary_json
                FROM placement_runs
                WHERE status NOT IN ('completed')
                ORDER BY started_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            for row in failed_rows:
                summary    = _decode_json(row.get("summary_json"))
                status_val = (row.get("status") or "unknown").lower()
                err_msg    = (
                    summary.get("error")
                    or f"Run {row.get('id')} ended with status '{row.get('status')}'"
                )
                severity = "critical" if status_val in ("failed", "error") else "warning"
                recovery = "automatically_resumed" if status_val == "running" else "check_server_logs"
                errors.append({
                    "error_id":       f"placement_run:{row.get('id')}",
                    "timestamp":      _fmt_ts(row.get("started_at")),
                    "chain":          row.get("chain_name") or "ethereum",
                    "phase":          "pipeline_analysis",
                    "message":        err_msg,
                    "severity":       severity,
                    "recovery_state": recovery,
                    "source":         "placement_runs",
                    "run_id":         row.get("id"),
                    "raw_summary":    summary,
                })
        except Exception as exc:
            logger.warning("etl/errors placement_runs query failed: %s", exc)

        # Source 3: stage-level errors from completed runs (neo4j, placement, layering, etc.)
        try:
            recent_completed = await fetch_all(
                """
                SELECT id, chain_name, started_at, completed_at, summary_json
                FROM placement_runs
                WHERE status = 'completed'
                  AND summary_json IS NOT NULL
                ORDER BY completed_at DESC
                LIMIT 20
                """,
            )
            stage_error_fields = [
                ("neo4j_error",       "neo4j_load",           "warning"),
                ("placement_error",   "placement_analysis",   "warning"),
                ("layering_error",    "layering_analysis",    "warning"),
                ("integration_error", "integration_analysis", "warning"),
                ("clustering_error",  "clustering",           "warning"),
            ]
            for row in recent_completed:
                summary = _decode_json(row.get("summary_json"))
                for field, phase, sev in stage_error_fields:
                    err_val = summary.get(field)
                    if err_val:
                        errors.append({
                            "error_id":       f"stage_error:{row.get('id')}:{field}",
                            "timestamp":      _fmt_ts(row.get("completed_at") or row.get("started_at")),
                            "chain":          row.get("chain_name") or "ethereum",
                            "phase":          phase,
                            "message":        str(err_val),
                            "severity":       sev,
                            "recovery_state": "stage_skipped_pipeline_continued",
                            "source":         "placement_runs_summary",
                            "run_id":         row.get("id"),
                            "raw_summary":    summary,
                        })
        except Exception as exc:
            logger.warning("etl/errors stage-level error scan failed: %s", exc)

    # Deduplicate
    seen: set[str] = set()
    unique: list[dict] = []
    for e in errors:
        if e["error_id"] not in seen:
            seen.add(e["error_id"])
            unique.append(e)

    paginated = unique[offset: offset + limit]
    return {"items": paginated, "total": len(unique)}


# ── GET /api/etl/databases/health  (also mounted at /api/databases/health) ────

@router.get("/databases/health")
async def get_databases_health():
    """
    Returns connectivity status, record counts, and response latency
    for each underlying database engine.
    """
    results: list[dict] = []

    # ── 1. MongoDB ─────────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    mongo_status = "offline"
    mongo_latency: float | None = None
    mongo_raw_count: int | None = None
    mongo_proc_count: int | None = None
    mongo_last_updated: str | None = None

    try:
        mongo_db = get_mongo_db()
        if mongo_db is not None:
            raw_col_name  = get_env("MONGO_RAW_COLLECTION", "MONGO_COLLECTION", default="raw_blocks")
            proc_col_name = get_processed_collection_name()
            raw_col  = mongo_db[raw_col_name]
            proc_col = mongo_db[proc_col_name]
            mongo_raw_count  = await raw_col.estimated_document_count()
            mongo_proc_count = await proc_col.estimated_document_count()
            latest = await proc_col.find_one({}, sort=[("_id", -1)], projection={"_id": 1, "timestamp": 1})
            if latest and latest.get("timestamp"):
                mongo_last_updated = str(latest["timestamp"])
            mongo_status  = "online"
            mongo_latency = round((time.perf_counter() - t0) * 1000, 2)
    except Exception as exc:
        logger.debug("MongoDB health check: %s", exc)

    results.append({
        "engine": "MongoDB", "role": "Raw Blockchain Store",
        "status": mongo_status, "latency_ms": mongo_latency,
        "last_updated": mongo_last_updated,
        "collections": [
            {"name": get_env("MONGO_RAW_COLLECTION", "MONGO_COLLECTION", default="raw_blocks"), "count": mongo_raw_count},
            {"name": get_processed_collection_name(), "count": mongo_proc_count},
        ],
    })

    # ── 2. MySQL / MariaDB ─────────────────────────────────────────────────────
    t0 = time.perf_counter()
    mysql_status = "offline"
    mysql_latency: float | None = None
    mysql_tx_count: int | None  = None
    mysql_addr_count: int | None = None
    mysql_last_updated: str | None = None

    if _mysql_ok():
        try:
            tx_row   = await fetch_one("SELECT COUNT(*) AS cnt FROM transactions")
            addr_row = await fetch_one("SELECT COUNT(*) AS cnt FROM addresses")
            last_row = await fetch_one("SELECT MAX(timestamp) AS last_ts FROM transactions")
            mysql_tx_count    = int((tx_row   or {}).get("cnt", 0))
            mysql_addr_count  = int((addr_row or {}).get("cnt", 0))
            mysql_last_updated = _fmt_ts((last_row or {}).get("last_ts"))
            mysql_status  = "online"
            mysql_latency = round((time.perf_counter() - t0) * 1000, 2)
        except Exception as exc:
            logger.debug("MySQL health check: %s", exc)

    results.append({
        "engine": "MySQL / MariaDB", "role": "Normalized Relational Store",
        "status": mysql_status, "latency_ms": mysql_latency,
        "last_updated": mysql_last_updated,
        "tables": [
            {"name": "transactions", "count": mysql_tx_count},
            {"name": "addresses",    "count": mysql_addr_count},
        ],
    })

    # ── 3. Neo4j ───────────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    neo4j_status = "offline"
    neo4j_latency: float | None = None
    neo4j_node_count: int | None = None
    neo4j_edge_count: int | None = None
    neo4j_last_updated: str | None = None

    driver = get_driver()
    if driver is not None:
        try:
            database = get_env("NEO4J_DATABASE", default="neo4j")
            async with driver.session(database=database) as session:
                nr = await session.run("MATCH (n:Address) RETURN count(n) AS cnt")
                n_rec = await nr.single()
                er = await session.run("MATCH ()-[r:TRANSFER]->() RETURN count(r) AS cnt")
                e_rec = await er.single()
                lr = await session.run(
                    "MATCH ()-[r:TRANSFER]->() WHERE r.block_number IS NOT NULL "
                    "RETURN r.block_number AS bn ORDER BY r.block_number DESC LIMIT 1"
                )
                l_rec = await lr.single()
            neo4j_node_count = int(n_rec["cnt"]) if n_rec else 0
            neo4j_edge_count = int(e_rec["cnt"]) if e_rec else 0
            if l_rec and l_rec.get("bn") is not None:
                neo4j_last_updated = f"block #{l_rec['bn']}"
            neo4j_status  = "online"
            neo4j_latency = round((time.perf_counter() - t0) * 1000, 2)
        except Exception as exc:
            logger.debug("Neo4j health check: %s", exc)

    results.append({
        "engine": "Neo4j", "role": "Graph / Topology Store",
        "status": neo4j_status, "latency_ms": neo4j_latency,
        "last_updated": neo4j_last_updated,
        "nodes": [
            {"label": "Address",  "count": neo4j_node_count},
            {"label": "Transfer", "count": neo4j_edge_count},
        ],
    })

    # ── 4. Analysis Cache ──────────────────────────────────────────────────────
    t0 = time.perf_counter()
    cache_status = "offline"
    cache_latency: float | None = None
    cache_placement_count: int | None  = None
    cache_layering_count: int | None   = None
    cache_integration_count: int | None = None
    cache_last_updated: str | None = None

    if _mysql_ok():
        try:
            p_row  = await fetch_one("SELECT COUNT(*) AS cnt FROM placement_runs  WHERE status='completed'")
            lr_row = await fetch_one("SELECT COUNT(*) AS cnt FROM layering_runs   WHERE status='completed'")
            ir_row = await fetch_one("SELECT COUNT(*) AS cnt FROM integration_runs WHERE status='completed'")
            lu_row = await fetch_one(
                """
                SELECT MAX(completed_at) AS last_ts FROM (
                  SELECT completed_at FROM placement_runs   WHERE status='completed'
                  UNION ALL
                  SELECT completed_at FROM layering_runs    WHERE status='completed'
                  UNION ALL
                  SELECT completed_at FROM integration_runs WHERE status='completed'
                ) AS combined
                """
            )
            cache_placement_count   = int((p_row  or {}).get("cnt", 0))
            cache_layering_count    = int((lr_row or {}).get("cnt", 0))
            cache_integration_count = int((ir_row or {}).get("cnt", 0))
            cache_last_updated      = _fmt_ts((lu_row or {}).get("last_ts"))
            cache_status  = "online"
            cache_latency = round((time.perf_counter() - t0) * 1000, 2)
        except Exception as exc:
            logger.debug("Alert cache health check: %s", exc)

    results.append({
        "engine": "MySQL (Analysis Cache)", "role": "Alert / Analysis Cache",
        "status": cache_status, "latency_ms": cache_latency,
        "last_updated": cache_last_updated,
        "tables": [
            {"name": "placement_runs",   "count": cache_placement_count},
            {"name": "layering_runs",    "count": cache_layering_count},
            {"name": "integration_runs", "count": cache_integration_count},
        ],
    })

    return {"databases": results, "checked_at": datetime.now(timezone.utc).isoformat()}
