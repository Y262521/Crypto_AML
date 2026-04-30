"""Chain of Custody API — joins Placement → Layering → Integration for one entity."""

from __future__ import annotations

from datetime import datetime
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pymysql.err import ProgrammingError

from db.mysql import fetch_all, fetch_one, get_pool
from db.neo4j import get_driver

router = APIRouter()
logger = logging.getLogger(__name__)


def _decode_json(value: Any, default):
    if value in (None, "", b""):
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _fmt(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _require_mysql() -> None:
    if get_pool() is None:
        raise HTTPException(status_code=503, detail="MySQL unavailable")


# ── helpers ───────────────────────────────────────────────────────────────────

async def _resolve_addresses(entity_id: str) -> list[str]:
    """Collect all addresses associated with an entity across all three stages."""
    addresses: set[str] = {entity_id.lower()}

    for table, col in [
        ("placement_entity_addresses", "entity_id"),
        ("layering_entity_addresses", "entity_id"),
    ]:
        try:
            rows = await fetch_all(
                f"SELECT address FROM {table} WHERE {col} = %s", (entity_id,)
            )
            for r in rows or []:
                if r.get("address"):
                    addresses.add(r["address"].lower())
        except ProgrammingError:
            pass

    return sorted(addresses)


async def _fetch_placement_stage(entity_id: str, addresses: list[str]) -> dict | None:
    """Fetch the latest placement detection for this entity or any of its addresses."""
    placeholders = ", ".join(["%s"] * len(addresses))
    try:
        # Try direct entity_id match first
        row = await fetch_one(
            """
            SELECT pd.entity_id, pd.entity_type, pd.placement_score,
                   pd.confidence_score, pd.behaviors_json, pd.reasons_json,
                   pd.supporting_tx_hashes_json, pd.first_seen_at, pd.last_seen_at,
                   pd.run_id
            FROM placement_detections pd
            WHERE pd.entity_id = %s
            ORDER BY pd.placement_score DESC
            LIMIT 1
            """,
            (entity_id,),
        )
        if not row:
            # Try via address membership
            row = await fetch_one(
                f"""
                SELECT pd.entity_id, pd.entity_type, pd.placement_score,
                       pd.confidence_score, pd.behaviors_json, pd.reasons_json,
                       pd.supporting_tx_hashes_json, pd.first_seen_at, pd.last_seen_at,
                       pd.run_id
                FROM placement_detections pd
                JOIN placement_entity_addresses pea
                  ON pea.run_id = pd.run_id AND pea.entity_id = pd.entity_id
                WHERE pea.address IN ({placeholders})
                ORDER BY pd.placement_score DESC
                LIMIT 1
                """,
                tuple(addresses),
            )
        if not row:
            return None

        # Fetch trace paths for this entity
        traces = await fetch_all(
            """
            SELECT upstream_entity_id, downstream_entity_id, depth,
                   path_index, edge_value_eth, supporting_tx_hashes_json,
                   first_seen_at, last_seen_at, terminal_reason
            FROM placement_traces
            WHERE run_id = %s AND origin_entity_id = %s
            ORDER BY path_index, depth
            LIMIT 50
            """,
            (row["run_id"], row["entity_id"]),
        )

        return {
            "stage": "placement",
            "entity_id": row["entity_id"],
            "entity_type": row.get("entity_type", "address"),
            "placement_score": float(row.get("placement_score") or 0),
            "confidence_score": float(row.get("confidence_score") or 0),
            "behaviors": _decode_json(row.get("behaviors_json"), []),
            "reasons": _decode_json(row.get("reasons_json"), []),
            "supporting_tx_hashes": _decode_json(row.get("supporting_tx_hashes_json"), []),
            "first_seen_at": _fmt(row.get("first_seen_at")),
            "last_seen_at": _fmt(row.get("last_seen_at")),
            "trace_paths": [
                {
                    "upstream": t.get("upstream_entity_id"),
                    "downstream": t.get("downstream_entity_id"),
                    "depth": t.get("depth"),
                    "path_index": t.get("path_index"),
                    "value_eth": float(t.get("edge_value_eth") or 0),
                    "tx_hashes": _decode_json(t.get("supporting_tx_hashes_json"), []),
                    "terminal_reason": t.get("terminal_reason"),
                }
                for t in (traces or [])
            ],
        }
    except ProgrammingError:
        return None


async def _fetch_layering_stage(entity_id: str, addresses: list[str]) -> dict | None:
    """Fetch the latest layering alert for this entity or any of its addresses."""
    placeholders = ", ".join(["%s"] * len(addresses))
    try:
        row = await fetch_one(
            """
            SELECT la.entity_id, la.entity_type, la.layering_score,
                   la.confidence_score, la.methods_json, la.reasons_json,
                   la.supporting_tx_hashes_json, la.evidence_ids_json,
                   la.first_seen_at, la.last_seen_at, la.run_id
            FROM layering_alerts la
            WHERE la.entity_id = %s
            ORDER BY la.layering_score DESC
            LIMIT 1
            """,
            (entity_id,),
        )
        if not row:
            row = await fetch_one(
                f"""
                SELECT la.entity_id, la.entity_type, la.layering_score,
                       la.confidence_score, la.methods_json, la.reasons_json,
                       la.supporting_tx_hashes_json, la.evidence_ids_json,
                       la.first_seen_at, la.last_seen_at, la.run_id
                FROM layering_alerts la
                JOIN layering_entity_addresses lea
                  ON lea.run_id = la.run_id AND lea.entity_id = la.entity_id
                WHERE lea.address IN ({placeholders})
                ORDER BY la.layering_score DESC
                LIMIT 1
                """,
                tuple(addresses),
            )
        if not row:
            return None

        # Fetch evidence records
        evidence = await fetch_all(
            """
            SELECT evidence_id, detector_type, evidence_type, title,
                   summary_text, entity_ids_json, tx_hashes_json, path_json,
                   metrics_json, first_seen_at, last_seen_at
            FROM layering_evidence
            WHERE run_id = %s AND entity_id = %s
            ORDER BY detector_type, evidence_id
            LIMIT 30
            """,
            (row["run_id"], row["entity_id"]),
        )

        return {
            "stage": "layering",
            "entity_id": row["entity_id"],
            "entity_type": row.get("entity_type", "address"),
            "layering_score": float(row.get("layering_score") or 0),
            "confidence_score": float(row.get("confidence_score") or 0),
            "methods": _decode_json(row.get("methods_json"), []),
            "reasons": _decode_json(row.get("reasons_json"), []),
            "supporting_tx_hashes": _decode_json(row.get("supporting_tx_hashes_json"), []),
            "first_seen_at": _fmt(row.get("first_seen_at")),
            "last_seen_at": _fmt(row.get("last_seen_at")),
            "evidence": [
                {
                    "evidence_id": e.get("evidence_id"),
                    "detector_type": e.get("detector_type"),
                    "evidence_type": e.get("evidence_type"),
                    "title": e.get("title"),
                    "summary": e.get("summary_text"),
                    "entity_ids": _decode_json(e.get("entity_ids_json"), []),
                    "tx_hashes": _decode_json(e.get("tx_hashes_json"), []),
                    "path": _decode_json(e.get("path_json"), []),
                    "metrics": _decode_json(e.get("metrics_json"), {}),
                }
                for e in (evidence or [])
            ],
        }
    except ProgrammingError:
        return None


async def _fetch_integration_stage(entity_id: str, addresses: list[str]) -> dict | None:
    """Fetch the latest integration alert for this entity or any of its addresses."""
    try:
        row = await fetch_one(
            """
            SELECT entity_id, entity_type, integration_score, confidence_score,
                   signals_fired_json, signal_scores_json, reasons_json,
                   supporting_tx_hashes_json, layering_score, placement_score,
                   metrics_json, first_seen_at, last_seen_at
            FROM integration_alerts
            WHERE entity_id = %s
            ORDER BY integration_score DESC
            LIMIT 1
            """,
            (entity_id,),
        )
        if not row:
            # Try any of the addresses
            for addr in addresses:
                row = await fetch_one(
                    """
                    SELECT entity_id, entity_type, integration_score, confidence_score,
                           signals_fired_json, signal_scores_json, reasons_json,
                           supporting_tx_hashes_json, layering_score, placement_score,
                           metrics_json, first_seen_at, last_seen_at
                    FROM integration_alerts
                    WHERE entity_id = %s
                    ORDER BY integration_score DESC
                    LIMIT 1
                    """,
                    (addr,),
                )
                if row:
                    break
        if not row:
            return None

        return {
            "stage": "integration",
            "entity_id": row["entity_id"],
            "entity_type": row.get("entity_type", "address"),
            "integration_score": float(row.get("integration_score") or 0),
            "confidence_score": float(row.get("confidence_score") or 0),
            "signals_fired": _decode_json(row.get("signals_fired_json"), []),
            "signal_scores": _decode_json(row.get("signal_scores_json"), {}),
            "reasons": _decode_json(row.get("reasons_json"), []),
            "supporting_tx_hashes": _decode_json(row.get("supporting_tx_hashes_json"), []),
            "layering_score": float(row.get("layering_score") or 0),
            "placement_score": float(row.get("placement_score") or 0),
            "metrics": _decode_json(row.get("metrics_json"), {}),
            "first_seen_at": _fmt(row.get("first_seen_at")),
            "last_seen_at": _fmt(row.get("last_seen_at")),
        }
    except ProgrammingError:
        return None


async def _fetch_neo4j_path(entity_id: str, addresses: list[str]) -> list[dict]:
    """
    Query Neo4j for TRANSFER edges involving this entity's addresses.
    Returns a list of {source, target, value_eth, tx_hash} for graph rendering.
    """
    driver = get_driver()
    if not driver:
        return []
    try:
        addr_list = addresses[:20]  # cap to avoid huge queries
        async with driver.session() as session:
            result = await session.run(
                """
                MATCH (s:Address)-[rel:TRANSFER]->(r:Address)
                WHERE s.address IN $addrs OR r.address IN $addrs
                RETURN s.address AS source, r.address AS target,
                       COALESCE(rel.value_eth, rel.amount, 0) AS value_eth,
                       COALESCE(rel.tx_hash, rel.hash, '') AS tx_hash,
                       rel.block_number AS block_number
                LIMIT 200
                """,
                addrs=addr_list,
            )
            edges = []
            async for r in result:
                edges.append({
                    "source": r["source"],
                    "target": r["target"],
                    "value_eth": float(r["value_eth"] or 0),
                    "tx_hash": r["tx_hash"] or "",
                    "block_number": r["block_number"],
                })
            return edges
    except Exception as exc:
        logger.warning("Neo4j path query failed: %s", exc)
        return []


# ── Route ─────────────────────────────────────────────────────────────────────

@router.get("/{entity_id}")
async def get_chain_of_custody(entity_id: str):
    """
    Return the full chain of custody for an entity:
    Placement origin → Layering hops → Integration exit.

    Also returns Neo4j graph edges for ReactFlow rendering.
    """
    _require_mysql()

    # Resolve all addresses for this entity
    addresses = await _resolve_addresses(entity_id)

    # Fetch all three stages in parallel
    import asyncio
    placement, layering, integration, neo4j_edges = await asyncio.gather(
        _fetch_placement_stage(entity_id, addresses),
        _fetch_layering_stage(entity_id, addresses),
        _fetch_integration_stage(entity_id, addresses),
        _fetch_neo4j_path(entity_id, addresses),
    )

    # Collect all tx hashes across all stages
    all_tx_hashes: set[str] = set()
    for stage in [placement, layering, integration]:
        if stage:
            all_tx_hashes.update(stage.get("supporting_tx_hashes") or [])

    # Determine which stages are present
    stages_found = [s["stage"] for s in [placement, layering, integration] if s]

    # Compute overall risk — highest score across all stages
    scores = []
    if placement:
        scores.append(placement["placement_score"])
    if layering:
        scores.append(layering["layering_score"])
    if integration:
        scores.append(integration["integration_score"])
    overall_risk = max(scores) if scores else 0.0

    return {
        "entity_id": entity_id,
        "addresses": addresses,
        "stages_found": stages_found,
        "overall_risk": round(overall_risk, 4),
        "all_tx_hashes": sorted(all_tx_hashes)[:50],
        "placement": placement,
        "layering": layering,
        "integration": integration,
        "neo4j_edges": neo4j_edges,
    }


@router.post("/{entity_id}/feedback")
async def post_integration_feedback(entity_id: str, payload: dict):
    """
    Improvement 1: Feedback loop — Integration finding triggers re-evaluation of Placement.

    When Integration confirms a high-confidence exit point, this endpoint:
    1. Records the feedback in placement_labels
    2. Returns the updated placement score with integration boost applied
    """
    _require_mysql()

    integration_score = float(payload.get("integration_score") or 0)
    signals_fired = payload.get("signals_fired") or []
    feedback_type = payload.get("feedback_type", "confirmed_exit_path")

    if integration_score < 0.60:
        return {"status": "skipped", "reason": "integration_score below feedback threshold (0.60)"}

    # Find the placement entity for this address
    placement_row = await fetch_one(
        """
        SELECT pd.run_id, pd.entity_id, pd.placement_score
        FROM placement_detections pd
        JOIN placement_entity_addresses pea
          ON pea.run_id = pd.run_id AND pea.entity_id = pd.entity_id
        WHERE pea.address = %s OR pd.entity_id = %s
        ORDER BY pd.placement_score DESC
        LIMIT 1
        """,
        (entity_id, entity_id),
    )

    if not placement_row:
        return {"status": "no_placement_found", "entity_id": entity_id}

    # Compute boosted placement score
    original_score = float(placement_row.get("placement_score") or 0)
    boost = min(0.15, integration_score * 0.15)  # max 15% boost
    boosted_score = min(1.0, original_score + boost)

    # Write feedback label to placement_labels
    try:
        await fetch_all(
            """
            INSERT INTO placement_labels
                (run_id, entity_id, entity_type, label, label_source, confidence_score, explanation)
            VALUES (%s, %s, 'address', %s, 'integration_feedback', %s, %s)
            ON DUPLICATE KEY UPDATE
                confidence_score = VALUES(confidence_score),
                explanation = VALUES(explanation)
            """,
            (
                placement_row["run_id"],
                placement_row["entity_id"],
                feedback_type,
                round(boosted_score, 4),
                f"Integration confirmed exit (score={integration_score:.2f}, signals={','.join(signals_fired)}). "
                f"Placement score boosted from {original_score:.2f} to {boosted_score:.2f}.",
            ),
        )
    except Exception as exc:
        logger.warning("Feedback label write failed: %s", exc)

    return {
        "status": "feedback_applied",
        "entity_id": entity_id,
        "placement_entity_id": placement_row["entity_id"],
        "original_placement_score": round(original_score, 4),
        "boosted_placement_score": round(boosted_score, 4),
        "boost_applied": round(boost, 4),
        "feedback_type": feedback_type,
        "integration_signals": signals_fired,
    }
