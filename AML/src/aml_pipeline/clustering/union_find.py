"""
Union-Find (Disjoint Set Union) data structure.

Used to merge address pairs from multiple heuristics into clusters
efficiently in O(α(n)) amortised time per operation.
"""

from __future__ import annotations

from typing import Dict, List, Set


class UnionFind:
    def __init__(self, nodes: List[str]):
        self._parent: Dict[str, str] = {n: n for n in nodes}
        self._rank: Dict[str, int] = {n: 0 for n in nodes}

    def find(self, x: str) -> str:
        if self._parent[x] != x:
            self._parent[x] = self.find(self._parent[x])   # path compression
        return self._parent[x]

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        # Union by rank
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1

    def add(self, x: str) -> None:
        if x not in self._parent:
            self._parent[x] = x
            self._rank[x] = 0

    def clusters(self) -> Dict[str, Set[str]]:
        """Return {root: {members}} for all clusters with >= 1 member."""
        groups: Dict[str, Set[str]] = {}
        for node in self._parent:
            root = self.find(node)
            groups.setdefault(root, set()).add(node)
        return groups
