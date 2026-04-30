"""Integration detection API routes."""

from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
import sys
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pymysql.err import ProgrammingError

from db.mysql import fetch_all, fetch_one, get_pool

router = APIRouter()
logger = logging.getLogger(__name__)
_SCHEMA_READY = False


def _require_mysql() -> None:
    if get_pool() is None:
        raise HTTPException(
            status_code=503,
            detail="MySQL is not connected. Integration data is unavailable.",
        )


def _aml_root() -> Path:
    return Path(__file__).resolve().parents[3] / "AML"


def _load_aml_config():
    aml_root = _aml_root()
    aml_src = str(aml_root / "src")
    if aml_src not in sys.path:
        sys.path.insert(0, aml_src)
    from dotenv import load_dotenv
    load_dotenv(aml_root / ".env")
    from aml_pipeline.config import load_config
    return load_config()


def ensure_integration_schema() -> None:
    """Create integration tables if they don't exist."""
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    cfg = _load_aml_config()
    from aml_pipeline.etl.load.mariadb_loader import create_tables_if_not_exist
    create_tables_if_not_exist(cfg)
    _SCHEMA_READY = True
    logger.info("Integration schema bootstrap completed for MySQL database %s", cfg.mysql_db)


def _decode_json(value: Any, default):
    if value in (None, "", b""):
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _format_ts(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


async def _latest_run() -> dict | None:
    return await fetch_one(
        """
        SELECT id, source, status, started_at, completed_at, summary_json
        FROM integration_runs
        WHERE status = 'completed'
        ORDER BY completed_at DESC, created_at DESC
        LIMIT 1
        """
    )


async def _get_run(run_id: str | None, before_date: str | None = None) -> dict | None:
    if run_id:
        return await fetch_one(
            "SELECT id, source, status, started_at, completed_at, summary_json FROM integration_runs WHERE id = %s",
            (run_id,),
        )
    if before_date:
        return await fetch_one(
            """
            SELECT id, source, status, started_at, completed_at, summary_json
            FROM integration_runs
            WHERE status = 'completed'
              AND DATE(completed_at) <= %s
            ORDER BY completed_at DESC
            LIMIT 1
            """,
            (before_date,),
        )
    return await _latest_run()


async def _latest_run_safe(run_id: str | None = None, before_date: str | None = None) -> dict | None:
    ensure_integration_schema()
    try:
        return await _get_run(run_id, before_date)
    except ProgrammingError:
        return None
    except Exception as exc:
        logger.warning("Could not fetch integration run: %s", exc)
        return None


async def _fetch_names_map(addresses: list[str]) -> dict[str, str]:
    """Look up owner names for a list of addresses from owner_list_addresses."""
    if not addresses:
        return {}
    placeholders = ", ".join(["%s"] * len(addresses))
    try:
        rows = await fetch_all(
            f"""
            SELECT ola.address, ol.full_name
            FROM owner_list_addresses ola
            JOIN owner_list ol ON ol.id = ola.owner_list_id
            WHERE ola.address IN ({placeholders})
            """,
            tuple(addresses),
        )
        return {row["address"]: row["full_name"] for row in rows}
    except Exception:
        return {}


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/runs")
async def get_integration_runs():
    """Return all completed integration runs sorted newest first."""
    _require_mysql()
    ensure_integration_schema()
    try:
        rows = await fetch_all(
            """
            SELECT id, source, status, started_at, completed_at, summary_json
            FROM integration_runs
            WHERE status = 'completed'
            ORDER BY completed_at DESC
            LIMIT 50
            """
        )
        return [
            {
                "id": r["id"],
                "source": r.get("source", "auto"),
                "status": r.get("status", "completed"),
                "started_at": _format_ts(r.get("started_at")),
                "completed_at": _format_ts(r.get("completed_at")),
                "summary": _decode_json(r.get("summary_json"), {}),
            }
            for r in (rows or [])
        ]
    except ProgrammingError:
        return []
    except Exception as exc:
        logger.warning("get_integration_runs failed: %s", exc)
        return []


@router.get("/summary")
async def get_integration_summary(
    run_id: str | None = Query(default=None),
    before_date: str | None = Query(default=None, alias="beforeDate"),
):
    """Return summary stats for the latest (or specified) integration run."""
    _require_mysql()
    run = await _latest_run_safe(run_id, before_date)
    if not run:
        return {
            "run_id": None,
            "summary": {
                "alerts": 0,
                "high_confidence_alerts": 0,
                "convergence_signals": 0,
                "dormancy_signals": 0,
                "terminal_signals": 0,
                "reaggregation_signals": 0,
            },
        }
    summary = _decode_json(run.get("summary_json"), {})
    return {
        "run_id": run["id"],
        "completed_at": _format_ts(run.get("completed_at")),
        "summary": summary,
    }


@router.get("/")
async def get_integration_alerts(
    run_id: str | None = Query(default=None),
    before_date: str | None = Query(default=None, alias="beforeDate"),
    limit: int = Query(default=200, ge=1, le=1000),
    min_score: float = Query(default=0.0, alias="minScore"),
    signal: str | None = Query(default=None),
):
    """Return integration alerts for the latest (or specified) run."""
    _require_mysql()
    run = await _latest_run_safe(run_id, before_date)
    if not run:
        return {"run_id": None, "items": []}

    active_run_id = run["id"]

    try:
        rows = await fetch_all(
            """
            SELECT
                entity_id, entity_type,
                integration_score, confidence_score,
                signals_fired_json, signal_scores_json,
                reasons_json, supporting_tx_hashes_json,
                layering_score, placement_score,
                metrics_json, first_seen_at, last_seen_at
            FROM integration_alerts
            WHERE run_id = %s
              AND integration_score >= %s
            ORDER BY integration_score DESC, confidence_score DESC
            LIMIT %s
            """,
            (active_run_id, min_score, limit),
        )
    except ProgrammingError:
        return {"run_id": active_run_id, "items": []}

    # Apply signal filter, then batch-fetch owner names
    filtered_rows = [
        r for r in (rows or [])
        if not signal or signal in _decode_json(r.get("signals_fired_json"), [])
    ]

    all_addresses = [r["entity_id"] for r in filtered_rows if r.get("entity_id")]
    names_map = await _fetch_names_map(all_addresses)

    items = []
    for r in filtered_rows:
        signals_fired = _decode_json(r.get("signals_fired_json"), [])
        signal_scores = _decode_json(r.get("signal_scores_json"), {})
        reasons = _decode_json(r.get("reasons_json"), [])
        metrics = _decode_json(r.get("metrics_json"), {})
        entity_id = r["entity_id"]

        items.append({
            "entity_id": entity_id,
            "entity_name": names_map.get(entity_id),  # None → frontend shows "Unknown"
            "entity_type": r.get("entity_type", "address"),
            "addresses": [entity_id],
            "integration_score": float(r.get("integration_score") or 0),
            "confidence_score": float(r.get("confidence_score") or 0),
            "signals_fired": signals_fired,
            "signal_scores": signal_scores,
            "primary_signal": signals_fired[0] if signals_fired else None,
            "reasons": reasons,
            "reason": reasons[0] if reasons else None,
            "layering_score": float(r.get("layering_score") or 0),
            "placement_score": float(r.get("placement_score") or 0),
            "metrics": metrics,
            "first_seen_at": _format_ts(r.get("first_seen_at")),
            "last_seen_at": _format_ts(r.get("last_seen_at")),
        })

    return {"run_id": active_run_id, "items": items}
