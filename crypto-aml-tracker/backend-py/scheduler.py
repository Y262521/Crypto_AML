"""
APScheduler — runs the ETL pipeline + analytics automatically.

Schedule (configurable via .env):
  PIPELINE_SCHEDULE_HOURS  — comma-separated hours to run (24h format)
  Default: "8,20"  → runs at 08:00 and 20:00 every day

What it does each run:
  1. Fetch new Ethereum blocks into raw MongoDB
  2. Transform all raw blocks -> load processed transactions into MariaDB and graph data into Neo4j
  3. Run clustering, placement, and layering analytics -> persist results to MySQL

Status is tracked in memory and exposed via /api/status.
"""

import logging
import os
import sys
import asyncio
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# ── shared state (read by /api/status) ───────────────────────────────────────
pipeline_status = {
    "last_run_at":       None,
    "last_run_status":   "never",   # "never" | "running" | "success" | "failed"
    "last_run_summary":  None,
    "next_run_at":       None,
    "runs_today":        0,
    "total_runs":        0,
}

_scheduler: AsyncIOScheduler | None = None


def _get_aml_root() -> Path:
    """Resolve the pipeline root directory relative to this file."""
    # crypto-aml-tracker/backend-py/scheduler.py → ../../AML
    return Path(__file__).resolve().parents[2] / "AML"


async def run_pipeline():
    """Execute the full ETL + analytics pipeline."""
    global pipeline_status

    pipeline_status["last_run_at"]     = datetime.now(timezone.utc).isoformat()
    pipeline_status["last_run_status"] = "running"
    pipeline_status["total_runs"]     += 1
    pipeline_status["runs_today"]     += 1

    logger.info("Scheduled pipeline run starting...")

    try:
        # Add the pipeline src directory to sys.path so we can import aml_pipeline
        aml_src = str(_get_aml_root() / "src")
        if aml_src not in sys.path:
            sys.path.insert(0, aml_src)

        # Load pipeline config pointing at the AML .env
        from dotenv import load_dotenv
        load_dotenv(_get_aml_root() / ".env")

        from aml_pipeline.config import load_config
        from aml_pipeline.pipelines.daily_pipeline import run_daily_pipeline

        cfg = load_config()

        # Run full pipeline: extract → transform → load → analytics
        summary = await asyncio.to_thread(
            run_daily_pipeline,
            cfg=cfg,
            run_clustering=True,
            skip_mongo_backup=True,
        )

        pipeline_status["last_run_status"]  = "success"
        pipeline_status["last_run_summary"] = {
            "blocks_extracted": summary.get("extract", [None, None])[1]
                if isinstance(summary.get("extract"), (list, tuple)) else None,
            "transactions_loaded": (summary.get("mariadb") or {}).get("transactions_loaded", 0),
            "neo4j_edges":         (summary.get("neo4j") or {}).get("rows_loaded", 0),
            "clusters_found":      (summary.get("clustering") or {}).get("clusters_found", 0),
            "placements_found":    (summary.get("placement") or {}).get("placements_found", 0),
            "behavior_hits":       (summary.get("placement") or {}).get("behavior_hits", 0),
            "layering_alerts":     (summary.get("layering") or {}).get("alerts_found", 0),
            "layering_detector_hits": (summary.get("layering") or {}).get("detector_hits", 0),
        }
        logger.info("Scheduled pipeline run completed: %s", pipeline_status["last_run_summary"])

    except Exception as exc:
        pipeline_status["last_run_status"]  = "failed"
        pipeline_status["last_run_summary"] = {"error": str(exc)}
        logger.error("Scheduled pipeline run failed: %s", exc, exc_info=True)


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    global _scheduler

    # Read schedule from env — default: 8am and 8pm
    hours_str = os.getenv("PIPELINE_SCHEDULE_HOURS", "8,20")
    hours = [h.strip() for h in hours_str.split(",") if h.strip()]
    hour_expr = ",".join(hours)

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        run_pipeline,
        trigger=CronTrigger(hour=hour_expr, minute=0),
        id="etl_pipeline",
        name="ETL + Analytics",
        replace_existing=True,
        misfire_grace_time=300,   # allow up to 5 min late start
    )

    _scheduler = scheduler
    logger.info("Scheduler configured: runs at hours %s UTC", hour_expr)
    return scheduler


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler


def get_next_run_time() -> str | None:
    if _scheduler is None:
        return None
    job = _scheduler.get_job("etl_pipeline")
    if job and job.next_run_time:
        return job.next_run_time.isoformat()
    return None
