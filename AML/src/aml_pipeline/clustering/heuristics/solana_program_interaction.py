"""
Shared Program Interaction Heuristic (Solana)
===============================================
Solana programs (smart contracts) are identified by their program ID.
Accounts that invoke the same set of non-trivial programs repeatedly
are likely controlled by the same entity or wallet software.

"Non-trivial" programs exclude:
  - System Program   (11111…)  — every wallet uses this
  - Memo Program     (MemoSq…) — metadata-only
  - Compute Budget   (ComputeBudget111…)

A wallet fingerprint is derived from the sorted set of programs it
invokes. Accounts sharing identical or highly overlapping program sets
across multiple transactions are linked.

Evidence strength:
  - Same programs in 1 tx:  weak
  - Same programs in 2+ txs: moderate
  - Rare programs (invoked by < 5% of addresses) in 2+ txs: strong
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import List, Set

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

# Programs excluded from fingerprinting (too common)
_SYSTEM_PROGRAMS = frozenset({
    "11111111111111111111111111111111",          # System Program
    "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",  # Memo
    "ComputeBudget111111111111111111111111111111",    # Compute Budget
    "Vote111111111111111111111111111111111111111h",   # Vote Program
})

_MIN_SHARED_PROGRAMS   = 1
_MIN_SHARED_TX_COUNT   = 2
_RARE_PROGRAM_MAX_FREQ = 0.05   # < 5% of all addresses → "rare"


class SharedProgramInteractionHeuristic(BaseHeuristic):
    """
    Links Solana accounts sharing the same non-trivial program interactions.
    """

    name = "solana_shared_program"
    description = (
        "Solana accounts invoking the same set of non-trivial programs "
        "across multiple transactions are likely controlled by the same entity."
    )

    def _extract_programs(self, data: dict) -> frozenset[str]:
        """Extract program IDs from input_method_id encoding."""
        mid = data.get("input_method_id") or ""
        if not mid:
            return frozenset()
        parts = mid.split("|")
        # First part is fee_payer; rest are programs
        programs = {p.strip() for p in parts[1:] if p.strip()}
        return frozenset(programs - _SYSTEM_PROGRAMS)

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        # addr → set of programs they've used
        addr_programs: dict[str, set[str]] = defaultdict(set)
        # program → count of addresses using it
        program_freq: Counter[str] = Counter()
        total_addresses: Set[str] = set()

        for u, v, data in G.edges(data=True):
            if u == v:
                continue
            programs = self._extract_programs(data)
            if not programs:
                continue
            addr_programs[u].update(programs)
            for p in programs:
                program_freq[p] += 1
            total_addresses.add(u)

        if not total_addresses:
            return []

        n_addr = len(total_addresses)

        # Identify rare programs
        rare_programs = {
            p for p, cnt in program_freq.items()
            if cnt / n_addr < _RARE_PROGRAM_MAX_FREQ
        }

        # program_fingerprint → list of addresses with that fingerprint
        fingerprint_addrs: dict[frozenset, list[str]] = defaultdict(list)
        for addr, programs in addr_programs.items():
            non_trivial = frozenset(programs - _SYSTEM_PROGRAMS)
            if len(non_trivial) >= _MIN_SHARED_PROGRAMS:
                fingerprint_addrs[non_trivial].append(addr)

        links: List[ClusterEdge] = []
        seen: set[ClusterEdge] = set()

        for prog_set, addrs in fingerprint_addrs.items():
            unique_addrs = sorted(set(addrs))
            if len(unique_addrs) < 2:
                continue

            # Boost confidence if rare programs are involved
            has_rare = bool(prog_set & rare_programs)
            min_required = 2 if has_rare else _MIN_SHARED_TX_COUNT + 1

            if len(unique_addrs) < 2:
                continue

            for i in range(len(unique_addrs)):
                for j in range(i + 1, len(unique_addrs)):
                    pair = (unique_addrs[i], unique_addrs[j])
                    if pair not in seen:
                        links.append(pair)
                        seen.add(pair)

        return links
