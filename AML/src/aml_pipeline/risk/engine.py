"""
Multi-Factor Risk Engine v3
============================
Institutional-grade AML scoring with full Integration stage support,
exponential behavior normalization, weighted propagation, and explainability.

Formula:
    risk_score = 0.25*label
               + 0.20*behavior
               + 0.15*propagation
               + 0.10*temporal
               + 0.10*exposure
               + 0.20*integration

All factor scores are in [0, 1].
Final risk_score is clamped to [0, 1].

POI hysteresis:
    Enter POI: risk_score >= 0.80 AND at least 2 factors >= 0.4
    Exit  POI: risk_score <  0.70
"""

from __future__ import annotations

import json
import logging
import math
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ── Label weights ─────────────────────────────────────────────────────────────
# Tiered: sanctioned/scam/mixer → high (0.9–1.0)
#         watchlist             → medium (≤ 0.6)
#         exchange              → capped low (≤ 0.2)
#         unknown               → 0
LABEL_WEIGHTS: Dict[str, float] = {
    "sanctioned":  1.00, "sanction":    1.00,
    "scam":        0.95, "fraud":       0.92,
    "mixer":       0.90, "mixing":      0.90,
    "darknet":     0.88, "ransomware":  0.88,
    "hack":        0.82, "exploit":     0.82,
    "high_risk":   0.75,
    "watchlist":   0.55,
    "exchange":    0.15,
    "merchant":    0.05,
    "unknown":     0.00,
}

# ── Behavior weights (used in exponential normalization) ──────────────────────
BEHAVIOR_WEIGHTS: Dict[str, float] = {
    "loop_detection":               0.40,
    "coordinated_cashout":          0.40,
    "mixing_interaction":           0.35,
    "shell_wallet_network":         0.35,
    "bridge_hopping":               0.30,
    "peeling_chain":                0.30,
    "smurfing":                     0.25,
    "structuring":                  0.25,
    "high_depth_transaction_chaining": 0.25,
    "micro_funding":                0.15,
    "immediate_utilization":        0.10,
    "funneling":                    0.10,
}

# ── Integration signal weights ────────────────────────────────────────────────
INTEGRATION_SIGNAL_WEIGHTS: Dict[str, float] = {
    "terminal_node":     0.30,
    "convergence":       0.25,
    "value_reaggregation": 0.20,
    "dormancy":          0.15,
    "asset_transformation": 0.10,
}

# ── Factor weights (must sum to 1.0) ─────────────────────────────────────────
W_LABEL       = 0.25
W_BEHAVIOR    = 0.20
W_PROPAGATION = 0.15
W_TEMPORAL    = 0.10
W_EXPOSURE    = 0.10
W_INTEGRATION = 0.20

# ── POI thresholds ────────────────────────────────────────────────────────────
POI_ENTER = 0.80   # enter POI if score >= this AND >= 2 factors >= 0.4
POI_EXIT  = 0.70   # exit  POI if score <  this

RISK_VERSION    = "v3.0"
MIN_EXPOSURE_ETH = 0.01

# ── Propagation hop decay ─────────────────────────────────────────────────────
PROPAGATION_DECAY = {1: 0.60, 2: 0.30, 3: 0.10}


def _clamp(v) -> float:
    return max(0.0, min(1.0, float(v or 0)))


# ─────────────────────────────────────────────────────────────────────────────
# Entity Graph
# ─────────────────────────────────────────────────────────────────────────────

class EntityGraph:
    """
    Adjacency map built from on-chain transactions.
    Edges are weighted by total ETH volume between cluster pairs.
    Cached for the lifetime of a single RiskEngine.run() call.
    """

    def __init__(self):
        self._adj: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._built = False

    def build(self, conn) -> None:
        if self._built:
            return
        logger.info("EntityGraph: building adjacency map...")
        with conn.cursor() as cur:
            cur.execute("""
                SELECT a_from.cluster_id AS fe,
                       a_to.cluster_id   AS te,
                       SUM(t.value_eth)  AS val
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
        logger.info("EntityGraph: %d nodes loaded", len(self._adj))

    def propagation_risk(
        self,
        eid: str,
        poi_scores: Dict[str, float],   # entity_id → risk_score for known POIs
        cache: Dict[str, float],
    ) -> float:
        """
        BFS up to 3 hops. For each POI neighbour found at hop h:
            contribution = poi_risk_score * PROPAGATION_DECAY[h]
        Returns the maximum contribution across all reachable POIs.
        """
        if eid in cache:
            return cache[eid]
        if eid in poi_scores:
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
                if nb in poi_scores:
                    decay = PROPAGATION_DECAY.get(hop, 0.0)
                    contribution = poi_scores[nb] * decay
                    best = max(best, contribution)
                q.append((nb, hop))

        result = _clamp(best)
        cache[eid] = result
        return result

    def connected_risky(
        self,
        eid: str,
        risk_scores: Dict[str, float],
        top_n: int = 5,
    ) -> List[dict]:
        """Return top-N connected entities ranked by risk_score × tx_volume."""
        neighbors = self._adj.get(eid, {})
        result = [
            {
                "entity_id":    nb,
                "risk_score":   round(risk_scores.get(nb, 0.0), 4),
                "tx_volume_eth": round(vol, 4),
            }
            for nb, vol in neighbors.items()
            if risk_scores.get(nb, 0.0) > 0
        ]
        result.sort(key=lambda x: x["risk_score"] * x["tx_volume_eth"], reverse=True)
        return result[:top_n]


# ─────────────────────────────────────────────────────────────────────────────
# Risk Engine
# ─────────────────────────────────────────────────────────────────────────────

class RiskEngine:
    def __init__(self, conn):
        self._conn  = conn
        self._graph = EntityGraph()

    # ── Public entry point ────────────────────────────────────────────────────

    def run(self) -> dict:
        logger.info("RiskEngine v3: starting full scoring run...")
        self._ensure_columns()
        self._ensure_poi_alerts_table()

        clusters         = self._load_clusters()
        labels_map       = self._load_labels()
        behaviors_map    = self._load_behaviors()
        tx_stats         = self._load_tx_stats()
        exposure_map     = self._load_exposure()
        integration_map  = self._load_integration_signals()
        poi_set          = self._load_existing_poi()

        self._graph.build(self._conn)

        # Build poi_scores dict for weighted propagation
        poi_scores: Dict[str, float] = {}
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, COALESCE(risk_score, 0) AS rs "
                "FROM wallet_clusters WHERE is_poi = 1"
            )
            for r in cur.fetchall():
                poi_scores[r["id"]] = float(r["rs"] or 0)

        prop_cache: Dict[str, float] = {}
        scored = poi_count = 0
        computed_scores: Dict[str, float] = {}

        with self._conn.cursor() as cur:
            for cluster_id, cluster in clusters.items():
                labels      = labels_map.get(cluster_id, [])
                behaviors   = behaviors_map.get(cluster_id, [])
                stats       = tx_stats.get(cluster_id, {})
                exp_tuple   = exposure_map.get(cluster_id, (0.0, 0.0))
                int_signals = integration_map.get(cluster_id, {})

                prop = self._graph.propagation_risk(cluster_id, poi_scores, prop_cache)

                breakdown = {
                    "label":       self._label_score(labels),
                    "behavior":    self._behavior_score(behaviors),
                    "propagation": prop,
                    "temporal":    self._temporal_score(stats),
                    "exposure":    self._exposure_score(exp_tuple),
                    "integration": self._integration_score(int_signals),
                }

                risk_score = _clamp(
                    W_LABEL       * breakdown["label"]
                    + W_BEHAVIOR    * breakdown["behavior"]
                    + W_PROPAGATION * breakdown["propagation"]
                    + W_TEMPORAL    * breakdown["temporal"]
                    + W_EXPOSURE    * breakdown["exposure"]
                    + W_INTEGRATION * breakdown["integration"]
                )
                computed_scores[cluster_id] = risk_score

                # ── POI hysteresis ────────────────────────────────────────────
                was_poi = cluster_id in poi_set
                if risk_score >= POI_ENTER:
                    is_poi = 1
                elif risk_score < POI_EXIT:
                    is_poi = 0
                else:
                    is_poi = 1 if was_poi else 0

                # Safety gate: require at least 2 factors >= 0.4
                # Prevents propagation alone from triggering POI
                strong_factors = sum(1 for v in breakdown.values() if v >= 0.4)
                if is_poi and strong_factors < 2:
                    is_poi = 0

                poi_reason = self._poi_reason(breakdown) if is_poi else None

                cur.execute("""
                    UPDATE wallet_clusters
                    SET risk_score       = %s,
                        risk_breakdown   = %s,
                        risk_version     = %s,
                        last_risk_update = %s,
                        is_poi           = %s,
                        poi_reason       = CASE WHEN %s IS NOT NULL THEN %s ELSE poi_reason END
                    WHERE id = %s
                """, (
                    round(risk_score, 6),
                    json.dumps({k: round(v, 4) for k, v in breakdown.items()}),
                    RISK_VERSION,
                    datetime.now(timezone.utc),
                    is_poi,
                    poi_reason, poi_reason,
                    cluster_id,
                ))
                scored += 1
                if is_poi:
                    poi_count += 1

        self._conn.commit()
        logger.info("RiskEngine v3: scored=%d poi=%d", scored, poi_count)
        return {
            "status":      "success",
            "scored":      scored,
            "poi_count":   poi_count,
            "graph_nodes": len(self._graph._adj),
            "version":     RISK_VERSION,
        }

    def get_connected_risky(self, entity_id: str, top_n: int = 5) -> List[dict]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT id, COALESCE(risk_score, 0) AS rs FROM wallet_clusters")
            scores = {r["id"]: float(r["rs"] or 0) for r in cur.fetchall()}
        if not self._graph._built:
            self._graph.build(self._conn)
        return self._graph.connected_risky(entity_id, scores, top_n)

    # ── Schema helpers ────────────────────────────────────────────────────────

    def _ensure_columns(self) -> None:
        cols = {
            "risk_score":      "DECIMAL(8,6) NOT NULL DEFAULT 0",
            "risk_breakdown":  "JSON NULL",
            "risk_version":    "VARCHAR(20) NULL",
            "last_risk_update": "DATETIME NULL",
            "is_poi":          "TINYINT(1) NOT NULL DEFAULT 0",
            "poi_reason":      "TEXT NULL",
        }
        with self._conn.cursor() as cur:
            cur.execute("DESCRIBE wallet_clusters")
            existing = {r["Field"] for r in cur.fetchall()}
            for col, defn in cols.items():
                if col not in existing:
                    cur.execute(
                        f"ALTER TABLE wallet_clusters ADD COLUMN {col} {defn}"
                    )
        self._conn.commit()

    def _ensure_poi_alerts_table(self) -> None:
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

    # ── Data loaders ──────────────────────────────────────────────────────────

    def _load_clusters(self) -> Dict[str, dict]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, owner_id, total_balance, risk_level FROM wallet_clusters"
            )
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
                    "category":    (r["list_category"] or "").lower(),
                    "entity_type": (r["entity_type"]   or "").lower(),
                })
        return result

    def _load_behaviors(self) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = defaultdict(list)
        with self._conn.cursor() as cur:
            # Placement behaviors
            try:
                cur.execute("""
                    SELECT pe.source_cluster_ids_json, pb.behavior_type
                    FROM placement_behaviors pb
                    JOIN placement_entities pe
                      ON pe.entity_id = pb.entity_id AND pe.run_id = pb.run_id
                    WHERE pb.run_id = (
                        SELECT id FROM placement_runs ORDER BY created_at DESC LIMIT 1
                    )
                """)
                for r in cur.fetchall():
                    try:
                        for cid in json.loads(r["source_cluster_ids_json"] or "[]"):
                            result[cid].append(r["behavior_type"])
                    except Exception:
                        pass
            except Exception:
                pass
            # Layering detector hits
            try:
                cur.execute("""
                    SELECT le.entity_id, ldh.detector_type
                    FROM layering_detector_hits ldh
                    JOIN layering_entities le
                      ON le.entity_id = ldh.entity_id AND le.run_id = ldh.run_id
                    WHERE ldh.run_id = (
                        SELECT id FROM layering_runs ORDER BY created_at DESC LIMIT 1
                    )
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
                       COUNT(t.tx_hash)                    AS tx_count,
                       MIN(UNIX_TIMESTAMP(t.timestamp))    AS first_ts,
                       MAX(UNIX_TIMESTAMP(t.timestamp))    AS last_ts,
                       SUM(t.value_eth)                    AS total_value
                FROM addresses a
                JOIN transactions t
                  ON t.from_address = a.address OR t.to_address = a.address
                WHERE a.cluster_id IS NOT NULL
                GROUP BY a.cluster_id
            """)
            for r in cur.fetchall():
                result[r["cluster_id"]] = {
                    "tx_count":    int(r["tx_count"]    or 0),
                    "first_ts":    float(r["first_ts"]  or 0),
                    "last_ts":     float(r["last_ts"]   or 0),
                    "total_value": float(r["total_value"] or 0),
                }
        return result

    def _load_exposure(self) -> Dict[str, Tuple[float, float]]:
        result: Dict[str, Tuple[float, float]] = {}
        with self._conn.cursor() as cur:
            try:
                cur.execute("""
                    SELECT a_to.cluster_id AS tc,
                           SUM(CASE WHEN wc_from.risk_level = 'high'
                                    THEN t.value_eth ELSE 0 END) AS risky,
                           SUM(t.value_eth) AS total
                    FROM transactions t
                    JOIN addresses a_from ON a_from.address = t.from_address
                    JOIN addresses a_to   ON a_to.address   = t.to_address
                    JOIN wallet_clusters wc_from ON wc_from.id = a_from.cluster_id
                    WHERE a_to.cluster_id IS NOT NULL
                    GROUP BY a_to.cluster_id
                """)
                for r in cur.fetchall():
                    result[r["tc"]] = (float(r["risky"] or 0), float(r["total"] or 0))
            except Exception:
                pass
        return result

    def _load_integration_signals(self) -> Dict[str, Dict[str, float]]:
        """
        Load integration signal scores from the latest integration run.
        Returns: { entity_id: { signal_name: score, ... } }
        """
        result: Dict[str, Dict[str, float]] = defaultdict(dict)
        with self._conn.cursor() as cur:
            try:
                cur.execute("""
                    SELECT entity_id, signals_fired_json, signal_scores_json
                    FROM integration_alerts
                    WHERE run_id = (
                        SELECT id FROM integration_runs
                        WHERE status = 'completed'
                        ORDER BY completed_at DESC
                        LIMIT 1
                    )
                """)
                for r in cur.fetchall():
                    eid = r["entity_id"]
                    try:
                        scores = json.loads(r["signal_scores_json"] or "{}")
                        if isinstance(scores, dict):
                            result[eid] = {k: float(v or 0) for k, v in scores.items()}
                    except Exception:
                        pass
            except Exception:
                pass
        return result

    def _load_existing_poi(self) -> Set[str]:
        with self._conn.cursor() as cur:
            try:
                cur.execute("SELECT id FROM wallet_clusters WHERE is_poi = 1")
                return {r["id"] for r in cur.fetchall()}
            except Exception:
                return set()

    # ── Factor scoring ────────────────────────────────────────────────────────

    def _label_score(self, labels: List[dict]) -> float:
        """
        Take the highest-risk label from owner_list.
        Tiers:
          sanctioned/scam/mixer → 0.90–1.00
          watchlist             → capped at 0.60
          exchange              → capped at 0.20
          unknown               → 0.0
        """
        best = 0.0
        for lb in labels:
            raw = LABEL_WEIGHTS.get(
                lb.get("category", ""),
                LABEL_WEIGHTS.get(lb.get("entity_type", ""), 0.0),
            )
            best = max(best, raw)
        return _clamp(best)

    def _behavior_score(self, behaviors: List[str]) -> float:
        """
        Exponential normalization prevents score saturation:
            score = 1 - exp(-sum_of_weights)
        A single high-weight behavior (e.g. loop_detection=0.40) → 0.33
        Two high-weight behaviors (0.40+0.40=0.80)               → 0.55
        Many behaviors (sum=2.0)                                  → 0.86
        """
        total_weight = sum(BEHAVIOR_WEIGHTS.get(b, 0.0) for b in behaviors)
        if total_weight <= 0:
            return 0.0
        return _clamp(1.0 - math.exp(-total_weight))

    def _temporal_score(self, stats: dict) -> float:
        """
        Detects burst activity: many transactions in a short window,
        or large value moved quickly.
        """
        s = 0.0
        tx  = stats.get("tx_count", 0)
        dur = stats.get("last_ts", 0) - stats.get("first_ts", 0)
        val = stats.get("total_value", 0)

        if   tx > 50 and dur < 3600:   s += 0.25
        elif tx > 20 and dur < 1800:   s += 0.15
        elif tx > 10 and dur < 3600:   s += 0.10

        if   val > 10 and dur < 3600:  s += 0.25
        elif val > 5  and dur < 7200:  s += 0.15
        elif val > 1  and dur < 14400: s += 0.05

        return _clamp(s)

    def _exposure_score(self, exp_tuple) -> float:
        """
        Fraction of incoming ETH that originated from high-risk clusters.
        Requires minimum volume to avoid noise from dust transactions.
        """
        if not isinstance(exp_tuple, tuple):
            return 0.0
        risky, total = exp_tuple
        if total < MIN_EXPOSURE_ETH:
            return 0.0
        return _clamp(risky / max(total, 1e-9))

    def _integration_score(self, signals: Dict[str, float]) -> float:
        """
        Weighted sum of integration signals from the integration pipeline.

        Signal weights:
            terminal_node        0.30  — funds stop here (exit point)
            convergence          0.25  — fan-in from multiple senders
            value_reaggregation  0.20  — reassembly of split funds
            dormancy             0.15  — cooling-off then activation
            asset_transformation 0.10  — token/chain swap to obscure origin

        Each signal score is in [0, 1].
        Final score is clamped to [0, 1].
        """
        if not signals:
            return 0.0
        total = sum(
            INTEGRATION_SIGNAL_WEIGHTS.get(sig, 0.0) * _clamp(score)
            for sig, score in signals.items()
        )
        return _clamp(total)

    # ── POI reason ────────────────────────────────────────────────────────────

    def _poi_reason(self, bd: dict) -> str:
        """
        Human-readable explanation of why an entity was designated POI.
        Lists the top 3 contributing factors with their scores.
        """
        top = sorted(bd.items(), key=lambda x: x[1], reverse=True)
        parts = [f"{k}={v:.2f}" for k, v in top if v > 0.10][:3]
        return (
            f"Multi-factor POI: {', '.join(parts)}"
            if parts
            else "Multi-factor threshold exceeded"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Safe simulation (no DB writes)
# ─────────────────────────────────────────────────────────────────────────────

def simulate_risk(entity_id: str, current_breakdown: dict, override: dict) -> dict:
    """
    Apply hypothetical overrides to an entity's risk breakdown and
    recompute the score in memory. Nothing is written to the database.

    Supported override keys:
        add_label        (str)   — inject a label (e.g. "sanctioned")
        remove_label     (bool)  — zero out the label factor
        toggle_behavior  (str)   — add a behavior signal
        add_integration  (str)   — inject an integration signal name
        weight_*         (float) — override individual factor weights
    """
    bd = dict(current_breakdown)

    # Label overrides
    if "add_label" in override and override["add_label"]:
        injected = LABEL_WEIGHTS.get(str(override["add_label"]).lower(), 0.0)
        bd["label"] = max(bd.get("label", 0.0), injected)
    if override.get("remove_label"):
        bd["label"] = 0.0

    # Behavior override — exponential re-normalization
    if "toggle_behavior" in override and override["toggle_behavior"]:
        bw = BEHAVIOR_WEIGHTS.get(str(override["toggle_behavior"]), 0.0)
        # Reverse-engineer current sum from existing behavior score, add new weight
        existing = bd.get("behavior", 0.0)
        # Approximate inverse: sum ≈ -ln(1 - score)
        current_sum = -math.log(max(1.0 - existing, 1e-9)) if existing < 1.0 else 3.0
        new_sum = current_sum + bw
        bd["behavior"] = _clamp(1.0 - math.exp(-new_sum))

    # Integration signal override
    if "add_integration" in override and override["add_integration"]:
        sig = str(override["add_integration"])
        sig_weight = INTEGRATION_SIGNAL_WEIGHTS.get(sig, 0.10)
        bd["integration"] = _clamp(bd.get("integration", 0.0) + sig_weight)

    # Factor weight overrides (allow analysts to stress-test weighting)
    wl = float(override.get("weight_label",       W_LABEL))
    wb = float(override.get("weight_behavior",    W_BEHAVIOR))
    wp = float(override.get("weight_propagation", W_PROPAGATION))
    wt = float(override.get("weight_temporal",    W_TEMPORAL))
    we = float(override.get("weight_exposure",    W_EXPOSURE))
    wi = float(override.get("weight_integration", W_INTEGRATION))

    new_score = _clamp(
        wl * bd.get("label",       0.0)
        + wb * bd.get("behavior",    0.0)
        + wp * bd.get("propagation", 0.0)
        + wt * bd.get("temporal",    0.0)
        + we * bd.get("exposure",    0.0)
        + wi * bd.get("integration", 0.0)
    )

    changed = {
        k: round(bd.get(k, 0.0) - current_breakdown.get(k, 0.0), 4)
        for k in set(list(bd.keys()) + list(current_breakdown.keys()))
        if abs(bd.get(k, 0.0) - current_breakdown.get(k, 0.0)) > 0.001
    }

    # POI check: score >= 0.80 AND at least 2 factors >= 0.4
    strong_factors = sum(1 for v in bd.values() if v >= 0.4)
    would_be_poi = new_score >= POI_ENTER and strong_factors >= 2

    return {
        "entity_id":       entity_id,
        "new_risk_score":  round(new_score, 4),
        "new_breakdown":   {k: round(v, 4) for k, v in bd.items()},
        "changed_factors": changed,
        "would_be_poi":    would_be_poi,
        "strong_factors":  strong_factors,
    }
