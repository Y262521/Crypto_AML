"""
Cluster API routes.

Clusters are stored in MySQL (wallet_clusters + owner_list + addresses + evidence).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from db.mysql import fetch_all, fetch_one, get_pool
from settings import get_env

router = APIRouter()
MIN_CLUSTER_SIZE = int(get_env("CLUSTER_MIN_CLUSTER_SIZE", default="2") or "2")

_OWNER_SELECT = """
       c.label_status,
       c.matched_owner_address,
       o.id AS owner_registry_id,
       o.full_name,
       o.entity_type,
       o.list_category,
       o.country,
       o.city,
       o.specifics,
       o.street_address,
       o.locality,
       o.administrative_area,
       o.postal_code,
       o.source_reference,
       o.notes
"""


class OwnerListCreateRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    entity_type: str = Field(default="individual", max_length=64)
    list_category: str = Field(default="watchlist", max_length=64)
    known_addresses: list[str] = Field(..., min_length=1)
    blockchain_network: str = Field(default="ethereum", max_length=64)
    specifics: str | None = Field(default=None, max_length=255)
    street_address: str | None = Field(default=None, max_length=255)
    locality: str | None = Field(default=None, max_length=128)
    city: str = Field(..., min_length=2, max_length=128)
    administrative_area: str | None = Field(default=None, max_length=128)
    postal_code: str | None = Field(default=None, max_length=32)
    country: str = Field(..., min_length=2, max_length=128)
    source_reference: str | None = Field(default=None, max_length=255)
    notes: str | None = None

    @field_validator("full_name", "city", "country", mode="before")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if not cleaned:
            raise ValueError("This field is required.")
        return cleaned

    @field_validator(
        "entity_type",
        "list_category",
        "blockchain_network",
        "specifics",
        "street_address",
        "locality",
        "administrative_area",
        "postal_code",
        "source_reference",
        "notes",
        mode="before",
    )
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("known_addresses", mode="before")
    @classmethod
    def _normalize_known_addresses(cls, value) -> list[str]:
        if isinstance(value, str):
            raw_items = value.replace(",", "\n").splitlines()
        else:
            raw_items = value or []
        cleaned = [str(item).strip() for item in raw_items if str(item).strip()]
        if not cleaned:
            raise ValueError("At least one blockchain address is required.")
        return cleaned


def _require_mysql():
    if get_pool() is None:
        raise HTTPException(
            status_code=503,
            detail="MySQL is not connected. Cluster data is unavailable.",
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


def _owner_payload(row: dict) -> dict | None:
    if not row.get("full_name"):
        return None
    return {
        "id": row.get("owner_registry_id"),
        "full_name": row.get("full_name"),
        "entity_type": row.get("entity_type"),
        "list_category": row.get("list_category"),
        "country": row.get("country"),
        "city": row.get("city"),
        "specifics": row.get("specifics"),
        "street_address": row.get("street_address"),
        "locality": row.get("locality"),
        "administrative_area": row.get("administrative_area"),
        "postal_code": row.get("postal_code"),
        "source_reference": row.get("source_reference"),
        "notes": row.get("notes"),
    }


def _owner_location(row: dict) -> str:
    parts = [
        row.get("specifics"),
        row.get("street_address"),
        row.get("locality"),
        row.get("city"),
        row.get("administrative_area"),
        row.get("postal_code"),
        row.get("country"),
    ]
    return ", ".join(part for part in parts if part)


async def _fetch_cluster_maps(cluster_ids: list[str]) -> tuple[dict, dict, dict]:
    placeholders = ", ".join(["%s"] * len(cluster_ids))

    addresses_rows = await fetch_all(
        f"""
        SELECT cluster_id, address, total_in, total_out
        FROM addresses
        WHERE cluster_id IN ({placeholders})
        ORDER BY address
        """,
        tuple(cluster_ids),
    )
    addresses_map: dict[str, list] = {}
    for row in addresses_rows:
        addresses_map.setdefault(row["cluster_id"], []).append(
            {
                "address": row.get("address"),
                "total_in": float(row.get("total_in") or 0.0),
                "total_out": float(row.get("total_out") or 0.0),
            }
        )

    activity_rows = await fetch_all(
        f"""
        SELECT cluster_id,
               COUNT(*) AS address_count,
               COALESCE(SUM(total_in), 0) AS total_in,
               COALESCE(SUM(total_out), 0) AS total_out,
               COALESCE(SUM(tx_count), 0) AS total_tx_count
        FROM addresses
        WHERE cluster_id IN ({placeholders})
        GROUP BY cluster_id
        """,
        tuple(cluster_ids),
    )
    activity_map = {row["cluster_id"]: row for row in activity_rows}

    evidence_rows = await fetch_all(
        f"""
        SELECT cluster_id, heuristic_name, evidence_text, confidence
        FROM cluster_evidence
        WHERE cluster_id IN ({placeholders})
        ORDER BY confidence DESC
        """,
        tuple(cluster_ids),
    )
    evidence_map: dict[str, list] = {}
    for row in evidence_rows:
        evidence_map.setdefault(row["cluster_id"], []).append(
            {
                "heuristic_name": row.get("heuristic_name"),
                "evidence_text": row.get("evidence_text"),
                "confidence": float(row.get("confidence") or 0.0),
            }
        )

    return addresses_map, activity_map, evidence_map


def _cluster_payload(
    row: dict,
    *,
    addresses_map: dict[str, list],
    activity_map: dict[str, dict],
    evidence_map: dict[str, list],
) -> dict:
    cid = row["id"]
    activity = activity_map.get(cid, {})
    cluster_addresses = addresses_map.get(cid, [])
    sample_addresses = [addr["address"] for addr in cluster_addresses[:3]]

    return {
        "cluster_id": cid,
        "cluster_size": int(activity.get("address_count") or row.get("cluster_size") or 0),
        "total_balance": float(row.get("total_balance") or 0.0),
        "risk_level": row.get("risk_level") or "normal",
        "label_status": row.get("label_status") or "unlabeled",
        "matched_owner_address": row.get("matched_owner_address"),
        "owner": _owner_payload(row),
        "location": _owner_location(row) or None,
        "addresses": cluster_addresses,
        "activity": {
            "total_in": float(activity.get("total_in") or 0.0),
            "total_out": float(activity.get("total_out") or 0.0),
            "total_tx_count": int(activity.get("total_tx_count") or 0),
            "address_count": int(activity.get("address_count") or 0),
        },
        "evidence": [
            {
                **item,
                "observed_address_count": len(cluster_addresses),
                "observed_address_sample": sample_addresses,
            }
            for item in evidence_map.get(cid, [])
        ],
    }


@router.get("/")
async def get_clusters(limit: int = Query(500, ge=1, le=5000)):
    _require_mysql()

    clusters = await fetch_all(
        f"""
        SELECT c.id,
               COALESCE(m.member_count, 0) AS cluster_size,
               c.total_balance,
               c.risk_level,
               {_OWNER_SELECT}
        FROM wallet_clusters c
        LEFT JOIN (
            SELECT cluster_id, COUNT(*) AS member_count
            FROM addresses
            WHERE cluster_id IS NOT NULL
            GROUP BY cluster_id
        ) m ON m.cluster_id = c.id
        LEFT JOIN owner_list o ON c.owner_id = o.id
        WHERE COALESCE(m.member_count, 0) >= %s
        ORDER BY COALESCE(m.member_count, 0) DESC, c.total_balance DESC
        LIMIT %s
        """,
        (MIN_CLUSTER_SIZE, limit),
    )
    if not clusters:
        return []

    cluster_ids = [row["id"] for row in clusters]
    addresses_map, activity_map, evidence_map = await _fetch_cluster_maps(cluster_ids)

    return [
        _cluster_payload(
            row,
            addresses_map=addresses_map,
            activity_map=activity_map,
            evidence_map=evidence_map,
        )
        for row in clusters
    ]


@router.get("/summary")
async def get_clusters_summary():
    _require_mysql()

    total_row = await fetch_one(
        """
        SELECT COUNT(*) AS total
        FROM (
            SELECT cluster_id
            FROM addresses
            WHERE cluster_id IS NOT NULL
            GROUP BY cluster_id
            HAVING COUNT(*) >= %s
        ) t
        """,
        (MIN_CLUSTER_SIZE,),
    ) or {}
    top_balance = await fetch_all(
        """
        SELECT c.id,
               COUNT(a.address) AS cluster_size,
               c.total_balance
        FROM wallet_clusters c
        JOIN addresses a ON a.cluster_id = c.id
        GROUP BY c.id, c.total_balance
        HAVING COUNT(a.address) >= %s
        ORDER BY c.total_balance DESC, COUNT(a.address) DESC
        LIMIT 5
        """,
        (MIN_CLUSTER_SIZE,),
    )
    top_size = await fetch_all(
        """
        SELECT c.id,
               COUNT(a.address) AS cluster_size,
               c.total_balance
        FROM wallet_clusters c
        JOIN addresses a ON a.cluster_id = c.id
        GROUP BY c.id, c.total_balance
        HAVING COUNT(a.address) >= %s
        ORDER BY COUNT(a.address) DESC, c.total_balance DESC
        LIMIT 5
        """,
        (MIN_CLUSTER_SIZE,),
    )
    status_rows = await fetch_all(
        """
        SELECT c.label_status, COUNT(*) AS total
        FROM wallet_clusters c
        JOIN (
            SELECT cluster_id, COUNT(*) AS member_count
            FROM addresses
            WHERE cluster_id IS NOT NULL
            GROUP BY cluster_id
            HAVING COUNT(*) >= %s
        ) m ON m.cluster_id = c.id
        GROUP BY c.label_status
        """,
        (MIN_CLUSTER_SIZE,),
    )
    status_counts = {row.get("label_status") or "unlabeled": int(row.get("total") or 0) for row in status_rows}

    return {
        "total": int(total_row.get("total") or 0),
        "matched": status_counts.get("matched", 0),
        "unlabeled": status_counts.get("unlabeled", 0),
        "conflict": status_counts.get("conflict", 0),
        "top_by_balance": [
            {
                "cluster_id": row.get("id"),
                "cluster_size": int(row.get("cluster_size") or 0),
                "total_balance": float(row.get("total_balance") or 0.0),
            }
            for row in top_balance
        ],
        "top_by_size": [
            {
                "cluster_id": row.get("id"),
                "cluster_size": int(row.get("cluster_size") or 0),
                "total_balance": float(row.get("total_balance") or 0.0),
            }
            for row in top_size
        ],
    }


@router.post("/run")
async def run_clustering():
    """Manually trigger clustering (hybrid with scheduled runs)."""
    try:
        cfg = _load_aml_config()
        from aml_pipeline.clustering.engine import ClusteringEngine

        engine = ClusteringEngine(cfg=cfg)
        results = await asyncio.to_thread(
            engine.run,
            persist=True,
            min_cluster_size=cfg.clustering_min_cluster_size,
        )
        return {"status": "ok", "clusters_found": len(results)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Clustering failed: {exc}") from exc


@router.post("/owner-list")
async def create_owner_list_record(payload: OwnerListCreateRequest):
    """Insert an owner-list entry and relabel any cluster containing that address."""
    _require_mysql()

    try:
        cfg = _load_aml_config()
        from aml_pipeline.clustering.owner_registry import create_owner_list_entry

        result = await asyncio.to_thread(
            create_owner_list_entry,
            payload.model_dump(),
            cfg=cfg,
        )
        return {"status": "ok", **result}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Owner insert failed: {exc}") from exc


@router.get("/{cluster_id}")
async def get_cluster(cluster_id: str):
    _require_mysql()
    row = await fetch_one(
        f"""
        SELECT c.id,
               COALESCE(m.member_count, 0) AS cluster_size,
               c.total_balance,
               c.risk_level,
               {_OWNER_SELECT}
        FROM wallet_clusters c
        LEFT JOIN (
            SELECT cluster_id, COUNT(*) AS member_count
            FROM addresses
            WHERE cluster_id IS NOT NULL
            GROUP BY cluster_id
        ) m ON m.cluster_id = c.id
        LEFT JOIN owner_list o ON c.owner_id = o.id
        WHERE c.id = %s
        """,
        (cluster_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Cluster not found")
    if int(row.get("cluster_size") or 0) < MIN_CLUSTER_SIZE:
        raise HTTPException(status_code=404, detail="Cluster not found")

    addresses = await fetch_all(
        """
        SELECT address, total_in, total_out
        FROM addresses
        WHERE cluster_id = %s
        ORDER BY address
        """,
        (cluster_id,),
    )
    activity = await fetch_one(
        """
        SELECT COUNT(*) AS address_count,
               COALESCE(SUM(total_in), 0) AS total_in,
               COALESCE(SUM(total_out), 0) AS total_out,
               COALESCE(SUM(tx_count), 0) AS total_tx_count
        FROM addresses
        WHERE cluster_id = %s
        """,
        (cluster_id,),
    ) or {}
    evidence = await fetch_all(
        """
        SELECT heuristic_name, evidence_text, confidence
        FROM cluster_evidence
        WHERE cluster_id = %s
        ORDER BY confidence DESC
        """,
        (cluster_id,),
    )

    return {
        "cluster_id": row.get("id"),
        "cluster_size": len(addresses),
        "total_balance": float(row.get("total_balance") or 0.0),
        "risk_level": row.get("risk_level") or "normal",
        "label_status": row.get("label_status") or "unlabeled",
        "matched_owner_address": row.get("matched_owner_address"),
        "owner": _owner_payload(row),
        "location": _owner_location(row) or None,
        "addresses": [
            {
                "address": addr.get("address"),
                "total_in": float(addr.get("total_in") or 0.0),
                "total_out": float(addr.get("total_out") or 0.0),
            }
            for addr in addresses
        ],
        "activity": {
            "total_in": float(activity.get("total_in") or 0.0),
            "total_out": float(activity.get("total_out") or 0.0),
            "total_tx_count": int(activity.get("total_tx_count") or 0),
            "address_count": int(activity.get("address_count") or 0),
        },
        "evidence": [
            {
                "heuristic_name": item.get("heuristic_name"),
                "evidence_text": item.get("evidence_text"),
                "confidence": float(item.get("confidence") or 0.0),
            }
            for item in evidence
        ],
    }
