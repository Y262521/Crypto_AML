"""
Common Input Ownership Heuristic (UTXO)
========================================
The most fundamental UTXO clustering heuristic.

Rule: All addresses that appear as INPUTS to the same transaction are
controlled by the same entity, because a single private key (or
co-signing group) must have authorised all inputs simultaneously.

This is the "CIO" heuristic used in all major Bitcoin clustering papers
(Meiklejohn et al. 2013, Ron & Shamir 2013).

Exceptions / false-positive controls:
  - CoinJoin transactions (many inputs from many unrelated parties)
    are filtered out using structural heuristics:
      * Very large input count (>= 10) with equal output amounts → CoinJoin
      * Many distinct output amounts near the same value → CoinJoin
  - Coinbase inputs are excluded (no real sender)
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import List, Set

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

# Threshold above which a tx is suspected CoinJoin
_COINJOIN_INPUT_THRESHOLD = 10
# If output amounts are this similar as a fraction, suspect CoinJoin
_COINJOIN_EQUAL_OUTPUT_RATIO = 0.05


class CommonInputOwnershipHeuristic(BaseHeuristic):
    """
    Links all input addresses in the same UTXO transaction.

    Extended to handle multi-input transactions from the exploded
    input→output pair format: we recover original co-inputs by
    grouping pairs with the same tx_hash and linking their from_addresses.
    """

    name = "common_input_ownership"
    description = (
        "All input addresses in the same UTXO transaction are likely "
        "controlled by the same entity (CIO heuristic)."
    )

    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.max_inputs = int(
            getattr(cfg, "utxo_cio_max_inputs", _COINJOIN_INPUT_THRESHOLD)
        )

    def _is_suspected_coinjoin(
        self,
        inputs: Set[str],
        output_values: List[float],
    ) -> bool:
        """Heuristic CoinJoin detection — avoids false-positive clusters."""
        if len(inputs) >= self.max_inputs:
            return True
        if len(output_values) < 2:
            return False
        avg = sum(output_values) / len(output_values)
        if avg <= 0:
            return False
        # Check if outputs are suspiciously equal
        equal_count = sum(
            1 for v in output_values
            if abs(v - avg) / avg <= _COINJOIN_EQUAL_OUTPUT_RATIO
        )
        return equal_count >= len(output_values) * 0.7

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        """
        Recover co-inputs from the exploded pair graph.

        In the UTXO flat pair format each edge represents one input→output
        pair from the same transaction. Edges sharing a tx_hash came from
        the same original transaction, so their from_addresses were co-inputs.
        """
        # tx_hash → {from_addresses} and {value_eth of outputs}
        tx_inputs: dict[str, set[str]]   = defaultdict(set)
        tx_out_values: dict[str, list[float]] = defaultdict(list)

        for u, v, data in G.edges(data=True):
            if u == v:
                continue
            if u.upper() == "COINBASE":
                continue
            # Accept any positive value (UTXO threshold differs from EVM)
            val = float(data.get("value_eth") or data.get("value_native") or 0.0)
            if val <= 0:
                continue
            tx_hash = data.get("tx_hash") or data.get("key") or ""
            if not tx_hash:
                continue
            tx_inputs[tx_hash].add(u)
            tx_out_values[tx_hash].append(val)

        links: List[ClusterEdge] = []
        seen: set[ClusterEdge] = set()

        for tx_hash, inputs in tx_inputs.items():
            if len(inputs) < 2:
                continue
            out_vals = tx_out_values.get(tx_hash, [])
            if self._is_suspected_coinjoin(inputs, out_vals):
                continue
            inp_list = sorted(inputs)
            for i in range(len(inp_list)):
                for j in range(i + 1, len(inp_list)):
                    pair = (inp_list[i], inp_list[j])
                    if pair not in seen:
                        links.append(pair)
                        seen.add(pair)

        return links
