"""
Repeated Program Invocation Heuristic (Solana)
================================================
Accounts that repeatedly invoke the same non-trivial program in the same
sequence pattern are likely running the same automated script or bot.

Unlike SharedProgramInteractionHeuristic (which looks at program SETS),
this heuristic looks at program SEQUENCES — the ordered list of programs
invoked in a single transaction.

A unique program invocation sequence is a strong wallet fingerprint
because it indicates the same code path was executed.

Detection:
  1. For each transaction, build a normalized program sequence
     (ordered list of non-system program IDs)
  2. Group transactions by their program sequence fingerprint
  3. Link from_addresses sharing the same sequence across >= 2 txs

False-positive controls:
  - Sequences of length 1 (single program) are excluded (too common)
  - Sequences seen in only 1 transaction are excluded
  - System programs are filtered from sequences
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

_SYSTEM_PROGRAMS = frozenset({
    "11111111111111111111111111111111",
    "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr",
    "ComputeBudget111111111111111111111111111111",
    "Vote111111111111111111111111111111111111111h",
    "SysvarRent111111111111111111111111111111111",
    "SysvarC1ock11111111111111111111111111111111",
})

_MIN_SEQUENCE_LENGTH  = 2   # at least 2 non-system programs
_MIN_OCCURRENCES      = 2   # sequence must appear in >= 2 txs


class RepeatedProgramInvocationHeuristic(BaseHeuristic):
    """
    Links Solana accounts sharing the same program invocation sequence
    across multiple transactions.
    """

    name = "solana_repeated_program"
    description = (
        "Solana accounts invoking the same sequence of non-trivial programs "
        "across multiple transactions are likely running the same automation."
    )

    def _extract_program_sequence(self, data: dict) -> tuple[str, ...]:
        """
        Extract ordered program sequence from input_method_id encoding.
        Format: "feepayer|prog1|prog2|prog3"
        """
        mid = data.get("input_method_id") or ""
        if not mid or "|" not in mid:
            return ()
        parts = mid.split("|")
        # Skip first part (fee_payer)
        programs = tuple(
            p.strip() for p in parts[1:]
            if p.strip() and p.strip() not in _SYSTEM_PROGRAMS
        )
        return programs

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        # sequence → list of from_addresses
        seq_senders: dict[tuple, list[str]] = defaultdict(list)
        # sequence → tx count
        seq_tx_count: Counter[tuple] = Counter()

        for u, v, data in G.edges(data=True):
            if u == v:
                continue
            seq = self._extract_program_sequence(data)
            if len(seq) < _MIN_SEQUENCE_LENGTH:
                continue
            seq_senders[seq].append(u)
            seq_tx_count[seq] += 1

        links: List[ClusterEdge] = []
        seen: set[ClusterEdge] = set()

        for seq, senders in seq_senders.items():
            if seq_tx_count[seq] < _MIN_OCCURRENCES:
                continue
            unique_senders = sorted(set(senders))
            if len(unique_senders) < 2:
                continue
            for i in range(len(unique_senders)):
                for j in range(i + 1, len(unique_senders)):
                    pair = (unique_senders[i], unique_senders[j])
                    if pair not in seen:
                        links.append(pair)
                        seen.add(pair)

        return links
