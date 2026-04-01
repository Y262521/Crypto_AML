"""Base class every heuristic must extend."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Tuple

import networkx as nx

from ...config import Config

# An edge in the union-find sense: (address_a, address_b)
ClusterEdge = Tuple[str, str]


class BaseHeuristic(ABC):
    """
    A heuristic analyses the transaction graph and returns pairs of addresses
    that should be merged into the same cluster.

    Subclasses implement `find_links` and declare `name` + `description`.
    """

    name: str = "base"
    description: str = ""

    def __init__(self, cfg: Config):
        self.cfg = cfg

    @abstractmethod
    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        """
        Return a list of (addr_a, addr_b) pairs that should be in the same cluster.
        Both addresses must already be nodes in G.
        """
