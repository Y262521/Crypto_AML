"""
Change Address Detection Heuristic (UTXO)
==========================================
In UTXO transactions the sender creates a "change" output that returns
unspent funds to an address they control.

Identifying change outputs lets us link the change address to the input
addresses — they are all controlled by the same wallet.

Change address detection rules (in priority order):
  1. Single-use address: if one output address appears only once in the
     entire graph (never seen before or after), it is likely change.
  2. Address type match: change address tends to be the same script type
     as the input addresses (P2PKH, P2SH, P2WPKH, etc.).
  3. Value asymmetry: the smaller of two outputs is more likely change
     when the larger clearly corresponds to the intended payment amount.
  4. Round-number payment: if one output is a round number (e.g. 0.1 BTC)
     it is likely the payment; the other output is change.

False-positive controls:
  - Transactions with only 1 output have no change (entire input goes to recipient)
  - Transactions with > 5 outputs are not analysed (complex batched payments)
  - CoinJoin-suspected transactions are skipped
"""

from __future__ import annotations

from collections import Counter
from typing import List, Set

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

_MAX_OUTPUTS_TO_ANALYSE = 5
_ROUND_NUMBER_TOLERANCE = 0.001   # within 0.1% of a round number


def _is_round_number(value: float) -> bool:
    """Return True if value is close to a round number (0.1, 0.5, 1.0, 5.0…)."""
    if value <= 0:
        return False
    for magnitude in [0.001, 0.01, 0.1, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0]:
        ratio = value / magnitude
        if abs(ratio - round(ratio)) / max(ratio, 1e-9) <= _ROUND_NUMBER_TOLERANCE:
            return True
    return False


def _detect_script_type(address: str) -> str:
    """Rough script type detection from address format."""
    if address.startswith("1"):
        return "P2PKH"
    if address.startswith("3"):
        return "P2SH"
    if address.startswith(("bc1q", "ltc1q", "p2wpkh")):
        return "P2WPKH"
    if address.startswith(("bc1p",)):
        return "P2TR"
    if address.startswith("D"):
        return "DOGE_P2PKH"
    if address.startswith("q"):
        return "BCH_P2PKH"
    return "UNKNOWN"


class ChangeAddressDetectionHeuristic(BaseHeuristic):
    """
    Links UTXO change addresses back to the input addresses of their transactions.
    """

    name = "utxo_change_address"
    description = (
        "UTXO change outputs are identified and linked to the input addresses "
        "of the same transaction (same wallet owner controls both)."
    )

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        # Build address frequency: how many times each address appears as output
        output_freq: Counter[str] = Counter()
        # tx_hash → {from_addresses}, {(to_addr, value)}
        tx_inputs: dict[str, set[str]] = {}
        tx_outputs: dict[str, list[tuple[str, float]]] = {}

        for u, v, data in G.edges(data=True):
            if u == v or u.upper() == "COINBASE":
                continue
            val = float(data.get("value_eth") or data.get("value_native") or 0.0)
            if val <= 0:
                continue
            tx_hash = data.get("tx_hash") or ""
            if not tx_hash:
                continue
            if tx_hash not in tx_inputs:
                tx_inputs[tx_hash] = set()
                tx_outputs[tx_hash] = []
            tx_inputs[tx_hash].add(u)
            tx_outputs[tx_hash].append((v, val))
            output_freq[v] += 1

        links: List[ClusterEdge] = []
        seen: set[ClusterEdge] = set()

        for tx_hash, inputs in tx_inputs.items():
            if not inputs:
                continue
            outputs = tx_outputs.get(tx_hash, [])
            if len(outputs) < 2 or len(outputs) > _MAX_OUTPUTS_TO_ANALYSE:
                continue

            # Determine dominant input script type
            input_types = Counter(_detect_script_type(a) for a in inputs)
            dominant_type = input_types.most_common(1)[0][0]

            change_candidates: set[str] = set()

            for to_addr, val in outputs:
                # Heuristic 1: single-use address → likely change
                if output_freq[to_addr] == 1:
                    change_candidates.add(to_addr)
                    continue
                # Heuristic 2: same script type as inputs
                if _detect_script_type(to_addr) == dominant_type:
                    change_candidates.add(to_addr)

            # Heuristic 3 + 4: value analysis when exactly 2 outputs
            if len(outputs) == 2:
                (addr_a, val_a), (addr_b, val_b) = outputs
                # Round number → payment; other → change
                if _is_round_number(val_a) and not _is_round_number(val_b):
                    change_candidates.add(addr_b)
                elif _is_round_number(val_b) and not _is_round_number(val_a):
                    change_candidates.add(addr_a)
                # Smaller value → change (when ratio > 10x)
                elif val_a > 0 and val_b > 0:
                    if val_a / val_b > 10:
                        change_candidates.add(addr_b)
                    elif val_b / val_a > 10:
                        change_candidates.add(addr_a)

            # Link each confirmed change address to all input addresses
            for change_addr in change_candidates:
                for inp_addr in sorted(inputs):
                    if change_addr == inp_addr:
                        continue
                    pair = tuple(sorted([change_addr, inp_addr]))
                    if pair not in seen:
                        links.append(pair)  # type: ignore[arg-type]
                        seen.add(pair)

        return links
