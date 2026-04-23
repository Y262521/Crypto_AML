"""Layering detection API routes."""

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
            detail="MySQL is not connected. Layering data is unavailable.",
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


def ensure_layering_schema() -> None:
    """Create or migrate AML tables so layering routes can query safely."""

    global _SCHEMA_READY
    if _SCHEMA_READY:
        return

    cfg = _load_aml_config()
    from aml_pipeline.etl.load.mariadb_loader import create_tables_if_not_exist

    create_tables_if_not_exist(cfg)
    _SCHEMA_READY = True
    logger.info("Layering schema bootstrap completed for MySQL database %s", cfg.mysql_db)


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


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return default


def _humanize_method(method: str | None) -> str:
    labels = {
        "peeling_chain": "Peeling chains",
        "mixing_interaction": "Mixing & anonymity tool interaction",
        "bridge_hopping": "Cross-chain & bridge hopping",
        "shell_wallet_network": "Shell wallet networks",
        "high_depth_transaction_chaining": "High-depth transaction chaining",
    }
    normalized = str(method or "").strip()
    return labels.get(normalized, normalized.replace("_", " ").strip().title())


def _normalized_methods(methods: list[Any], method_scores: dict[str, Any]) -> list[str]:
    score_map = {
        str(key).strip(): _coerce_float(value)
        for key, value in (method_scores or {}).items()
        if str(key or "").strip()
    }
    ordered: list[str] = []
    seen: set[str] = set()
    for method in methods or []:
        normalized = str(method or "").strip()
        if not normalized or normalized in seen:
            continue
        ordered.append(normalized)
        seen.add(normalized)

    for method in score_map:
        if method not in seen:
            ordered.append(method)

    if not ordered:
        return []

    return sorted(
        ordered,
        key=lambda method: (score_map.get(method, 0.0), method),
        reverse=True,
    )


def _has_strong_secondary(methods: list[str], method_scores: dict[str, float]) -> bool:
    if len(methods) < 2:
        return False
    primary_score = _coerce_float(method_scores.get(methods[0]))
    secondary_score = _coerce_float(method_scores.get(methods[1]))
    if primary_score <= 0 or secondary_score <= 0:
        return False
    scale = 10.0 if primary_score > 1.0 else 1.0
    return secondary_score >= scale * 0.45 and secondary_score >= primary_score * 0.72


def _summarize_layering_reason(
    methods: list[str],
    reasons: list[Any],
    method_scores: dict[str, float],
    placement_behaviors: list[Any],
    metrics: dict[str, Any],
) -> str | None:
    cleaned_reasons = [str(reason).strip() for reason in reasons or [] if str(reason or "").strip()]
    primary_method = methods[0] if methods else None
    if not primary_method and cleaned_reasons:
        return cleaned_reasons[0]
    if not primary_method:
        return None

    primary_templates = {
        "peeling_chain": "Peeling chains dominate this entity, with value repeatedly shaved into smaller follow-on transfers.",
        "mixing_interaction": "Mixing and anonymity-tool interaction is the dominant layering signal around this entity.",
        "bridge_hopping": "Cross-chain and bridge hopping is the dominant signal, suggesting the flow re-entered after bridge use.",
        "shell_wallet_network": "Shell wallet network behavior dominates here, with funds cycling through a tightly connected wallet set.",
        "high_depth_transaction_chaining": "High-depth transaction chaining dominates here, with funds forwarded through long value-retaining hops.",
    }
    summary_parts = [primary_templates.get(primary_method, f"{_humanize_method(primary_method)} is the dominant layering signal for this entity.")]

    if _has_strong_secondary(methods, method_scores):
        summary_parts.append(
            f"{_humanize_method(methods[1])} also scores strongly enough to reinforce the same alert."
        )

    behaviors = [str(item).replace("_", " ").strip() for item in placement_behaviors or [] if str(item or "").strip()]
    if behaviors:
        summary_parts.append(f"Placement seeding for this entity was already linked to {', '.join(behaviors[:2])}.")

    bridge_pair_count = int(metrics.get("bridge_pair_count") or 0) if isinstance(metrics, dict) else 0
    if bridge_pair_count > 0:
        noun = "pair" if bridge_pair_count == 1 else "pairs"
        verb = "supports" if bridge_pair_count == 1 else "support"
        summary_parts.append(f"{bridge_pair_count} bridge-linked transfer {noun} {verb} the trace.")

    if cleaned_reasons:
        raw_reason = cleaned_reasons[0]
        if raw_reason.lower() not in " ".join(summary_parts).lower():
            summary_parts.append(raw_reason)

    return " ".join(summary_parts)


async def _latest_run() -> dict | None:
    return await fetch_one(
        """
        SELECT id, source, placement_run_id, status, started_at, completed_at, summary_json
        FROM layering_runs
        WHERE status = 'completed'
        ORDER BY completed_at DESC, created_at DESC
        LIMIT 1
        """
    )


async def _get_run(run_id: str | None = None) -> dict | None:
    if run_id:
        return await fetch_one(
            """
            SELECT id, source, placement_run_id, status, started_at, completed_at, summary_json
            FROM layering_runs
            WHERE id = %s
            """,
            (run_id,),
        )
    return await _latest_run()


async def _latest_run_safe(run_id: str | None = None) -> dict | None:
    ensure_layering_schema()
    try:
        return await _get_run(run_id)
    except ProgrammingError as exc:
        if exc.args and exc.args[0] == 1146:
            global _SCHEMA_READY
            _SCHEMA_READY = False
            ensure_layering_schema()
            return await _get_run(run_id)
        raise


async def _fetch_addresses_map(run_id: str, entity_ids: list[str]) -> dict[str, list[str]]:
    if not entity_ids:
        return {}
    placeholders = ", ".join(["%s"] * len(entity_ids))
    rows = await fetch_all(
        f"""
        SELECT entity_id, address
        FROM layering_entity_addresses
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


def _layering_payload(row: dict, addresses: list[str]) -> dict:
    method_scores = _decode_json(row.get("method_scores_json"), {})
    methods = _decode_json(row.get("methods_json"), [])
    reasons = _decode_json(row.get("reasons_json"), [])
    evidence_ids = _decode_json(row.get("evidence_ids_json"), [])
    supporting_tx_hashes = _decode_json(row.get("supporting_tx_hashes_json"), [])
    metrics = _decode_json(row.get("metrics_json"), {})
    placement_behaviors = _decode_json(row.get("placement_behaviors_json"), [])
    numeric_method_scores = {
        key: _coerce_float(value)
        for key, value in (method_scores or {}).items()
        if str(key or "").strip()
    }
    methods = _normalized_methods(methods, numeric_method_scores)
    reason = _summarize_layering_reason(
        methods=methods,
        reasons=reasons,
        method_scores=numeric_method_scores,
        placement_behaviors=placement_behaviors,
        metrics=metrics,
    )
    return {
        "entity_id": row.get("entity_id"),
        "entity_type": row.get("entity_type"),
        "addresses": addresses,
        "address_count": len(addresses),
        "confidence": _coerce_float(row.get("confidence_score")),
        "layering_score": _coerce_float(row.get("layering_score")),
        "risk_score": round(_coerce_float(row.get("layering_score")) * 100.0, 2),
        "placement_score": _coerce_float(row.get("placement_score")),
        "placement_confidence": _coerce_float(row.get("placement_confidence")),
        "methods": methods,
        "primary_method": methods[0] if methods else None,
        "method_scores": numeric_method_scores,
        "reasons": reasons,
        "reason": reason,
        "evidence_ids": evidence_ids,
        "evidence_count": len(evidence_ids),
        "supporting_tx_hashes": supporting_tx_hashes,
        "validation_status": row.get("validation_status"),
        "validation_confidence": _coerce_float(row.get("validation_confidence")),
        "source_kind": row.get("source_kind"),
        "placement_behaviors": placement_behaviors,
        "first_seen_at": _format_ts(row.get("first_seen_at")),
        "last_seen_at": _format_ts(row.get("last_seen_at")),
        "metrics": metrics,
    }


@router.get("/runs")
async def get_layering_runs():
    _require_mysql()
    ensure_layering_schema()
    rows = await fetch_all(
        """
        SELECT id, source, placement_run_id, completed_at, summary_json
        FROM layering_runs
        WHERE status = 'completed'
        ORDER BY completed_at DESC, created_at DESC
        LIMIT 10
        """
    )
    return [
        {
            "id": row.get("id"),
            "source": row.get("source"),
            "placement_run_id": row.get("placement_run_id"),
            "completed_at": _format_ts(row.get("completed_at")),
            "summary": _decode_json(row.get("summary_json"), {}),
        }
        for row in rows
    ]


@router.get("")
async def get_layering_alerts(
    limit: int = Query(50, ge=1, le=500),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    run_id: str | None = Query(None),
):
    _require_mysql()
    run = await _latest_run_safe(run_id)
    if not run:
        return {
            "run_id": None,
            "generated_at": None,
            "summary": {},
            "items": [],
        }

    rows = await fetch_all(
        """
        SELECT a.entity_id,
               a.entity_type,
               a.confidence_score,
               a.layering_score,
               a.placement_score,
               a.placement_confidence,
               a.method_scores_json,
               a.methods_json,
               a.reasons_json,
               a.supporting_tx_hashes_json,
               a.evidence_ids_json,
               a.metrics_json,
               a.first_seen_at,
               a.last_seen_at,
               e.validation_status,
               e.validation_confidence,
               e.source_kind,
               e.placement_behaviors_json
        FROM layering_alerts a
        JOIN layering_entities e
          ON e.run_id = a.run_id
         AND e.entity_id = a.entity_id
        WHERE a.run_id = %s
          AND a.confidence_score >= %s
        ORDER BY a.layering_score DESC, a.confidence_score DESC, a.entity_id ASC
        LIMIT %s
        """,
        (run["id"], min_confidence, limit),
    )
    entity_ids = [row["entity_id"] for row in rows]
    address_map = await _fetch_addresses_map(run["id"], entity_ids)

    return {
        "run_id": run["id"],
        "generated_at": _format_ts(run.get("completed_at")),
        "summary": _decode_json(run.get("summary_json"), {}),
        "items": [
            _layering_payload(row, address_map.get(row["entity_id"], []))
            for row in rows
        ],
    }


@router.get("/summary")
async def get_layering_summary(run_id: str | None = Query(None)):
    _require_mysql()
    run = await _latest_run_safe(run_id)
    if not run:
        return {
            "run_id": None,
            "generated_at": None,
            "summary": {},
            "top_alerts": [],
        }

    top_rows = await fetch_all(
        """
        SELECT entity_id, layering_score, methods_json
        FROM layering_alerts
        WHERE run_id = %s
        ORDER BY layering_score DESC, confidence_score DESC
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
                "layering_score": float(row.get("layering_score") or 0.0),
                "risk_score": round(float(row.get("layering_score") or 0.0) * 100.0, 2),
                "methods": _decode_json(row.get("methods_json"), []),
                "address_sample": address_map.get(row.get("entity_id"), [])[:3],
            }
            for row in top_rows
        ],
    }


@router.get("/{entity_id}")
async def get_layering_detail(entity_id: str, run_id: str | None = Query(None)):
    _require_mysql()
    run = await _latest_run_safe(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="No layering analysis run found")

    row = await fetch_one(
        """
        SELECT a.entity_id,
               a.entity_type,
               a.confidence_score,
               a.layering_score,
               a.placement_score,
               a.placement_confidence,
               a.method_scores_json,
               a.methods_json,
               a.reasons_json,
               a.supporting_tx_hashes_json,
               a.evidence_ids_json,
               a.metrics_json,
               a.first_seen_at,
               a.last_seen_at,
               e.validation_status,
               e.validation_confidence,
               e.source_kind,
               e.placement_behaviors_json
        FROM layering_alerts a
        JOIN layering_entities e
          ON e.run_id = a.run_id
         AND e.entity_id = a.entity_id
        WHERE a.run_id = %s
          AND a.entity_id = %s
        LIMIT 1
        """,
        (run["id"], entity_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Layering alert not found")

    address_map = await _fetch_addresses_map(run["id"], [entity_id])
    detections = await fetch_all(
        """
        SELECT detector_type,
               confidence_score,
               summary_text,
               score_components_json,
               metrics_json,
               supporting_tx_hashes_json,
               evidence_ids_json,
               first_observed_at,
               last_observed_at
        FROM layering_detector_hits
        WHERE run_id = %s
          AND entity_id = %s
        ORDER BY confidence_score DESC, detector_type ASC
        """,
        (run["id"], entity_id),
    )
    evidence = await fetch_all(
        """
        SELECT evidence_id,
               detector_type,
               evidence_type,
               title,
               summary_text,
               entity_ids_json,
               tx_hashes_json,
               path_json,
               metrics_json,
               first_seen_at,
               last_seen_at
        FROM layering_evidence
        WHERE run_id = %s
          AND entity_id = %s
        ORDER BY detector_type ASC, evidence_id ASC
        """,
        (run["id"], entity_id),
    )
    bridge_pairs = await fetch_all(
        """
        SELECT source_tx_hash,
               destination_tx_hash,
               bridge_contract,
               token_symbol,
               amount,
               latency_seconds,
               confidence_score,
               source_address,
               destination_address,
               details_json
        FROM layering_bridge_pairs
        WHERE run_id = %s
          AND entity_id = %s
        ORDER BY confidence_score DESC, amount DESC
        """,
        (run["id"], entity_id),
    )

    tx_hashes = set(_decode_json(row.get("supporting_tx_hashes_json"), []))
    for item in detections:
        tx_hashes.update(_decode_json(item.get("supporting_tx_hashes_json"), []))
    for item in evidence:
        tx_hashes.update(_decode_json(item.get("tx_hashes_json"), []))
    for pair in bridge_pairs:
        tx_hashes.update({pair.get("source_tx_hash"), pair.get("destination_tx_hash")})
    tx_hashes.discard(None)

    linked_transactions = []
    if tx_hashes:
        tx_hash_list = sorted(tx_hashes)[:100]
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
        "alert": _layering_payload(row, address_map.get(entity_id, [])),
        "detections": [
            {
                "detector_type": item.get("detector_type"),
                "confidence_score": float(item.get("confidence_score") or 0.0),
                "summary": item.get("summary_text"),
                "score_components": _decode_json(item.get("score_components_json"), {}),
                "metrics": _decode_json(item.get("metrics_json"), {}),
                "supporting_tx_hashes": _decode_json(item.get("supporting_tx_hashes_json"), []),
                "evidence_ids": _decode_json(item.get("evidence_ids_json"), []),
                "first_observed_at": _format_ts(item.get("first_observed_at")),
                "last_observed_at": _format_ts(item.get("last_observed_at")),
            }
            for item in detections
        ],
        "evidence": [
            {
                "evidence_id": item.get("evidence_id"),
                "detector_type": item.get("detector_type"),
                "evidence_type": item.get("evidence_type"),
                "title": item.get("title"),
                "summary": item.get("summary_text"),
                "entity_ids": _decode_json(item.get("entity_ids_json"), []),
                "tx_hashes": _decode_json(item.get("tx_hashes_json"), []),
                "path": _decode_json(item.get("path_json"), []),
                "metrics": _decode_json(item.get("metrics_json"), {}),
                "first_seen_at": _format_ts(item.get("first_seen_at")),
                "last_seen_at": _format_ts(item.get("last_seen_at")),
            }
            for item in evidence
        ],
        "bridge_pairs": [
            {
                "source_tx_hash": item.get("source_tx_hash"),
                "destination_tx_hash": item.get("destination_tx_hash"),
                "bridge_contract": item.get("bridge_contract"),
                "token_symbol": item.get("token_symbol"),
                "amount": float(item.get("amount") or 0.0),
                "latency_seconds": float(item.get("latency_seconds") or 0.0),
                "confidence_score": float(item.get("confidence_score") or 0.0),
                "source_address": item.get("source_address"),
                "destination_address": item.get("destination_address"),
                "details": _decode_json(item.get("details_json"), {}),
            }
            for item in bridge_pairs
        ],
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
