"""
Build a NetworkX directed graph from normalised transaction records.

Nodes  = Ethereum addresses
Edges  = individual transactions (directed: from → to)

Each edge carries:
  tx_hash, block_number, timestamp, value_eth,
  is_contract_call, gas_used, status
"""

from __future__ import annotations

import logging
from typing import Iterable

import networkx as nx

from .base import TxRecord

logger = logging.getLogger(__name__)


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
