"""
Cluster Risk Scorer
=====================
Assigns a 0-100 risk score and human-readable labels to each cluster
based on which heuristics fired and the cluster's behavioural indicators.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set


@dataclass
class ClusterResult:
    cluster_id: str
    addresses: List[str]
    risk_score: float                    # 0 – 100
    labels: List[str]                    # e.g. ["possible_mixer", "fan_out"]
    heuristics_fired: List[str]          # which heuristics contributed
    indicators: Dict[str, object]        # raw behavioural stats
    explanation: str                     # human-readable summary


# Score contribution per heuristic
_HEURISTIC_SCORES: Dict[str, float] = {
    # Advanced
    "peel_chain":              40.0,   # layering via value-forwarding chain
    "layering":                38.0,   # rapid multi-hop + structuring
    "community_detection":     30.0,   # dense transaction community
    "address_poisoning":       28.0,   # visual address spoofing attack
    "dusting_attack":          25.0,   # surveillance dust campaign
    # Intermediate
    "loop_detection":          35.0,   # circular flows → layering
    "contract_interaction":    25.0,   # mixer / DeFi interaction
    "fan_pattern":             20.0,   # fan-out / fan-in
    "temporal_coordination":   20.0,   # coordinated timing
    "token_flow":              15.0,   # repeated ERC-20 flows
    "behavioral_similarity":   10.0,   # shared counterparties
}

# Label rules: (heuristic_name, label)
_LABEL_RULES: List[tuple] = [
    ("peel_chain",             "peel_chain_layering"),
    ("layering",               "rapid_layering"),
    ("community_detection",    "dense_transaction_community"),
    ("address_poisoning",      "address_poisoning_attack"),
    ("dusting_attack",         "dusting_surveillance"),
    ("loop_detection",         "possible_layering"),
    ("contract_interaction",   "possible_mixer"),
    ("fan_pattern",            "exchange_like_behavior"),
    ("temporal_coordination",  "coordinated_activity"),
    ("token_flow",             "token_flow_cluster"),
    ("behavioral_similarity",  "shared_counterparties"),
]


def score_cluster(
    cluster_id: str,
    addresses: Set[str],
    heuristics_fired: List[str],
    indicators: Dict[str, object],
) -> ClusterResult:
    """Compute risk score and labels for a single cluster."""
    score = 0.0
    for h in heuristics_fired:
        score += _HEURISTIC_SCORES.get(h, 5.0)

    # Bonus for large clusters (more addresses = more suspicious)
    size = len(addresses)
    if size >= 10:
        score += 15.0
    elif size >= 5:
        score += 8.0
    elif size >= 3:
        score += 3.0

    score = min(score, 100.0)

    labels = [label for h, label in _LABEL_RULES if h in heuristics_fired]
    if not labels:
        labels = ["normal"]

    # Build explanation
    parts = []
    if "peel_chain" in heuristics_fired:
        parts.append("peel chain detected — funds forwarded hop-by-hop to obscure origin")
    if "layering" in heuristics_fired:
        parts.append("rapid multi-hop layering or structuring (smurfing) detected")
    if "community_detection" in heuristics_fired:
        parts.append("dense transaction community — addresses transact heavily with each other")
    if "address_poisoning" in heuristics_fired:
        parts.append("address poisoning attack — visually similar addresses with zero-value transactions")
    if "dusting_attack" in heuristics_fired:
        parts.append("dusting attack — tiny transactions sent to many addresses for surveillance")
    if "loop_detection" in heuristics_fired:
        parts.append("circular fund flows detected (layering pattern)")
    if "contract_interaction" in heuristics_fired:
        parts.append("shared smart contract interactions (possible mixer)")
    if "fan_pattern" in heuristics_fired:
        parts.append("fan-in/fan-out pattern (consolidation or distribution)")
    if "temporal_coordination" in heuristics_fired:
        parts.append("coordinated transactions within short time windows")
    if "token_flow" in heuristics_fired:
        parts.append("repeated ERC-20 token flows between addresses")
    if "behavioral_similarity" in heuristics_fired:
        parts.append(f"share >= {indicators.get('min_shared_counterparties', '?')} common counterparties")

    explanation = "; ".join(parts) if parts else "No suspicious patterns detected."

    return ClusterResult(
        cluster_id=cluster_id,
        addresses=sorted(addresses),
        risk_score=round(score, 1),
        labels=labels,
        heuristics_fired=heuristics_fired,
        indicators=indicators,
        explanation=explanation,
    )
