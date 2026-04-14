"""
Cluster result model (no risk scoring).

Each cluster represents a likely real-world wallet/entity inferred from
behavioral link heuristics. Evidence is stored separately in MySQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ClusterResult:
    cluster_id: str
    addresses: List[str]
    heuristics_fired: List[str]
    heuristic_counts: Dict[str, int]
    indicators: Dict[str, object]


def build_cluster_result(
    cluster_id: str,
    addresses: List[str],
    heuristics_fired: List[str],
    indicators: Dict[str, object],
    *,
    heuristic_counts: Dict[str, int] | None = None,
) -> ClusterResult:
    counts = heuristic_counts or {}
    ranked = sorted(
        set(heuristics_fired),
        key=lambda h: (counts.get(h, 0), h),
        reverse=True,
    )
    return ClusterResult(
        cluster_id=cluster_id,
        addresses=sorted(addresses),
        heuristics_fired=ranked,
        heuristic_counts=counts,
        indicators=indicators,
    )
