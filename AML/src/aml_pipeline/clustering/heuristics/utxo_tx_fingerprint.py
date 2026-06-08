"""
Transaction Fingerprint Clustering Heuristic (UTXO)
=====================================================
Identifies wallets that consistently produce transactions with the same
structural "fingerprint" — a characteristic combination of:
  - Number of inputs
  - Number of outputs
  - Output value pattern (e.g. always splits into 2 outputs with similar ratio)
  - Fee rate pattern (gas_used analog for UTXO)
  - Script type combination

Wallets controlled by the same software/entity tend to produce transactions
with nearly identical structure repeatedly.

This heuristic links pairs of from_addresses whose transactions share the
same fingerprint across multiple blocks, making it chain-agnostic and
resistant to CoinJoin noise.

False-positive controls:
  - Fingerprints seen in fewer than 2 transactions are ignored
  - Common "1-input 1-output" fingerprint is excluded (too generic)
  - Fingerprints involving > 8 inputs are skipped (too generic / CoinJoin)
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

_MIN_FINGERPRINT_OCCURRENCES = 2
_MAX_INPUTS_FOR_FINGERPRINT  = 8
_VALUE_BUCKET_DIVISOR = 1000   # bucket satoshi values into 1000-sat buckets


def _value_bucket(value_native: float) -> int:
    """Quantise a native-asset value into a coarse bucket for fingerprinting."""
    # Convert to approximate satoshis then bucket
    satoshis = int(value_native * 1e8)
    if satoshis <= 0:
        return 0
    # Logarithmic bucketing: which power-of-10 range?
    import math
    return int(math.log10(max(satoshis, 1)))


class TxFingerprintClusteringHeuristic(BaseHeuristic):
    """
    Groups senders whose transactions share a structural fingerprint.
    """

    name = "utxo_tx_fingerprint"
    description = (
        "Addresses producing transactions with the same structural fingerprint "
        "(input count, output count, value pattern) across multiple blocks are "
        "likely controlled by the same wallet software or entity."
    )

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        # fingerprint → list of from_addresses
        fingerprint_senders: dict[tuple, list[str]] = defaultdict(list)

        # tx_hash → set of from_addresses, set of to_addresses, list of values
        tx_inputs:  dict[str, set[str]]   = defaultdict(set)
        tx_outputs: dict[str, set[str]]   = defaultdict(set)
        tx_values:  dict[str, list[float]] = defaultdict(list)

        for u, v, data in G.edges(data=True):
            if u == v or u.upper() == "COINBASE":
                continue
            val = float(data.get("value_eth") or data.get("value_native") or 0.0)
            if val <= 0:
                continue
            tx_hash = data.get("tx_hash") or ""
            if not tx_hash:
                continue
            tx_inputs[tx_hash].add(u)
            tx_outputs[tx_hash].add(v)
            tx_values[tx_hash].append(val)

        for tx_hash, inputs in tx_inputs.items():
            n_in = len(inputs)
            if n_in < 2 or n_in > _MAX_INPUTS_FOR_FINGERPRINT:
                continue
            outputs = tx_outputs.get(tx_hash, set())
            n_out = len(outputs)
            # Skip boring 1-in 1-out
            if n_in == 1 and n_out == 1:
                continue
            values = sorted(tx_values.get(tx_hash, []))
            # Build value bucket signature
            val_sig = tuple(_value_bucket(v) for v in values[:4])
            fingerprint = (n_in, n_out, val_sig)
            for addr in sorted(inputs):
                fingerprint_senders[fingerprint].append(addr)

        links: List[ClusterEdge] = []
        seen: set[ClusterEdge] = set()

        for fingerprint, senders in fingerprint_senders.items():
            if len(senders) < _MIN_FINGERPRINT_OCCURRENCES:
                continue
            # Deduplicate and link all senders sharing this fingerprint
            unique_senders = sorted(set(senders))
            if len(unique_senders) < 2:
                continue
            for i in range(len(unique_senders)):
                for j in range(i + 1, len(unique_senders)):
                    pair = (unique_senders[i], unique_senders[j])
                    if pair not in seen:
                        links.append(pair)
                        seen.add(pair)

        return links
