"""
Shared Program Interaction Heuristic (Solana)
===============================================
Solana on-chain programs (smart contracts) are referenced by their Program ID.
Addresses that repeatedly interact with the same set of non-trivial programs
(excluding system-level programs) are likely part of the same ecosystem
or controlled by the same entity using the same wallet infrastructure.

"Non-trivial program" means NOT:
  - System Program (11111111111111111111111111111111)
  - Token Program (TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA)
  - Associated Token Program
  - Compute Budget Program

These are excluded because virtually every wallet interacts with them.

Algorithm:
  1. For each from_address, collect the set of program IDs it called
     (via to_address where is_contract_call=True).
  2. Pair addresses sharing >= K non-trivial programs.
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

# System-level programs to exclude (too common to be meaningful signal)
_EXCLUDED_PROGRAMS = frozenset({
    "11111111111111111111111111111111",           # System Program
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # Token Program
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",  # Token-2022
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJe1bMW",  # Associated Token
    "ComputeBudget111111111111111111111111111111",    # Compute Budget
    "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",  # Memo
    "Vote111111111111111111111111111111111111111h",   # Vote
})

_MIN_SHARED_PROGRAMS  = 2
_MIN_INTERACTIONS     = 2   # must interact with the program at least twice


class SharedProgramInteractionHeuristic(BaseHeuristic):
    """
    Links Solana addresses that interact with the same set of non-trivial programs.
    """

    name = "solana_shared_program"
    description = (
        "Solana addresses interacting with the same set of non-trivial programs "
        "are likely controlled by the same entity."
    )

    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.min_shared = int(
            getattr(cfg, "solana_min_shared_programs", _MIN_SHARED_PROGRAMS)
        )

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        # address → {program_id: interaction_count}
        addr_programs: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for u, v, data in G.edges(data=True):
            if u == v:
                continue
            if not data.get("is_contract_call"):
                continue
            # v is the program / contract being called
            prog_id = v
            if not prog_id or prog_id in _EXCLUDED_PROGRAMS:
                continue
            addr_programs[u][prog_id] += 1

        # Filter: only keep programs with >= _MIN_INTERACTIONS
        filtered: dict[str, set[str]] = {
            addr: {
                prog for prog, cnt in progs.items()
                if cnt >= _MIN_INTERACTIONS
            }
            for addr, progs in addr_programs.items()
        }
        filtered = {addr: progs for addr, progs in filtered.items() if progs}

        # Build inverted index: program → list of addresses
        prog_users: dict[str, list[str]] = defaultdict(list)
        for addr, progs in filtered.items():
            for prog in progs:
                prog_users[prog].append(addr)

        # Count shared programs per pair
        pair_shared: dict[tuple[str, str], int] = defaultdict(int)
        for prog, users in prog_users.items():
            if len(users) < 2:
                continue
            users_sorted = sorted(set(users))
            for i in range(len(users_sorted)):
                for j in range(i + 1, len(users_sorted)):
                    pair_shared[(users_sorted[i], users_sorted[j])] += 1

        links: List[ClusterEdge] = []
        for pair, count in pair_shared.items():
            if count >= self.min_shared:
                links.append(pair)

        return links
