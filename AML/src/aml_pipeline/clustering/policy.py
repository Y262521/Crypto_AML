"""Shared clustering policy for merge gating."""

from __future__ import annotations

from typing import Iterable, Set

PRIMARY_HEURISTICS = frozenset(
    {
        "behavioral_similarity",
        "repeated_flow",
        "loop_detection",
        "fan_pattern",
        "temporal_coordination",
        "contract_interaction",
    }
)


def should_merge_pair(heuristics_fired: Iterable[str], min_support: int = 2) -> bool:
    """Require multi-signal evidence and at least one primary heuristic."""
    fired: Set[str] = set(heuristics_fired)
    if len(fired) < max(min_support, 1):
        return False
    return bool(fired & PRIMARY_HEURISTICS)
