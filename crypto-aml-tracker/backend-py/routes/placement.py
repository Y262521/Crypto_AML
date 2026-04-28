"""Placement detection API routes."""

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
            detail="MySQL is not connected. Placement data is unavailable.",
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


def ensure_placement_schema() -> None:
    """Create or migrate AML tables so placement routes can query safely."""

    global _SCHEMA_READY
    if _SCHEMA_READY:
        return

    cfg = _load_aml_config()
    from aml_pipeline.etl.load.mariadb_loader import create_tables_if_not_exist

    create_tables_if_not_exist(cfg)
    _SCHEMA_READY = True
    logger.info("Placement schema bootstrap completed for MySQL database %s", cfg.mysql_db)


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
        FROM placement_runs
        WHERE status = 'completed'
        ORDER BY completed_at DESC, created_at DESC
        LIMIT 1
        """
    )


async def _get_run(run_id: str | None, before_date: str | None = None) -> dict | None:
    """Return a specific run by ID, by date, or the latest."""
    if run_id:
        return await fetch_one(
            "SELECT id, source, status, started_at, completed_at, summary_json FROM placement_runs WHERE id = %s",
            (run_id,),
        )
    if before_date:
        # Find the most recent completed run on or before the given date
        return await fetch_one(
            """
            SELECT id, source, status, started_at, completed_at, summary_json
            FROM placement_runs
            WHERE status = 'completed'
              AND DATE(completed_at) <= %s
            ORDER BY completed_at DESC
            LIMIT 1
            """,
            (before_date,),
        )
    return await _latest_run()


async def _latest_run_safe(run_id: str | None = None, before_date: str | None = None) -> dict | None:
    ensure_placement_schema()
    try:
        return await _get_run(run_id, before_date)
    except ProgrammingError as exc:
        if exc.args and exc.args[0] == 1146:
            global _SCHEMA_READY
            _SCHEMA_READY = False
            ensure_placement_schema()
            return await _get_run(run_id, before_date)
        raise


async def _fetch_entity_map(run_id: str, entity_ids: list[str]) -> dict[str, dict]:
    if not entity_ids:
        return {}
    placeholders = ", ".join(["%s"] * len(entity_ids))
    rows = await fetch_all(
        f"""
        SELECT entity_id, entity_type, validation_status, validation_confidence, source_kind, address_count, metrics_json
        FROM placement_entities
        WHERE run_id = %s
          AND entity_id IN ({placeholders})
        """,
        tuple([run_id, *entity_ids]),
    )
    return {
        row["entity_id"]: {
            "entity_id": row.get("entity_id"),
            "entity_type": row.get("entity_type"),
            "validation_status": row.get("validation_status"),
            "validation_confidence": float(row.get("validation_confidence") or 0.0),
            "source_kind": row.get("source_kind"),
            "address_count": int(row.get("address_count") or 0),
            "metrics": _decode_json(row.get("metrics_json"), {}),
        }
        for row in rows
    }


async def _fetch_addresses_map(run_id: str, entity_ids: list[str]) -> dict[str, list[str]]:
    if not entity_ids:
        return {}
    placeholders = ", ".join(["%s"] * len(entity_ids))
    rows = await fetch_all(
        f"""
        SELECT entity_id, address
        FROM placement_entity_addresses
        WHERE run_id = %s
          AND entity_id IN ({placeholders})
        ORDER BY address
        """,
        tuple([run_id, *entity_ids]),
    )
    address_map: dict[str, list[str]] = {}
    for row in rows:
        address_map.setdefault(row["entity_id"], []).append(row.get("address"))
    return address_map


def _placement_payload(row: dict, addresses: list[str], names_map: dict | None = None) -> dict:
    behaviors = _decode_json(row.get("behaviors_json"), [])
    reasons = _decode_json(row.get("reasons_json"), [])
    linked_root_entities = _decode_json(row.get("linked_root_entities_json"), [])
    supporting_tx_hashes = _decode_json(row.get("supporting_tx_hashes_json"), [])
    metrics = _decode_json(row.get("metrics_json"), {})
    behavior_profile = metrics.get("behavior_profile") if isinstance(metrics, dict) else {}
    if not isinstance(behavior_profile, dict):
        behavior_profile = {}
    banned = {"funneling", "funnel", "immediate_utilization", "immediate-utilization", "immediate utilization"}
    behaviors = [b for b in (behaviors or []) if (b or "").lower() not in banned]
    display_behaviors = [b for b in (behavior_profile.get("display_behaviors") or behaviors[:1]) if (b or "").lower() not in banned]
    primary_behavior = behavior_profile.get("primary_behavior") if (behavior_profile.get("primary_behavior") or "").lower() not in banned else (display_behaviors[0] if display_behaviors else None)

    # Resolve entity name from owner_list
    entity_name = None
    if names_map:
        entity_id = row.get("entity_id", "")
        entity_name = names_map.get(entity_id)
        if not entity_name:
            for addr in addresses:
                entity_name = names_map.get(addr)
                if entity_name:
                    break

    return {
        "entity_id": row.get("entity_id"),
        "entity_name": entity_name,  # None = unlabeled → frontend shows "Unknown"
        "entity_type": row.get("entity_type"),
        "addresses": addresses,
        "address_count": len(addresses),
        "confidence": float(row.get("confidence_score") or 0.0),
        "placement_score": float(row.get("placement_score") or 0.0),
        "risk_score": round(float(row.get("placement_score") or 0.0) * 100.0, 2),
        "behavior_score": float(row.get("behavior_score") or 0.0),
        "graph_position_score": float(row.get("graph_position_score") or 0.0),
        "temporal_score": float(row.get("temporal_score") or 0.0),
        "behaviors": display_behaviors,
        "all_behaviors": behaviors,
        "primary_behavior": primary_behavior,
        "behavior_profile": {
            "primary_behavior": primary_behavior,
            "display_behaviors": display_behaviors,
            "display_mode": behavior_profile.get("display_mode") or ("dominant" if display_behaviors else "none"),
            "ranked_behaviors": [rb for rb in (behavior_profile.get("ranked_behaviors") or []) if (rb.get("behavior_type") or "").lower() not in banned],
        },
        "reasons": reasons,
        "reason": reasons[0] if reasons else None,
        "linked_root_entities": linked_root_entities,
        "supporting_tx_hashes": supporting_tx_hashes,
        "validation_status": row.get("validation_status"),
        "validation_confidence": float(row.get("validation_confidence") or 0.0),
        "source_kind": row.get("source_kind"),
        "first_seen_at": _format_ts(row.get("first_seen_at")),
        "last_seen_at": _format_ts(row.get("last_seen_at")),
        "metrics": metrics,
    }


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


def _build_trace_paths(
    rows: list[dict],
    entity_map: dict[str, dict],
    address_map: dict[str, list[str]],
) -> list[dict]:
    grouped: dict[tuple[str, int], list[dict]] = {}
    for row in rows:
        grouped.setdefault((row["root_entity_id"], int(row["path_index"] or 0)), []).append(row)

    trace_paths: list[dict] = []
    for (root_entity_id, path_index), path_rows in grouped.items():
        ordered = sorted(path_rows, key=lambda item: int(item.get("depth") or 0))
        nodes: list[str] = []
        for row in ordered:
            upstream = row.get("upstream_entity_id")
            downstream = row.get("downstream_entity_id")
            if upstream and not nodes:
                nodes.append(upstream)
            if downstream:
                nodes.append(downstream)
        if not nodes and ordered:
            nodes.append(ordered[0].get("upstream_entity_id"))

        trace_paths.append(
            {
                "path_index": path_index,
                "root_entity_id": root_entity_id,
                "origin_entity_id": ordered[0].get("origin_entity_id"),
                "score": float(ordered[0].get("path_score") or 0.0),
                "terminal_reason": next(
                    (row.get("terminal_reason") for row in reversed(ordered) if row.get("terminal_reason")),
                    None,
                ),
                "nodes": [
                    {
                        **entity_map.get(entity_id, {"entity_id": entity_id}),
                        "addresses": address_map.get(entity_id, []),
                    }
                    for entity_id in nodes
                    if entity_id
                ],
                "edges": [
                    {
                        "depth": int(row.get("depth") or 0),
                        "upstream_entity_id": row.get("upstream_entity_id"),
                        "downstream_entity_id": row.get("downstream_entity_id"),
                        "path_score": float(row.get("path_score") or 0.0),
                        "edge_value_eth": float(row.get("edge_value_eth") or 0.0),
                        "supporting_tx_hashes": _decode_json(row.get("supporting_tx_hashes_json"), []),
                        "first_seen_at": _format_ts(row.get("first_seen_at")),
                        "last_seen_at": _format_ts(row.get("last_seen_at")),
                    }
                    for row in ordered
                ],
            }
        )

    trace_paths.sort(key=lambda path: (path["score"], -len(path["nodes"])), reverse=True)
    return trace_paths


@router.get("/runs")
async def get_placement_runs():
    """Return the last 10 completed placement runs for the run selector."""
    _require_mysql()
    ensure_placement_schema()
    try:
        rows = await fetch_all(
            """
            SELECT id, source, status, started_at, completed_at, summary_json
            FROM placement_runs
            WHERE status = 'completed'
            ORDER BY completed_at DESC, created_at DESC
            LIMIT 10
            """
        )
        return [
            {
                "id": row["id"],
                "source": row.get("source"),
                "completed_at": _format_ts(row.get("completed_at")),
                "started_at": _format_ts(row.get("started_at")),
                "summary": _decode_json(row.get("summary_json"), {}),
            }
            for row in rows
        ]
    except Exception as exc:
        logger.warning("Failed to fetch placement runs: %s", exc)
        return []


@router.get("/")
async def get_placements(
    limit: int = Query(50, ge=1, le=500),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    run_id: str | None = Query(None),
    before_date: str | None = Query(None),
):
    _require_mysql()
    run = await _latest_run_safe(run_id, before_date)
    if not run:
        return {
            "run_id": None,
            "generated_at": None,
            "summary": {},
            "items": [],
        }

    rows = await fetch_all(
        """
        SELECT d.entity_id,
               d.entity_type,
               d.confidence_score,
               d.placement_score,
               d.behavior_score,
               d.graph_position_score,
               d.temporal_score,
               d.reasons_json,
               d.behaviors_json,
               d.linked_root_entities_json,
               d.supporting_tx_hashes_json,
               d.metrics_json,
               d.first_seen_at,
               d.last_seen_at,
               e.validation_status,
               e.validation_confidence,
               e.source_kind
        FROM placement_detections d
        JOIN placement_entities e
          ON e.run_id = d.run_id
         AND e.entity_id = d.entity_id
        WHERE d.run_id = %s
          AND d.confidence_score >= %s
        ORDER BY d.placement_score DESC, d.confidence_score DESC, d.entity_id ASC
        LIMIT %s
        """,
        (run["id"], min_confidence, limit),
    )
    entity_ids = [row["entity_id"] for row in rows]
    address_map = await _fetch_addresses_map(run["id"], entity_ids)
    all_addresses = [addr for addrs in address_map.values() for addr in addrs] + entity_ids
    names_map = await _fetch_names_map(all_addresses)

    return {
        "run_id": run["id"],
        "generated_at": _format_ts(run.get("completed_at")),
        "summary": _decode_json(run.get("summary_json"), {}),
        "items": [
            _placement_payload(row, address_map.get(row["entity_id"], []), names_map)
            for row in rows
        ],
    }


@router.get("/summary")
async def get_placement_summary():
    _require_mysql()
    run = await _latest_run_safe()
    if not run:
        return {
            "run_id": None,
            "generated_at": None,
            "summary": {},
            "top_alerts": [],
        }

    top_rows = await fetch_all(
        """
        SELECT entity_id, placement_score
        FROM placement_detections
        WHERE run_id = %s
        ORDER BY placement_score DESC, confidence_score DESC
        LIMIT 5
        """,
        (run["id"],),
    )
    entity_ids = [row["entity_id"] for row in top_rows]
    address_map = await _fetch_addresses_map(run["id"], entity_ids)

    return {
        "run_id": run["id"],
        "generated_at": _format_ts(run.get("completed_at")),
        "summary": _decode_json(run.get("summary_json"), {}),
        "top_alerts": [
            {
                "entity_id": row.get("entity_id"),
                "placement_score": float(row.get("placement_score") or 0.0),
                "risk_score": round(float(row.get("placement_score") or 0.0) * 100.0, 2),
                "address_sample": address_map.get(row.get("entity_id"), [])[:3],
            }
            for row in top_rows
        ],
    }



@router.get("/{entity_id}")
async def get_placement_detail(entity_id: str):
    _require_mysql()
    run = await _latest_run_safe()
    if not run:
        raise HTTPException(status_code=404, detail="No placement analysis run found")

    row = await fetch_one(
        """
        SELECT d.entity_id,
               d.entity_type,
               d.confidence_score,
               d.placement_score,
               d.behavior_score,
               d.graph_position_score,
               d.temporal_score,
               d.reasons_json,
               d.behaviors_json,
               d.linked_root_entities_json,
               d.supporting_tx_hashes_json,
               d.metrics_json,
               d.first_seen_at,
               d.last_seen_at,
               e.validation_status,
               e.validation_confidence,
               e.source_kind
        FROM placement_detections d
        JOIN placement_entities e
          ON e.run_id = d.run_id
         AND e.entity_id = d.entity_id
        WHERE d.run_id = %s
          AND d.entity_id = %s
        LIMIT 1
        """,
        (run["id"], entity_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Placement alert not found")

    behaviors = await fetch_all(
        """
        SELECT behavior_type,
               confidence_score,
               metrics_json,
               supporting_tx_hashes_json,
               first_observed_at,
               last_observed_at
        FROM placement_behaviors
        WHERE run_id = %s
          AND entity_id = %s
        ORDER BY confidence_score DESC, behavior_type ASC
        """,
        (run["id"], entity_id),
    )
    # defensive filter to remove banned behavior types from detail responses
    _banned = {"funneling", "funnel", "immediate_utilization", "immediate-utilization", "immediate utilization"}
    behaviors = [b for b in behaviors if (b.get("behavior_type") or "").lower() not in _banned]
    labels = await fetch_all(
        """
        SELECT label, label_source, confidence_score, explanation
        FROM placement_labels
        WHERE run_id = %s
          AND entity_id = %s
        ORDER BY confidence_score DESC, label ASC
        """,
        (run["id"], entity_id),
    )
    trace_rows = await fetch_all(
        """
        SELECT root_entity_id,
               origin_entity_id,
               path_index,
               depth,
               upstream_entity_id,
               downstream_entity_id,
               path_score,
               is_terminal,
               terminal_reason,
               edge_value_eth,
               supporting_tx_hashes_json,
               first_seen_at,
               last_seen_at
        FROM placement_traces
        WHERE run_id = %s
          AND origin_entity_id = %s
        ORDER BY path_index ASC, depth ASC
        """,
        (run["id"], entity_id),
    )

    trace_entity_ids = sorted(
        {
            node_id
            for row_item in trace_rows
            for node_id in (row_item.get("upstream_entity_id"), row_item.get("downstream_entity_id"))
            if node_id
        }
    )
    entity_map = await _fetch_entity_map(run["id"], trace_entity_ids)
    address_map = await _fetch_addresses_map(run["id"], sorted(set(trace_entity_ids + [entity_id])))
    trace_paths = _build_trace_paths(trace_rows, entity_map, address_map)

    tx_hashes = set(_decode_json(row.get("supporting_tx_hashes_json"), []))
    for behavior in behaviors:
        tx_hashes.update(_decode_json(behavior.get("supporting_tx_hashes_json"), []))
    for trace_row in trace_rows:
        tx_hashes.update(_decode_json(trace_row.get("supporting_tx_hashes_json"), []))

    linked_transactions = []
    if tx_hashes:
        tx_hash_list = sorted(tx_hashes)[:50]
        placeholders = ", ".join(["%s"] * len(tx_hash_list))
        linked_transactions = await fetch_all(
            f"""
            SELECT tx_hash, from_address, to_address, value_eth, timestamp, block_number
            FROM transactions
            WHERE tx_hash IN ({placeholders})
            ORDER BY timestamp ASC, block_number ASC, tx_hash ASC
            """,
            tuple(tx_hash_list),
        )

    return {
        "run_id": run["id"],
        "generated_at": _format_ts(run.get("completed_at")),
        "summary": _decode_json(run.get("summary_json"), {}),
        "placement": _placement_payload(row, address_map.get(entity_id, [])),
        "behaviors": [
            {
                "behavior_type": item.get("behavior_type"),
                "confidence_score": float(item.get("confidence_score") or 0.0),
                "metrics": _decode_json(item.get("metrics_json"), {}),
                "supporting_tx_hashes": _decode_json(item.get("supporting_tx_hashes_json"), []),
                "first_observed_at": _format_ts(item.get("first_observed_at")),
                "last_observed_at": _format_ts(item.get("last_observed_at")),
            }
            for item in behaviors
        ],
        "labels": [
            {
                "label": item.get("label"),
                "source": item.get("label_source"),
                "confidence_score": float(item.get("confidence_score") or 0.0),
                "explanation": item.get("explanation"),
            }
            for item in labels
        ],
        "trace_paths": trace_paths,
        "linked_transactions": [
            {
                "tx_hash": tx.get("tx_hash"),
                "from_address": tx.get("from_address"),
                "to_address": tx.get("to_address"),
                "value_eth": float(tx.get("value_eth") or 0.0),
                "timestamp": _format_ts(tx.get("timestamp")),
                "block_number": int(tx.get("block_number") or 0),
            }
            for tx in linked_transactions
        ],
    }
