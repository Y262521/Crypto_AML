"""
Multi-Factor Risk Engine v2
============================
Real graph-based propagation + validated exposure + POI hysteresis.

risk_score = 0.35*label + 0.25*behavior + 0.20*propagation + 0.10*temporal + 0.10*exposure
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, List, Set, Tuple

logger = logging.getLogger(__name__)

LABEL_WEIGHTS: Dict[str, float] = {
    "sanctioned": 1.0, "sanction": 1.0, "scam": 0.95, "fraud": 0.90,
    "mixer": 0.90, "mixing": 0.90, "darknet": 0.85, "ransomware": 0.85,
    "hack": 0.80, "exploit": 0.80, "high_risk": 0.75, "watchlist": 0.60,
    "exchange": 0.10, "unknown": 0.0,
}

BEHAVIOR_WEIGHTS: Dict[str, float] = {
    "loop_detection": 0.40, "coordinated_cashout": 0.40,
    "peeling_chain": 0.30, "smurfing": 0.25, "structuring": 0.25,
    "bridge_hopping": 0.30, "mixing_interaction": 0.35,
    "shell_wallet_network": 0.35, "high_depth_transaction_chaining": 0.25,
    "micro_funding": 0.15, "immediate_utilization": 0.10, "funneling": 0.10,
}

PROPAGATION_DECAY = {1: 0.6, 2: 0.3, 3: 0.1}
W_LABEL = 0.35; W_BEHAVIOR = 0.25; W_PROPAGATION = 0.20
W_TEMPORAL = 0.10; W_EXPOSURE = 0.10
POI_ENTER = 0.80; POI_EXIT = 0.70
RISK_VERSION = "v2.0"
MIN_EXPOSURE_ETH = 0.01


def _clamp(v) -> float:
    return max(0.0, min(1.0, float(v or 0)))


class EntityGraph:
    """Adjacency map built from transactions. Cached per RiskEngine run."""

    def __init__(self):
        self._adj: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._built = False

    def build(self, conn) -> None:
        if self._built:
            return
        logger.info("EntityGraph: building...")
        with conn.cursor() as cur:
            cur.execute("""
                SELECT a_from.cluster_id AS fe, a_to.cluster_id AS te,
                       SUM(t.value_eth) AS val
                FROM transactions t
                JOIN addresses a_from ON a_from.address = t.from_address
                JOIN addresses a_to   ON a_to.address   = t.to_address
                WHERE a_from.cluster_id IS NOT NULL
                  AND a_to.cluster_id   IS NOT NULL
                  AND a_from.cluster_id != a_to.cluster_id
                GROUP BY a_from.cluster_id, a_to.cluster_id
            """)
            for r in cur.fetchall():
                v = float(r["val"] or 0)
                self._adj[r["fe"]][r["te"]] += v
                self._adj[r["te"]][r["fe"]] += v
        self._built = True
        logger.info("EntityGraph: %d nodes", len(self._adj))

    def propagation_risk(self, eid: str, poi_set: Set[str], cache: Dict[str, float]) -> float:
        if eid in cache:
            return cache[eid]
        if eid in poi_set:
            cache[eid] = 1.0
            return 1.0
        best = 0.0
        visited: Set[str] = {eid}
        q: deque = deque([(eid, 0)])
        while q:
            cur_node, depth = q.popleft()
            if depth >= 3:
                continue
            for nb in self._adj.get(cur_node, {}):
                if nb in visited:
                    continue
                visited.add(nb)
                hop = depth + 1
                if nb in poi_set:
                    best = max(best, PROPAGATION_DECAY.get(hop, 0.0))
                q.append((nb, hop))
        result = _clamp(best)
        cache[eid] = result
        return result

    def connected_risky(self, eid: str, risk_scores: Dict[str, float], top_n: int = 5) -> List[dict]:
        """Return top connected entities sorted by risk score × tx volume."""
        neighbors = self._adj.get(eid, {})
        result = []
        for nb, vol in neighbors.items():
            rs = risk_scores.get(nb, 0.0)
            if rs > 0:
                result.append({"entity_id": nb, "risk_score": round(rs, 4), "tx_volume_eth": round(vol, 4)})
        result.sort(key=lambda x: x["risk_score"] * x["tx_volume_eth"], reverse=True)
        return result[:top_n]


class RiskEngine:
    def __init__(self, conn):
        self._conn  = conn
        self._graph = EntityGraph()

    def run(self) -> dict:
        logger.info("RiskEngine v2: starting...")
        self._ensure_columns()
        self._ensure_poi_alerts_table()

        clusters      = self._load_clusters()
        labels_map    = self._load_labels()
        behaviors_map = self._load_behaviors()
        tx_stats      = self._load_tx_stats()
        exposure_map  = self._load_exposure()
        poi_set       = self._load_existing_poi()

        self._graph.build(self._conn)
        prop_cache: Dict[str, float] = {}
        scored = poi_count = 0
        computed_scores: Dict[str, float] = {}

        with self._conn.cursor() as cur:
            for cluster_id, cluster in clusters.items():
                labels    = labels_map.get(cluster_id, [])
                behaviors = behaviors_map.get(cluster_id, [])
                stats     = tx_stats.get(cluster_id, {})
                exp_tuple = exposure_map.get(cluster_id, (0.0, 0.0))

                prop = self._graph.propagation_risk(cluster_id, poi_set, prop_cache)

                breakdown = {
                    "label":       self._label_score(labels),
                    "behavior":    self._behavior_score(behaviors),
                    "propagation": prop,
                    "temporal":    self._temporal_score(stats),
                    "exposure":    self._exposure_score(exp_tuple),
                }

                risk_score = _clamp(
                    W_LABEL * breakdown["label"]
                    + W_BEHAVIOR * breakdown["behavior"]
                    + W_PROPAGATION * breakdown["propagation"]
                    + W_TEMPORAL * breakdown["temporal"]
                    + W_EXPOSURE * breakdown["exposure"]
                )
                computed_scores[cluster_id] = risk_score

                was_poi = cluster_id in poi_set
                if risk_score >= POI_ENTER:
                    is_poi = 1
                elif risk_score < POI_EXIT:
                    is_poi = 0
                else:
                    is_poi = 1 if was_poi else 0

                strong = sum(1 for v in breakdown.values() if v >= 0.4)
                if is_poi and breakdown["label"] < 0.8 and strong < 2:
                    is_poi = 0

                poi_reason = self._poi_reason(breakdown) if is_poi else None

                cur.execute("""
                    UPDATE wallet_clusters
                    SET risk_score=%s, risk_breakdown=%s, risk_version=%s,
                        last_risk_update=%s, is_poi=%s,
                        poi_reason=CASE WHEN %s IS NOT NULL THEN %s ELSE poi_reason END
                    WHERE id=%s
                """, (
                    round(risk_score, 6),
                    json.dumps({k: round(v, 4) for k, v in breakdown.items()}),
                    RISK_VERSION, datetime.now(timezone.utc), is_poi,
                    poi_reason, poi_reason, cluster_id,
                ))
                scored += 1
                if is_poi:
                    poi_count += 1

        self._conn.commit()
        logger.info("RiskEngine: scored=%d poi=%d", scored, poi_count)
        return {"status": "success", "scored": scored, "poi_count": poi_count,
                "graph_nodes": len(self._graph._adj)}

    def get_connected_risky(self, entity_id: str, top_n: int = 5) -> List[dict]:
        """Get top connected risky entities for the detail panel."""
        with self._conn.cursor() as cur:
            cur.execute("SELECT id, risk_score FROM wallet_clusters WHERE risk_score > 0")
            scores = {r["id"]: float(r["risk_score"] or 0) for r in cur.fetchall()}
        if not self._graph._built:
            self._graph.build(self._conn)
        return self._graph.connected_risky(entity_id, scores, top_n)

    def _ensure_columns(self):
        cols = {
            "risk_score": "DECIMAL(8,6) NOT NULL DEFAULT 0",
            "risk_breakdown": "JSON NULL",
            "risk_version": "VARCHAR(20) NULL",
            "last_risk_update": "DATETIME NULL",
            "is_poi": "TINYINT(1) NOT NULL DEFAULT 0",
            "poi_reason": "TEXT NULL",
        }
        with self._conn.cursor() as cur:
            cur.execute("DESCRIBE wallet_clusters")
            existing = {r["Field"] for r in cur.fetchall()}
            for col, defn in cols.items():
                if col not in existing:
                    cur.execute(f"ALTER TABLE wallet_clusters ADD COLUMN {col} {defn}")
        self._conn.commit()

    def _ensure_poi_alerts_table(self):
        with self._conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS poi_alerts (
                    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
                    tx_hash         VARCHAR(66)  NULL,
                    entity_id       VARCHAR(64)  NULL,
                    matched_address VARCHAR(64)  NULL,
                    risk_score      DECIMAL(6,4) NOT NULL DEFAULT 0,
                    alert_type      VARCHAR(50)  NOT NULL DEFAULT 'watchlist_match',
                    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_pa_entity  (entity_id),
                    INDEX idx_pa_address (matched_address)
                )
            """)
        self._conn.commit()

    def _load_clusters(self) -> Dict[str, dict]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT id, owner_id, total_balance, risk_level FROM wallet_clusters")
            return {r["id"]: r for r in cur.fetchall()}

    def _load_labels(self) -> Dict[str, List[dict]]:
        result: Dict[str, List[dict]] = defaultdict(list)
        with self._conn.cursor() as cur:
            cur.execute("""
                SELECT a.cluster_id, ol.list_category, ol.entity_type
                FROM addresses a
                JOIN owner_list_addresses ola ON ola.address = a.address
                JOIN owner_list ol ON ol.id = ola.owner_list_id
                WHERE a.cluster_id IS NOT NULL
            """)
            for r in cur.fetchall():
                result[r["cluster_id"]].append({
                    "category": (r["list_category"] or "").lower(),
                    "entity_type": (r["entity_type"] or "").lower(),
                })
        return result

    def _load_behaviors(self) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = defaultdict(list)
        with self._conn.cursor() as cur:
            try:
                cur.execute("""
                    SELECT pe.source_cluster_ids_json, pb.behavior_type
                    FROM placement_behaviors pb
                    JOIN placement_entities pe ON pe.entity_id=pb.entity_id AND pe.run_id=pb.run_id
                    WHERE pb.run_id=(SELECT id FROM placement_runs ORDER BY created_at DESC LIMIT 1)
                """)
                for r in cur.fetchall():
                    try:
                        for cid in json.loads(r["source_cluster_ids_json"] or "[]"):
                            result[cid].append(r["behavior_type"])
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                cur.execute("""
                    SELECT le.entity_id, ldh.detector_type
                    FROM layering_detector_hits ldh
                    JOIN layering_entities le ON le.entity_id=ldh.entity_id AND le.run_id=ldh.run_id
                    WHERE ldh.run_id=(SELECT id FROM layering_runs ORDER BY created_at DESC LIMIT 1)
                """)
                for r in cur.fetchall():
                    result[r["entity_id"]].append(r["detector_type"])
            except Exception:
                pass
        return result

    def _load_tx_stats(self) -> Dict[str, dict]:
        result: Dict[str, dict] = {}
        with self._conn.cursor() as cur:
            cur.execute("""
                SELECT a.cluster_id,
                       COUNT(t.tx_hash) AS tx_count,
                       MIN(UNIX_TIMESTAMP(t.timestamp)) AS first_ts,
                       MAX(UNIX_TIMESTAMP(t.timestamp)) AS last_ts,
                       SUM(t.value_eth) AS total_value
                FROM addresses a
                JOIN transactions t ON t.from_address=a.address OR t.to_address=a.address
                WHERE a.cluster_id IS NOT NULL
                GROUP BY a.cluster_id
            """)
            for r in cur.fetchall():
                result[r["cluster_id"]] = {
                    "tx_count": int(r["tx_count"] or 0),
                    "first_ts": float(r["first_ts"] or 0),
                    "last_ts":  float(r["last_ts"]  or 0),
                    "total_value": float(r["total_value"] or 0),
                }
        return result

    def _load_exposure(self) -> Dict[str, Tuple[float, float]]:
        result: Dict[str, Tuple[float, float]] = {}
        with self._conn.cursor() as cur:
            try:
                cur.execute("""
                    SELECT a_to.cluster_id AS tc,
                           SUM(CASE WHEN wc_from.risk_level='high' THEN t.value_eth ELSE 0 END) AS risky,
                           SUM(t.value_eth) AS total
                    FROM transactions t
                    JOIN addresses a_from ON a_from.address=t.from_address
                    JOIN addresses a_to   ON a_to.address=t.to_address
                    JOIN wallet_clusters wc_from ON wc_from.id=a_from.cluster_id
                    WHERE a_to.cluster_id IS NOT NULL
                    GROUP BY a_to.cluster_id
                """)
                for r in cur.fetchall():
                    result[r["tc"]] = (float(r["risky"] or 0), float(r["total"] or 0))
            except Exception:
                pass
        return result

    def _load_existing_poi(self) -> Set[str]:
        with self._conn.cursor() as cur:
            try:
                cur.execute("SELECT id FROM wallet_clusters WHERE is_poi=1")
                return {r["id"] for r in cur.fetchall()}
            except Exception:
                return set()

    def _label_score(self, labels: List[dict]) -> float:
        best = 0.0
        for lb in labels:
            w = LABEL_WEIGHTS.get(lb.get("category", ""),
                LABEL_WEIGHTS.get(lb.get("entity_type", ""), 0.0))
            best = max(best, w)
        return _clamp(best)

    def _behavior_score(self, behaviors: List[str]) -> float:
        return _clamp(sum(BEHAVIOR_WEIGHTS.get(b, 0.0) for b in behaviors))

    def _temporal_score(self, stats: dict) -> float:
        s = 0.0
        tx = stats.get("tx_count", 0)
        dur = stats.get("last_ts", 0) - stats.get("first_ts", 0)
        val = stats.get("total_value", 0)
        if tx > 50 and dur < 3600:   s += 0.2
        elif tx > 20 and dur < 1800: s += 0.15
        if val > 10 and dur < 3600:  s += 0.2
        elif val > 5 and dur < 7200: s += 0.1
        return _clamp(s)

    def _exposure_score(self, exp_tuple) -> float:
        if not isinstance(exp_tuple, tuple):
            return 0.0
        risky, total = exp_tuple
        if total < MIN_EXPOSURE_ETH:
            return 0.0
        return _clamp(risky / max(total, 1e-9))

    def _poi_reason(self, bd: dict) -> str:
        top = sorted(bd.items(), key=lambda x: x[1], reverse=True)
        parts = [f"{k}={v:.2f}" for k, v in top if v > 0.1][:3]
        return f"High risk: {', '.join(parts)}" if parts else "Multi-factor threshold exceeded"


def simulate_risk(entity_id: str, current_breakdown: dict, override: dict) -> dict:
    bd = dict(current_breakdown)
    if "add_label" in override:
        bd["label"] = max(bd.get("label", 0.0), LABEL_WEIGHTS.get(override["add_label"].lower(), 0.0))
    if "remove_label" in override:
        bd["label"] = 0.0
    if "toggle_behavior" in override:
        bd["behavior"] = _clamp(bd.get("behavior", 0.0) + BEHAVIOR_WEIGHTS.get(override["toggle_behavior"], 0.0))

    wl = float(override.get("weight_label",       W_LABEL))
    wb = float(override.get("weight_behavior",    W_BEHAVIOR))
    wp = float(override.get("weight_propagation", W_PROPAGATION))
    wt = float(override.get("weight_temporal",    W_TEMPORAL))
    we = float(override.get("weight_exposure",    W_EXPOSURE))

    new_score = _clamp(wl*bd.get("label",0) + wb*bd.get("behavior",0) +
                       wp*bd.get("propagation",0) + wt*bd.get("temporal",0) +
                       we*bd.get("exposure",0))

    changed = {k: round(bd[k] - current_breakdown.get(k, 0), 4)
               for k in bd if abs(bd[k] - current_breakdown.get(k, 0)) > 0.001}

    return {
        "entity_id":       entity_id,
        "new_risk_score":  round(new_score, 4),
        "new_breakdown":   {k: round(v, 4) for k, v in bd.items()},
        "changed_factors": changed,
        "would_be_poi":    new_score >= POI_ENTER,
    }
