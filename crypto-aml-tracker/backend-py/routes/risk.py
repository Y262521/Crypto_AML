"""
Risk Engine API
===============
GET  /api/risk/entities          → all entities with risk scores
GET  /api/risk/entities/{id}     → single entity risk detail
GET  /api/risk/poi               → all POI entities
POST /api/risk/run               → trigger risk scoring
POST /api/risk/simulate          → simulate risk changes (no DB write)
GET  /api/risk/watchlist/{addr}  → check address against watchlist
POST /api/risk/mock-data         → inject mock POI entities (dev only, in-memory)
DELETE /api/risk/mock-data       → remove mock POI entities
GET  /api/risk/mock-status       → check whether mock data is active
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel
from db.mysql import fetch_all, fetch_one, get_pool

router = APIRouter()
logger = logging.getLogger(__name__)

_risk_status = {"status": "never", "ran_at": None, "summary": None}
_audit_log: list = []
_entity_graph_cache = {"graph": None, "scores": None, "built_at": None}
_CACHE_TTL_SECONDS = 300  # 5 minutes

# ── Mock POI data store (dev-only, in-memory, never written to DB) ─────────────
_mock_enabled: bool = False

_MOCK_ENTITIES: list[dict] = [
    {
        "entity_id":       "MOCK_POI_001",
        "risk_score":      0.94,
        "risk_breakdown":  {
            "label": 0.95, "behavior": 0.88, "propagation": 0.80,
            "temporal": 0.65, "exposure": 0.75, "integration": 0.90,
        },
        "risk_version":    "mock-v3.0",
        "last_risk_update": datetime.utcnow().isoformat(),
        "is_poi":          True,
        "poi_reason":      "Multi-factor POI: label=0.95, integration=0.90, behavior=0.88",
        "total_balance":   120.5,
        "risk_level":      "critical",
        "label_status":    "sanctioned",
        "full_name":       "Mock Sanctioned Mixer",
        "entity_type":     "mixer",
        "list_category":   "sanction",
        "country":         "Unknown",
        "display_name":    "Mock Sanctioned Mixer",
        "addresses":       [
            "0xdead000000000000000000000000000000000001",
            "0xdead000000000000000000000000000000000002",
            "0xdead000000000000000000000000000000000003",
        ],
        "_is_mock": True,
    },
    {
        "entity_id":       "MOCK_POI_002",
        "risk_score":      0.88,
        "risk_breakdown":  {
            "label": 0.80, "behavior": 0.85, "propagation": 0.70,
            "temporal": 0.60, "exposure": 0.65, "integration": 0.82,
        },
        "risk_version":    "mock-v3.0",
        "last_risk_update": datetime.utcnow().isoformat(),
        "is_poi":          True,
        "poi_reason":      "Multi-factor POI: behavior=0.85, integration=0.82, label=0.80",
        "total_balance":   45.2,
        "risk_level":      "critical",
        "label_status":    "scam",
        "full_name":       "Mock Scam Cluster",
        "entity_type":     "cluster",
        "list_category":   "watchlist",
        "country":         "Unknown",
        "display_name":    "Mock Scam Cluster",
        "addresses":       [
            "0xbad0000000000000000000000000000000000001",
            "0xbad0000000000000000000000000000000000002",
        ],
        "_is_mock": True,
    },
    {
        "entity_id":       "MOCK_POI_003",
        "risk_score":      0.91,
        "risk_breakdown":  {
            "label": 0.88, "behavior": 0.82, "propagation": 0.88,
            "temporal": 0.72, "exposure": 0.78, "integration": 0.85,
        },
        "risk_version":    "mock-v3.0",
        "last_risk_update": datetime.utcnow().isoformat(),
        "is_poi":          True,
        "poi_reason":      "Multi-factor POI: propagation=0.88, integration=0.85, label=0.88",
        "total_balance":   78.9,
        "risk_level":      "critical",
        "label_status":    "darknet",
        "full_name":       "Mock Darknet Exchange",
        "entity_type":     "exchange",
        "list_category":   "sanction",
        "country":         "Unknown",
        "display_name":    "Mock Darknet Exchange",
        "addresses":       [
            "0xcafe000000000000000000000000000000000001",
            "0xcafe000000000000000000000000000000000002",
            "0xcafe000000000000000000000000000000000003",
            "0xcafe000000000000000000000000000000000004",
        ],
        "_is_mock": True,
    },
]

# Mock POI alert (optional transaction alert flow)
_MOCK_ALERT = {
    "id":              "MOCK_ALERT_001",
    "tx_hash":         "0xmocktx0000000000000000000000000000000000000000000000000000000001",
    "entity_id":       "MOCK_POI_001",
    "matched_address": "0xdead000000000000000000000000000000000001",
    "risk_score":      0.94,
    "alert_type":      "poi_transaction",
    "created_at":      datetime.utcnow().isoformat(),
    "_is_mock":        True,
}


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


def _decode_json(val: Any, default):
    if not val:
        return default
    if isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(val)
    except Exception:
        return default


def _fmt(val: Any) -> Any:
    if isinstance(val, datetime):
        return val.isoformat()
    return val


def _require_mysql():
    if not get_pool():
        raise HTTPException(status_code=503, detail="MySQL not available")


# ── Audit logging ─────────────────────────────────────────────────────────────

def _audit(entity_id: str, action: str, changes: dict, user_id: str = "analyst"):
    entry = {
        "user_id":   user_id,
        "entity_id": entity_id,
        "action":    action,
        "changes":   changes,
        "timestamp": datetime.utcnow().isoformat(),
    }
    _audit_log.append(entry)
    logger.info("AUDIT: %s", entry)
    return entry


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/entities")
async def get_risk_entities(
    min_risk: float = Query(0.0, ge=0.0, le=1.0),
    poi_only: bool  = Query(False),
    limit: int      = Query(300, ge=1, le=1000),
):
    _require_mysql()
    try:
        where = "WHERE 1=1"
        params = []
        if min_risk > 0:
            where += " AND wc.risk_score >= %s"
            params.append(min_risk)
        if poi_only:
            where += " AND wc.is_poi = 1"
        params.append(limit)

        rows = await fetch_all(f"""
            SELECT
                wc.id            AS entity_id,
                COALESCE(wc.risk_score, 0)    AS risk_score,
                wc.risk_breakdown,
                wc.risk_version,
                wc.last_risk_update,
                COALESCE(wc.is_poi, 0)        AS is_poi,
                wc.poi_reason,
                wc.total_balance,
                wc.risk_level,
                wc.label_status,
                ol.full_name,
                ol.entity_type,
                ol.list_category,
                ol.country
            FROM wallet_clusters wc
            LEFT JOIN owner_list ol ON wc.owner_id = ol.id
            {where}
            ORDER BY wc.risk_score DESC, wc.total_balance DESC
            LIMIT %s
        """, tuple(params))

        result = []
        for row in rows:
            r = dict(row)
            r["risk_breakdown"]   = _decode_json(r.get("risk_breakdown"), {})
            r["last_risk_update"] = _fmt(r.get("last_risk_update"))
            r["risk_score"]       = float(r.get("risk_score") or 0)
            r["is_poi"]           = bool(r.get("is_poi"))
            r["display_name"]     = r.get("full_name") or f"Unlabeled Cluster [{r['entity_id'][:12]}]"

            # Addresses
            addrs = await fetch_all(
                "SELECT address FROM addresses WHERE cluster_id = %s LIMIT 20",
                (r["entity_id"],)
            )
            r["addresses"] = [a["address"] for a in addrs]
            result.append(r)

        # Merge mock entities when mock mode is active
        if _mock_enabled:
            real_ids = {r["entity_id"] for r in result}
            for mock in _MOCK_ENTITIES:
                if mock["entity_id"] in real_ids:
                    continue  # don't duplicate if somehow already present
                if poi_only and not mock["is_poi"]:
                    continue
                if min_risk > 0 and mock["risk_score"] < min_risk:
                    continue
                result.append(dict(mock))
            # Re-sort by risk_score descending after merge
            result.sort(key=lambda x: float(x.get("risk_score") or 0), reverse=True)

        return result
    except Exception as e:
        logger.error("get_risk_entities error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/poi")
async def get_poi_entities(limit: int = Query(100, ge=1, le=500)):
    _require_mysql()
    return await get_risk_entities(min_risk=0.0, poi_only=True, limit=limit)


@router.get("/entities/{entity_id}")
async def get_risk_entity(entity_id: str):
    # Serve mock entity directly without hitting DB
    if _mock_enabled:
        for mock in _MOCK_ENTITIES:
            if mock["entity_id"] == entity_id:
                return dict(mock)

    _require_mysql()
    try:
        row = await fetch_one("""
            SELECT wc.id AS entity_id,
                   COALESCE(wc.risk_score, 0)  AS risk_score,
                   wc.risk_breakdown,
                   wc.risk_version,
                   wc.last_risk_update,
                   COALESCE(wc.is_poi, 0)      AS is_poi,
                   wc.poi_reason,
                   wc.total_balance,
                   wc.risk_level,
                   wc.label_status,
                   ol.full_name, ol.entity_type, ol.list_category, ol.country
            FROM wallet_clusters wc
            LEFT JOIN owner_list ol ON wc.owner_id = ol.id
            WHERE wc.id = %s
        """, (entity_id,))
        if not row:
            raise HTTPException(status_code=404, detail="Entity not found")

        r = dict(row)
        r["risk_breakdown"]   = _decode_json(r.get("risk_breakdown"), {})
        r["last_risk_update"] = _fmt(r.get("last_risk_update"))
        r["risk_score"]       = float(r.get("risk_score") or 0)
        r["is_poi"]           = bool(r.get("is_poi"))
        r["display_name"]     = r.get("full_name") or f"Unlabeled Cluster [{entity_id[:12]}]"

        addrs = await fetch_all(
            "SELECT address FROM addresses WHERE cluster_id = %s", (entity_id,)
        )
        r["addresses"] = [a["address"] for a in addrs]
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_risk_status():
    return _risk_status


def _run_risk_engine():
    global _risk_status
    _risk_status["status"] = "running"
    _risk_status["ran_at"] = datetime.utcnow().isoformat()
    try:
        import pymysql, pymysql.cursors
        cfg  = _load_aml_config()
        conn = pymysql.connect(
            host=cfg.mysql_host, port=cfg.mysql_port,
            user=cfg.mysql_user, password=cfg.mysql_password,
            database=cfg.mysql_db, charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor, autocommit=False,
        )
        from aml_pipeline.risk.engine import RiskEngine
        from aml_pipeline.risk.watchlist import sync_watchlist

        engine  = RiskEngine(conn)
        summary = engine.run()
        sync_watchlist(conn)
        conn.close()

        _risk_status["status"]  = "success"
        _risk_status["summary"] = summary
        # Invalidate graph cache so next connected query rebuilds
        _entity_graph_cache["graph"]    = None
        _entity_graph_cache["scores"]   = None
        _entity_graph_cache["built_at"] = None
    except Exception as e:
        _risk_status["status"]  = "failed"
        _risk_status["summary"] = {"error": str(e)}
        logger.error("Risk engine failed: %s", e)


@router.post("/run")
async def run_risk_engine(background_tasks: BackgroundTasks):
    if _risk_status["status"] == "running":
        raise HTTPException(status_code=409, detail="Risk engine already running")
    background_tasks.add_task(_run_risk_engine)
    return {"message": "Risk scoring started"}


# ── Simulation ────────────────────────────────────────────────────────────────

class SimulateRequest(BaseModel):
    entity_id: str
    override: dict
    user_id: Optional[str] = "analyst"


@router.post("/simulate")
async def simulate_risk(req: SimulateRequest):
    # Support simulation against mock entities without DB lookup
    if _mock_enabled:
        for mock in _MOCK_ENTITIES:
            if mock["entity_id"] == req.entity_id:
                current_score     = float(mock["risk_score"])
                current_breakdown = dict(mock["risk_breakdown"])
                try:
                    from aml_pipeline.risk.engine import simulate_risk as _simulate
                    result = _simulate(req.entity_id, current_breakdown, req.override)
                except Exception:
                    # Fallback: simple in-memory simulation when risk engine unavailable
                    result = _simple_simulate(current_score, current_breakdown, req.override)
                result["current_risk_score"] = round(current_score, 4)
                result["difference"]         = round(result["new_risk_score"] - current_score, 4)
                _audit(req.entity_id, "simulate_risk", {
                    "override": req.override,
                    "current":  current_score,
                    "simulated": result["new_risk_score"],
                    "mock": True,
                }, req.user_id)
                return result

    _require_mysql()
    try:
        row = await fetch_one(
            "SELECT risk_score, risk_breakdown FROM wallet_clusters WHERE id = %s",
            (req.entity_id,)
        )
        if not row:
            raise HTTPException(status_code=404, detail="Entity not found")

        current_score     = float(row.get("risk_score") or 0)
        current_breakdown = _decode_json(row.get("risk_breakdown"), {})

        try:
            from aml_pipeline.risk.engine import simulate_risk as _simulate
            result = _simulate(req.entity_id, current_breakdown, req.override)
        except Exception:
            result = _simple_simulate(current_score, current_breakdown, req.override)

        result["current_risk_score"] = round(current_score, 4)
        result["difference"]         = round(result["new_risk_score"] - current_score, 4)

        _audit(req.entity_id, "simulate_risk", {
            "override": req.override,
            "current":  current_score,
            "simulated": result["new_risk_score"],
        }, req.user_id)

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit")
async def get_audit_log(limit: int = Query(50, ge=1, le=500)):
    return _audit_log[-limit:]


@router.get("/watchlist/{address}")
async def check_watchlist(address: str):
    try:
        from aml_pipeline.risk.watchlist import check_watchlist as _check
        result = _check(address)
        return {"address": address, "on_watchlist": result is not None, "info": result}
    except Exception as e:
        return {"address": address, "on_watchlist": False, "error": str(e)}


@router.get("/entities/{entity_id}/connected")
async def get_connected_risky(entity_id: str, top_n: int = Query(5, ge=1, le=20)):
    """Get top connected risky entities — uses cached graph when available."""
    _require_mysql()
    try:
        import pymysql, pymysql.cursors
        from datetime import datetime as _dt
        cfg  = _load_aml_config()

        # Use cached graph if fresh
        now = _dt.utcnow().timestamp()
        cache = _entity_graph_cache
        if (cache["graph"] is not None and cache["built_at"] is not None
                and now - cache["built_at"] < _CACHE_TTL_SECONDS):
            graph  = cache["graph"]
            scores = cache["scores"] or {}
        else:
            conn = pymysql.connect(
                host=cfg.mysql_host, port=cfg.mysql_port,
                user=cfg.mysql_user, password=cfg.mysql_password,
                database=cfg.mysql_db, charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor, autocommit=False,
            )
            from aml_pipeline.risk.engine import EntityGraph, RiskEngine
            graph = EntityGraph()
            graph.build(conn)
            # Load current risk scores
            with conn.cursor() as cur:
                cur.execute("SELECT id, COALESCE(risk_score,0) AS rs FROM wallet_clusters")
                scores = {r["id"]: float(r["rs"]) for r in cur.fetchall()}
            conn.close()
            cache["graph"]    = graph
            cache["scores"]   = scores
            cache["built_at"] = now

        return graph.connected_risky(entity_id, scores, top_n)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/poi-alerts")
async def get_poi_alerts(limit: int = Query(50, ge=1, le=500)):
    """Get recent POI transaction alerts."""
    _require_mysql()
    try:
        rows = await fetch_all("""
            SELECT id, tx_hash, entity_id, matched_address, risk_score, alert_type, created_at
            FROM poi_alerts
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))
        result = [dict(r) | {"created_at": _fmt(r.get("created_at"))} for r in rows]
    except Exception:
        result = []

    # Prepend mock alert when mock mode is active
    if _mock_enabled:
        result = [dict(_MOCK_ALERT)] + result

    return result


# ── Simple in-memory simulation fallback ─────────────────────────────────────

def _simple_simulate(
    current_score: float,
    breakdown: dict,
    override: dict,
) -> dict:
    """
    Lightweight in-memory simulation matching the v3 engine formula.
    Used when the AML risk engine Python module is unavailable.
    Does NOT write to the database.

    Formula: 0.25*label + 0.20*behavior + 0.15*propagation
           + 0.10*temporal + 0.10*exposure + 0.20*integration
    """
    import math

    WEIGHTS = {
        "label": 0.25, "behavior": 0.20, "propagation": 0.15,
        "temporal": 0.10, "exposure": 0.10, "integration": 0.20,
    }
    LABEL_BOOST = {
        "sanctioned": 1.00, "sanction": 1.00, "scam": 0.95, "fraud": 0.92,
        "mixer": 0.90, "mixing": 0.90, "darknet": 0.88, "ransomware": 0.88,
        "hack": 0.82, "exploit": 0.82, "high_risk": 0.75,
        "watchlist": 0.55, "exchange": 0.15,
    }
    BEHAVIOR_ADD = {
        "loop_detection": 0.40, "coordinated_cashout": 0.40,
        "mixing_interaction": 0.35, "shell_wallet_network": 0.35,
        "bridge_hopping": 0.30, "peeling_chain": 0.30,
        "smurfing": 0.25, "structuring": 0.25,
        "high_depth_transaction_chaining": 0.25,
        "micro_funding": 0.15,
    }
    INTEGRATION_ADD = {
        "terminal_node": 0.30, "convergence": 0.25,
        "value_reaggregation": 0.20, "dormancy": 0.15,
        "asset_transformation": 0.10,
    }

    new_bd = dict(breakdown)

    # Label override
    if "add_label" in override and override["add_label"]:
        new_bd["label"] = max(new_bd.get("label", 0), LABEL_BOOST.get(override["add_label"], 0.70))
    if override.get("remove_label"):
        new_bd["label"] = 0.0

    # Behavior override — exponential normalization
    if "toggle_behavior" in override and override["toggle_behavior"]:
        bw = BEHAVIOR_ADD.get(override["toggle_behavior"], 0.15)
        existing = new_bd.get("behavior", 0.0)
        current_sum = -math.log(max(1.0 - existing, 1e-9)) if existing < 1.0 else 3.0
        new_bd["behavior"] = min(1.0, 1.0 - math.exp(-(current_sum + bw)))

    if "weight_behavior" in override:
        new_bd["behavior"] = min(1.0, float(override["weight_behavior"]))

    # Integration signal override
    if "add_integration" in override and override["add_integration"]:
        sig_w = INTEGRATION_ADD.get(override["add_integration"], 0.10)
        new_bd["integration"] = min(1.0, new_bd.get("integration", 0.0) + sig_w)

    new_score = sum(new_bd.get(k, 0) * w for k, w in WEIGHTS.items())
    new_score = round(min(1.0, max(0.0, new_score)), 4)

    changed = {
        k: round(new_bd.get(k, 0) - breakdown.get(k, 0), 4)
        for k in WEIGHTS
        if abs(new_bd.get(k, 0) - breakdown.get(k, 0)) > 0.001
    }

    strong_factors = sum(1 for v in new_bd.values() if v >= 0.4)
    would_be_poi = new_score >= 0.80 and strong_factors >= 2

    return {
        "new_risk_score":   new_score,
        "new_breakdown":    new_bd,
        "changed_factors":  changed,
        "would_be_poi":     would_be_poi,
        "strong_factors":   strong_factors,
    }


# ── Mock data endpoints (dev-only) ────────────────────────────────────────────

@router.get("/mock-status")
async def get_mock_status():
    """Return whether mock POI data is currently active."""
    return {
        "mock_enabled": _mock_enabled,
        "mock_entity_count": len(_MOCK_ENTITIES) if _mock_enabled else 0,
        "mock_entity_ids": [m["entity_id"] for m in _MOCK_ENTITIES] if _mock_enabled else [],
    }


@router.post("/mock-data")
async def enable_mock_data():
    """
    Enable mock POI entities for dev/testing.
    Entities are served in-memory — nothing is written to the database.
    """
    global _mock_enabled
    _mock_enabled = True
    logger.info("Mock POI data ENABLED — %d entities injected in-memory", len(_MOCK_ENTITIES))
    _audit("system", "mock_data_enabled", {"entity_count": len(_MOCK_ENTITIES)})
    return {
        "message": f"Mock POI data enabled — {len(_MOCK_ENTITIES)} entities active",
        "mock_enabled": True,
        "entities": [
            {
                "entity_id":    m["entity_id"],
                "display_name": m["display_name"],
                "risk_score":   m["risk_score"],
                "is_poi":       m["is_poi"],
                "label":        m["label_status"],
            }
            for m in _MOCK_ENTITIES
        ],
    }


@router.delete("/mock-data")
async def disable_mock_data():
    """
    Disable mock POI entities.
    Reverts to real data only. No database changes are made.
    """
    global _mock_enabled
    _mock_enabled = False
    logger.info("Mock POI data DISABLED")
    _audit("system", "mock_data_disabled", {})
    return {"message": "Mock POI data disabled — real data only", "mock_enabled": False}
