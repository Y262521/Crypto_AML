"""
Build a NetworkX directed graph from normalised transaction records.

Nodes  = Ethereum addresses
Edges  = individual transactions (directed: from → to)

Each edge carries:
  tx_hash, block_number, timestamp, value_eth,
  is_contract_call, gas_used, status
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import logging
from typing import Any, Iterable

import networkx as nx

from .base import TxRecord

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GraphArtifacts:
    """Graph plus adjacency indexes used by downstream analytics."""

    graph: nx.MultiDiGraph
    incoming_edges: dict[str, list[dict[str, Any]]]
    outgoing_edges: dict[str, list[dict[str, Any]]]


def build_graph(transactions: Iterable[TxRecord]) -> nx.DiGraph:
    """
    Consume an iterable of TxRecord and return a directed multigraph.

    Parallel edges (same sender/receiver, different tx) are preserved
    as separate edges keyed by tx_hash so heuristics can count them.
    """
    G = nx.MultiDiGraph()
    count = 0

    for tx in transactions:
        frm = tx.from_address
        to = tx.to_address

        if not frm or not to:
            continue

        if not G.has_node(frm):
            G.add_node(frm, blockchain="ethereum")
        if not G.has_node(to):
            G.add_node(to, blockchain="ethereum")

        G.add_edge(
            frm, to,
            key=tx.tx_hash,
            tx_hash=tx.tx_hash,
            block_number=tx.block_number,
            timestamp=tx.timestamp,
            value_eth=tx.value_eth,
            is_contract_call=tx.is_contract_call,
            gas_used=tx.gas_used,
            status=tx.status,
        )
        count += 1

    logger.info(
        "Graph built: %d nodes, %d edges from %d transactions",
        G.number_of_nodes(), G.number_of_edges(), count,
    )
    return G


def build_graph_artifacts(transactions: Iterable[TxRecord]) -> GraphArtifacts:
    """Build the graph and deterministic adjacency lists for each address."""

    graph = build_graph(transactions)
    incoming_edges: dict[str, list[dict[str, Any]]] = defaultdict(list)
    outgoing_edges: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for source, target, tx_hash, data in graph.edges(keys=True, data=True):
        edge = {
            "from_address": source,
            "to_address": target,
            "tx_hash": data.get("tx_hash") or tx_hash,
            "block_number": data.get("block_number"),
            "timestamp": data.get("timestamp"),
            "value_eth": float(data.get("value_eth") or 0.0),
            "is_contract_call": bool(data.get("is_contract_call")),
            "gas_used": data.get("gas_used"),
            "status": data.get("status"),
        }
        outgoing_edges[source].append(edge)
        incoming_edges[target].append(edge)

    def _edge_sort_key(edge: dict[str, Any]) -> tuple[float, str]:
        return (
            float(edge.get("timestamp") or 0.0),
            str(edge.get("tx_hash") or ""),
        )

    for edge_map in (incoming_edges, outgoing_edges):
        for edges in edge_map.values():
            edges.sort(key=_edge_sort_key)

    return GraphArtifacts(
        graph=graph,
        incoming_edges=dict(incoming_edges),
        outgoing_edges=dict(outgoing_edges),
    )
