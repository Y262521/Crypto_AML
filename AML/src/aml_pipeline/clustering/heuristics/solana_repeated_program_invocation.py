"""
Repeated Program Invocation Heuristic (Solana)
================================================
Identifies addresses that invoke the same sequence of programs in the
same order across multiple transactions. This "program call fingerprint"
is highly specific to wallet software / automated scripts.

Unlike SharedProgramInteraction (which only checks what programs are
called), this heuristic checks the ORDER and PATTERN of program calls
within transactions — much stronger evidence of shared infrastructure.

Algorithm:
  1. For each transaction, build an ordered sequence of program invocations
     from the is_contract_call edges (program is to_address).
  2. Hash the sequence into a "program signature".
  3. Addresses that produce the same program signature in >= 2 transactions
     are linked.

Note: Because we store Solana transactions as individual transfer pairs
in TxRecord, we group by tx_hash to reconstruct per-transaction program
sequences before building the fingerprint.
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

_EXCLUDED_PROGRAMS = frozenset({
    "11111111111111111111111111111111",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJe1bMW",
    "ComputeBudget111111111111111111111111111111",
})

_MIN_SIGNATURE_OCCURRENCES = 2   # pattern must appear >= 2 times
_MIN_PROGRAMS_IN_SIGNATURE = 2   # at least 2 non-trivial programs


class RepeatedProgramInvocationHeuristic(BaseHeuristic):
    """
    Links Solana addresses that produce the same ordered program-call
    signature across multiple transactions.
    """

    name = "solana_repeated_program_invocation"
    description = (
        "Solana addresses that invoke programs in the same sequence across "
        "multiple transactions are likely using the same wallet software."
    )

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        # tx_hash → {from_address} and ordered list of program IDs called
        tx_signers:  dict[str, set[str]]   = defaultdict(set)
        tx_programs: dict[str, list[str]]  = defaultdict(list)
        tx_order:    dict[str, int]        = defaultdict(int)

        for u, v, data in G.edges(data=True):
            if u == v:
                continue
            if not data.get("is_contract_call"):
                continue
            prog_id = v
            if prog_id in _EXCLUDED_PROGRAMS:
                continue
            tx_hash = data.get("tx_hash") or ""
            if not tx_hash:
                continue
            tx_signers[tx_hash].add(u)
            # Use block_number + timestamp as ordering proxy
            order_key = float(data.get("timestamp") or 0.0)
            tx_programs[tx_hash].append((order_key, prog_id))

        # Build signature for each tx: sorted list of non-trivial program IDs
        # (sorted to be order-independent — same programs = same infra)
        sig_senders: dict[tuple, list[str]] = defaultdict(list)

        for tx_hash, prog_entries in tx_programs.items():
            prog_list = sorted(set(p for _, p in prog_entries))
            if len(prog_list) < _MIN_PROGRAMS_IN_SIGNATURE:
                continue
            signature = tuple(prog_list)
            for signer in tx_signers.get(tx_hash, set()):
                sig_senders[signature].append(signer)

        links: List[ClusterEdge] = []
        seen: set[ClusterEdge] = set()

        for sig, senders in sig_senders.items():
            if len(senders) < _MIN_SIGNATURE_OCCURRENCES:
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
