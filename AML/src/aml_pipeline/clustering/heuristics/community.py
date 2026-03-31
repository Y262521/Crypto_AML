"""
Community Detection Heuristic (Louvain-style)
===============================================
Community detection finds densely connected subgraphs — groups of addresses
that transact with each other far more than with the rest of the network.

This is a graph-level clustering technique that complements the
pair-wise heuristics. It catches clusters that no single heuristic
would find, but that are clearly "cliques" in the transaction graph.

Algorithm:
  We use NetworkX's greedy modularity communities (approximation of Louvain)
  on an undirected projection of the transaction graph.

  Modularity measures how much more densely connected a community is
  compared to a random graph with the same degree sequence.
  High modularity = strong community structure.

  Steps:
  1. Project the directed multigraph to an undirected weighted graph
     (edge weight = number of transactions between the pair)
  2. Run greedy modularity community detection
  3. For each community with >= MIN_COMMUNITY_SIZE members,
     link all pairs within the community

This catches:
  - Wash trading rings (dense mutual transactions)
  - Coordinated wallet clusters
  - DeFi protocol user clusters
  - Exchange sub-networks
"""

from __future__ import annotations

from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

_MIN_COMMUNITY_SIZE = 3
_MIN_INTERNAL_EDGES = 3   # community must have at least this many internal edges


class CommunityDetectionHeuristic(BaseHeuristic):
    name = "community_detection"
    description = (
        "Uses greedy modularity community detection to find densely connected "
        "address clusters — groups transacting with each other far more than "
        "with the rest of the network. Catches wash trading rings and "
        "coordinated wallet clusters."
    )

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        if G.number_of_nodes() < _MIN_COMMUNITY_SIZE:
            return []

        # Project to undirected weighted graph
        # Weight = number of transactions between the pair
        UG = nx.Graph()
        for u, v, data in G.edges(data=True):
            if u == v:
                continue
            if UG.has_edge(u, v):
                UG[u][v]["weight"] += 1
            else:
                UG.add_edge(u, v, weight=1)

        if UG.number_of_edges() == 0:
            return []

        # Run greedy modularity community detection
        try:
            from networkx.algorithms.community import greedy_modularity_communities
            communities = list(greedy_modularity_communities(UG, weight="weight"))
        except Exception:
            return []

        links: List[ClusterEdge] = []
        seen_pairs: set = set()

        for community in communities:
            members = list(community)
            if len(members) < _MIN_COMMUNITY_SIZE:
                continue

            # Count internal edges
            internal = sum(
                1 for i in range(len(members))
                for j in range(i + 1, len(members))
                if UG.has_edge(members[i], members[j])
            )
            if internal < _MIN_INTERNAL_EDGES:
                continue

            members.sort()
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    pair = (members[i], members[j])
                    if pair not in seen_pairs:
                        links.append(pair)
                        seen_pairs.add(pair)

        return links
