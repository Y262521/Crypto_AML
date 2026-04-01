"""
Address Poisoning Heuristic
==============================
Address poisoning is an attack where a malicious actor sends a zero-value
(or near-zero) transaction FROM an address that looks visually similar to
a victim's frequent counterparty.

The goal: trick the victim into copying the wrong address from their
transaction history and sending funds to the attacker.

Visual similarity is based on:
  - Same first N characters (prefix match)
  - Same last M characters (suffix match)
  - Both prefix AND suffix match (strongest signal)

Detection:
  1. For each address in the graph, find all other addresses that share
     a prefix (first 6 chars) AND suffix (last 4 chars)
  2. If a near-zero value transaction exists between them, flag as
     address poisoning
  3. Link the poisoner and victim together for investigation

Note: This heuristic identifies BOTH the attacker and victim as a cluster
so analysts can investigate both sides.
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

# Characters to compare at start and end of address (after "0x")
_PREFIX_LEN = 6
_SUFFIX_LEN = 4
# Maximum ETH value for a poisoning transaction (near-zero)
_POISON_MAX_ETH = 0.0


class AddressPoisoningHeuristic(BaseHeuristic):
    name = "address_poisoning"
    description = (
        "Detects address poisoning attacks: malicious addresses visually "
        "similar to legitimate counterparties sending zero-value transactions "
        "to trick victims into sending funds to the wrong address."
    )

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        nodes = [n for n in G.nodes() if len(n) >= 10]

        # Build lookup: (prefix, suffix) → list of addresses
        prefix_suffix_map: dict[tuple, list] = defaultdict(list)
        for addr in nodes:
            clean = addr.lower().replace("0x", "")
            key = (clean[:_PREFIX_LEN], clean[-_SUFFIX_LEN:])
            prefix_suffix_map[key].append(addr)

        links: List[ClusterEdge] = []
        seen_pairs: set = set()

        for (prefix, suffix), similar_addrs in prefix_suffix_map.items():
            if len(similar_addrs) < 2:
                continue

            # Check if any of these similar addresses sent near-zero transactions
            for i in range(len(similar_addrs)):
                for j in range(i + 1, len(similar_addrs)):
                    a, b = similar_addrs[i], similar_addrs[j]
                    pair = tuple(sorted([a, b]))
                    if pair in seen_pairs:
                        continue

                    # Check for near-zero value edge between them or to common targets
                    poisoning_found = False
                    for u, v, data in G.edges(data=True):
                        val = data.get("value_eth", 0.0) or 0.0
                        if val <= _POISON_MAX_ETH and (u in (a, b) or v in (a, b)):
                            poisoning_found = True
                            break

                    if poisoning_found:
                        links.append(pair)  # type: ignore[arg-type]
                        seen_pairs.add(pair)

        return links
