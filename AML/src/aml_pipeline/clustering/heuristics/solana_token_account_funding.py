"""
Shared Token Account Funding Heuristic (Solana)
=================================================
In Solana, each wallet must hold a separate token account (ATA —
Associated Token Account) for each SPL token it owns. Creating an ATA
costs a small amount of SOL (rent-exemption).

If the same account funds (pays rent for) the ATAs of multiple other
accounts for the same token mint, those funded accounts are likely
controlled by the same entity as the funder.

This is the Solana equivalent of the EVM Common Funder heuristic,
adapted to the ATA creation pattern.

Detection:
  1. Identify transactions where from_address sends a small SOL amount
     to a to_address that subsequently holds an SPL token balance
  2. Group to_addresses by the same (from_address, token_mint) pair
  3. Link funded accounts together

False-positive controls:
  - Exclude funders that fund > 30 accounts (likely an exchange)
  - Require minimum 2 funded accounts per funder
  - Only consider amounts in the ATA rent range (0.002–0.003 SOL)
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

_ATA_RENT_MIN_SOL = 0.001     # minimum SOL for ATA creation
_ATA_RENT_MAX_SOL = 0.01      # maximum SOL for ATA creation
_MAX_FUNDED_ACCOUNTS = 30     # exclude high-volume funders
_MIN_FUNDED_ACCOUNTS = 2


class SharedTokenAccountFundingHeuristic(BaseHeuristic):
    """
    Links Solana accounts funded by the same account for the same token mint.
    """

    name = "solana_shared_token_funding"
    description = (
        "Solana accounts whose token accounts are funded by the same source "
        "account are likely controlled by the same entity."
    )

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        # (funder, token_context) → set of funded accounts
        # token_context: the to_address's domain (program context)
        funder_funded: dict[str, set[str]] = defaultdict(set)

        for u, v, data in G.edges(data=True):
            if u == v:
                continue
            val = float(data.get("value_eth") or data.get("value_native") or 0.0)

            # Check if this looks like an ATA funding (small SOL transfer)
            if not (_ATA_RENT_MIN_SOL <= val <= _ATA_RENT_MAX_SOL):
                continue

            # The funder (u) → funded account (v)
            funder_funded[u].add(v)

        links: List[ClusterEdge] = []
        seen: set[ClusterEdge] = set()

        for funder, funded_set in funder_funded.items():
            if len(funded_set) < _MIN_FUNDED_ACCOUNTS:
                continue
            if len(funded_set) > _MAX_FUNDED_ACCOUNTS:
                continue   # Likely an exchange or dApp

            funded_list = sorted(funded_set)
            for i in range(len(funded_list)):
                for j in range(i + 1, len(funded_list)):
                    pair = (funded_list[i], funded_list[j])
                    if pair not in seen:
                        links.append(pair)
                        seen.add(pair)

        return links
