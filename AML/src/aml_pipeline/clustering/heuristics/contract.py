"""
Smart Contract Interaction Heuristic
======================================
Addresses that interact with the same smart contracts (DeFi, mixers, bridges)
are grouped together.

Additionally detects Deposit → Contract → Withdraw cycles:
  addr_A  →  contract  →  addr_B
where addr_A and addr_B are linked because they use the same contract
as an intermediary (classic mixer / tumbler pattern).
"""

from __future__ import annotations

from collections import defaultdict
from typing import List, Set

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

# Minimum number of addresses that must share a contract before we link them
_MIN_SHARED_CONTRACT_USERS = 2


class ContractInteractionHeuristic(BaseHeuristic):
    name = "contract_interaction"
    description = (
        "Addresses interacting with the same smart contracts are grouped. "
        "Deposit→Contract→Withdraw cycles are flagged as mixer-like behaviour."
    )

    def __init__(self, cfg: Config):
        super().__init__(cfg)

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        links: List[ClusterEdge] = []

        # Identify contract nodes: nodes that receive contract-call edges
        contract_nodes: Set[str] = set()
        for u, v, data in G.edges(data=True):
            if data.get("is_contract_call"):
                contract_nodes.add(v)

        # Group addresses by which contracts they call
        contract_callers: dict[str, set] = defaultdict(set)
        for u, v, data in G.edges(data=True):
            if v in contract_nodes and data.get("is_contract_call"):
                contract_callers[v].add(u)

        # Link all callers of the same contract
        for contract, callers in contract_callers.items():
            caller_list = sorted(callers)
            for i in range(len(caller_list)):
                for j in range(i + 1, len(caller_list)):
                    links.append((caller_list[i], caller_list[j]))

        # Detect Deposit → Contract → Withdraw:
        # addr_A → contract → addr_B  (A deposits, B withdraws via same contract)
        for contract in contract_nodes:
            depositors = {u for u, v in G.in_edges(contract)}
            withdrawers = {v for u, v in G.out_edges(contract)}
            # Addresses that only deposit (not withdraw) paired with those that only withdraw
            pure_depositors = depositors - withdrawers
            pure_withdrawers = withdrawers - depositors
            for dep in pure_depositors:
                for wit in pure_withdrawers:
                    if dep != wit:
                        links.append((dep, wit))

        return links
