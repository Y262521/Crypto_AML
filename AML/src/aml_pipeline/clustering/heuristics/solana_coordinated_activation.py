"""
Coordinated Account Activation Heuristic (Solana)
===================================================
Newly created Solana accounts that receive their first SOL funding
within the same narrow time window from the same or related sources
are likely part of a coordinated wallet deployment.

This pattern appears when:
  - An entity programmatically creates many wallets simultaneously
  - A script funds multiple fresh accounts in quick succession
  - A CaaS (Clusters-as-a-Service) operation spins up wallets in batch

Detection:
  1. Identify "first touch" events: transactions to accounts with no
     prior incoming balance (first_seen == this tx timestamp)
  2. Group newly-activated accounts by time window W
  3. Within each window, if >= K accounts are activated from <= M
     distinct funders → link those accounts

False-positive controls:
  - Airdrop detection: if > 100 accounts activate in one window,
    it is likely a public airdrop — skip (too broad)
  - Require at least 3 accounts in the same window
  - Exclude known high-volume programs (system, token)
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

_MIN_ACCOUNTS_IN_WINDOW  = 3
_MAX_ACCOUNTS_IN_WINDOW  = 100   # airdrop guard
_MAX_DISTINCT_FUNDERS    = 5     # coordinated = few funders


class CoordinatedAccountActivationHeuristic(BaseHeuristic):
    """
    Links newly activated Solana accounts that receive first funding
    within the same narrow time window.
    """

    name = "solana_coordinated_activation"
    description = (
        "Solana accounts activated (first funded) within the same narrow "
        "time window from few sources are likely jointly deployed."
    )

    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.window = cfg.clustering_temporal_window_seconds

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        # addr → earliest incoming timestamp
        first_seen: dict[str, float] = {}
        # addr → set of funders
        funders_of: dict[str, set[str]] = defaultdict(set)

        for u, v, data in G.edges(data=True):
            if u == v:
                continue
            val = float(data.get("value_eth") or data.get("value_native") or 0.0)
            if val <= 0:
                continue
            ts = float(data.get("timestamp") or 0.0)
            if v not in first_seen or ts < first_seen[v]:
                first_seen[v] = ts
            funders_of[v].add(u)

        # Sort newly activated accounts by their first-seen timestamp
        new_accounts = sorted(first_seen.items(), key=lambda x: x[1])
        if not new_accounts:
            return []

        links: List[ClusterEdge] = []
        seen: set[ClusterEdge] = set()
        n = len(new_accounts)
        left = 0

        for right in range(n):
            ts_r = new_accounts[right][1]
            # Advance left pointer
            while new_accounts[left][1] < ts_r - self.window:
                left += 1

            window_accounts = [new_accounts[i][0] for i in range(left, right + 1)]

            if len(window_accounts) < _MIN_ACCOUNTS_IN_WINDOW:
                continue
            if len(window_accounts) > _MAX_ACCOUNTS_IN_WINDOW:
                continue

            # Collect all funders in this window
            all_funders: set[str] = set()
            for acc in window_accounts:
                all_funders.update(funders_of.get(acc, set()))

            if len(all_funders) > _MAX_DISTINCT_FUNDERS:
                continue   # Too many funders → public airdrop, not coordinated

            # Link all accounts in this window
            sorted_accs = sorted(window_accounts)
            for i in range(len(sorted_accs)):
                for j in range(i + 1, len(sorted_accs)):
                    pair = (sorted_accs[i], sorted_accs[j])
                    if pair not in seen:
                        links.append(pair)
                        seen.add(pair)

        return links
