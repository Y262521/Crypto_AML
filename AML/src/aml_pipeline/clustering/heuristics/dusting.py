"""
Dusting Attack Heuristic
==========================
A dusting attack sends tiny amounts of cryptocurrency ("dust") to many
addresses. When those addresses later spend their funds (combining the
dust with other UTXOs or in ETH: sending from the same wallet), the
attacker can de-anonymize them by tracing the dust.

On Ethereum, dusting manifests as:
  - One address sending very small amounts (< DUST_THRESHOLD ETH) to
    many different addresses in a short time window
  - The receiving addresses are then linked because they all received
    dust from the same source

Detection:
  1. Find addresses that send many tiny transactions (dust sender)
  2. All recipients of dust from the same sender are linked together
     (they are likely being tracked by the same attacker)
  3. Also link the dust sender itself to its victims (for investigation)
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

# Maximum ETH value to be considered "dust"
_DUST_THRESHOLD_ETH = 0.001
# Minimum number of dust recipients to flag a sender as a dust attacker
_MIN_DUST_RECIPIENTS = 5


class DustingAttackHeuristic(BaseHeuristic):
    name = "dusting_attack"
    description = (
        "Detects dusting attacks: one address sending tiny amounts to many "
        "addresses to de-anonymize them. All dust recipients are linked "
        "as targets of the same surveillance campaign."
    )

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        # Find dust senders: addresses sending many tiny-value transactions
        dust_recipients: dict[str, set] = defaultdict(set)

        for u, v, data in G.edges(data=True):
            val = data.get("value_eth", 0.0) or 0.0
            if 0 < val <= _DUST_THRESHOLD_ETH:
                dust_recipients[u].add(v)

        links: List[ClusterEdge] = []
        seen_pairs: set = set()

        for sender, recipients in dust_recipients.items():
            if len(recipients) < _MIN_DUST_RECIPIENTS:
                continue

            # Link all recipients together (they are all being tracked)
            recipient_list = sorted(recipients)
            for i in range(len(recipient_list)):
                for j in range(i + 1, len(recipient_list)):
                    pair = (recipient_list[i], recipient_list[j])
                    if pair not in seen_pairs:
                        links.append(pair)
                        seen_pairs.add(pair)

        return links
