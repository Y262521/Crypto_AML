"""
Cluster API routes.

Reads pre-computed address clusters from MongoDB (written by the AML
clustering engine) and exposes them to the React frontend.
"""

from fastapi import APIRouter, HTTPException
from db.mongo import get_db

router = APIRouter()


@router.get("/")
async def get_clusters():
    """Return all address clusters sorted by risk score descending."""
    db = get_db()
    try:
        docs = await db.address_clusters.find(
            {}, {"_id": 0}
        ).sort("risk_score", -1).limit(200).to_list(200)
        return docs
    except Exception as e:
        print(f"Error in get_clusters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_clusters_summary():
    """Return aggregate stats about the cluster collection."""
    db = get_db()
    try:
        total = await db.address_clusters.count_documents({})
        high   = await db.address_clusters.count_documents({"risk_score": {"$gte": 70}})
        medium = await db.address_clusters.count_documents({"risk_score": {"$gte": 40, "$lt": 70}})
        low    = await db.address_clusters.count_documents({"risk_score": {"$lt": 40}})
        return {
            "total": total,
            "high_risk": high,
            "medium_risk": medium,
            "low_risk": low,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{cluster_id}")
async def get_cluster(cluster_id: str):
    """Return a single cluster by ID."""
    db = get_db()
    try:
        doc = await db.address_clusters.find_one(
            {"cluster_id": cluster_id}, {"_id": 0}
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Cluster not found")
        return doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
