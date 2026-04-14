"""
Cluster API routes.

Clusters are stored in MySQL (wallet_clusters + owners + addresses + evidence).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

from fastapi import APIRouter, HTTPException, Query

from db.mysql import fetch_all, fetch_one, get_pool
from settings import get_env

router = APIRouter()
MIN_CLUSTER_SIZE = int(get_env("CLUSTER_MIN_CLUSTER_SIZE", default="2") or "2")


def _require_mysql():
    if get_pool() is None:
        raise HTTPException(
            status_code=503,
            detail="MySQL is not connected. Cluster data is unavailable.",
        )


def _owner_payload(row: dict) -> dict:
    return {
        "full_name": row.get("full_name"),
        "country": row.get("country"),
        "city": row.get("city"),
        "specifics": row.get("specifics"),
        "street_address": row.get("street_address"),
        "locality": row.get("locality"),
        "administrative_area": row.get("administrative_area"),
        "postal_code": row.get("postal_code"),
    }


@router.get("/")
async def get_clusters(limit: int = Query(500, ge=1, le=5000)):
    _require_mysql()

    clusters = await fetch_all(
        """
        SELECT c.id,
               COALESCE(m.member_count, 0) AS cluster_size,
               c.total_balance,
               c.risk_level,
               o.full_name, o.country, o.city, o.specifics, o.street_address, o.locality, o.administrative_area, o.postal_code
        FROM wallet_clusters c
        LEFT JOIN (
            SELECT cluster_id, COUNT(*) AS member_count
            FROM addresses
            WHERE cluster_id IS NOT NULL
            GROUP BY cluster_id
        ) m ON m.cluster_id = c.id
        LEFT JOIN owners o ON c.owner_id = o.id
        WHERE COALESCE(m.member_count, 0) >= %s
        ORDER BY COALESCE(m.member_count, 0) DESC, c.total_balance DESC
        LIMIT %s
        """,
        (MIN_CLUSTER_SIZE, limit),
    )
    if not clusters:
        return []

    cluster_ids = [row["id"] for row in clusters]
    placeholders = ", ".join(["%s"] * len(cluster_ids))

    addresses_rows = await fetch_all(
        f"SELECT cluster_id, address, total_in, total_out FROM addresses WHERE cluster_id IN ({placeholders}) ORDER BY address",
        tuple(cluster_ids),
    )
    addresses_map: dict[str, list] = {}
    for row in addresses_rows:
        addresses_map.setdefault(row["cluster_id"], []).append({
            "address": row.get("address"),
            "total_in": float(row.get("total_in") or 0.0),
            "total_out": float(row.get("total_out") or 0.0),
        })

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
        evidence_map.setdefault(row["cluster_id"], []).append({
            "heuristic_name": row.get("heuristic_name"),
            "evidence_text": row.get("evidence_text"),
            "confidence": float(row.get("confidence") or 0.0),
        })

    payload = []
    for row in clusters:
        cid = row["id"]
        activity = activity_map.get(cid, {})
        cluster_addresses = addresses_map.get(cid, [])
        sample_addresses = [addr["address"] for addr in cluster_addresses[:3]]
        payload.append({
            "cluster_id": cid,
            "cluster_size": int(activity.get("address_count") or row.get("cluster_size") or 0),
            "total_balance": float(row.get("total_balance") or 0.0),
            "owner": _owner_payload(row),
            "location": ", ".join(
                [
                    part for part in [
                        row.get("country"),
                        row.get("city"),
                        row.get("sub_city"),
                        row.get("kebele"),
                    ] if part
                ]
            ),
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
        })

    return payload


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

    return {
        "total": int(total_row.get("total") or 0),
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
        aml_root = Path(__file__).resolve().parents[3] / "AML"
        aml_src = str(aml_root / "src")
        if aml_src not in sys.path:
            sys.path.insert(0, aml_src)
        from dotenv import load_dotenv
        load_dotenv(aml_root / ".env")

        from aml_pipeline.config import load_config
        from aml_pipeline.clustering.engine import ClusteringEngine

        cfg = load_config()
        engine = ClusteringEngine(cfg=cfg)
        results = await asyncio.to_thread(
            engine.run,
            persist=True,
            min_cluster_size=cfg.clustering_min_cluster_size,
        )
        return {"status": "ok", "clusters_found": len(results)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Clustering failed: {exc}") from exc


@router.get("/{cluster_id}")
async def get_cluster(cluster_id: str):
    _require_mysql()
    row = await fetch_one(
        """
        SELECT c.id,
               COALESCE(m.member_count, 0) AS cluster_size,
               c.total_balance,
               c.risk_level,
               o.full_name, o.country, o.city, o.specifics, o.street_address, o.locality, o.administrative_area, o.postal_code
        FROM wallet_clusters c
        LEFT JOIN (
            SELECT cluster_id, COUNT(*) AS member_count
            FROM addresses
            WHERE cluster_id IS NOT NULL
            GROUP BY cluster_id
        ) m ON m.cluster_id = c.id
        LEFT JOIN owners o ON c.owner_id = o.id
        WHERE c.id = %s
        """,
        (cluster_id,),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Cluster not found")
    if int(row.get("cluster_size") or 0) < MIN_CLUSTER_SIZE:
        raise HTTPException(status_code=404, detail="Cluster not found")

    addresses = await fetch_all(
        "SELECT address FROM addresses WHERE cluster_id = %s ORDER BY address",
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
        "owner": _owner_payload(row),
        "location": ", ".join(
            [part for part in [
                row.get("specifics"),
                row.get("street_address"),
                row.get("locality"),
                row.get("city"),
                row.get("administrative_area"),
                row.get("postal_code"),
                row.get("country")
            ] if part]
        ),
        "addresses": [a.get("address") for a in addresses],
        "activity": {
            "total_in": float(activity.get("total_in") or 0.0),
            "total_out": float(activity.get("total_out") or 0.0),
            "total_tx_count": int(activity.get("total_tx_count") or 0),
            "address_count": int(activity.get("address_count") or 0),
        },
        "evidence": [
            {
                "heuristic_name": e.get("heuristic_name"),
                "evidence_text": e.get("evidence_text"),
                "confidence": float(e.get("confidence") or 0.0),
            }
            for e in evidence
        ],
    }
