"""
Common Fee Payer Heuristic (Solana)
=====================================
Every Solana transaction has exactly one fee payer — the account that
authorises and pays for transaction fees.

If two accounts are funded by the same fee payer across multiple
transactions, they are likely controlled by the same entity
(the fee payer holds the master wallet).

Evidence strength:
  - 1 shared fee payer:  weak  (could be an exchange or relayer)
  - 2+ shared transactions via same fee payer:  moderate
  - Same fee payer + overlapping programs:  strong

False-positive controls:
  - Fee payers that appear in >= 50 transactions are treated as
    "infrastructure" (relayers, dApps) and excluded.
  - Fee payer == from_address (self-paying) is excluded.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

_HIGH_FREQ_THRESHOLD = 50
_MIN_SHARED_TX       = 2


class CommonFeePayerHeuristic(BaseHeuristic):
    """
    Links accounts funded by the same fee payer across multiple transactions.

    Reads fee_payer from the input_method_id field (encoded as
    "feepayer|prog1|prog2" by the SolanaAdapter).
    """

    name = "solana_common_fee_payer"
    description = (
        "Solana accounts sharing the same fee payer across >= 2 transactions "
        "are likely controlled by the same entity."
    )

    def _parse_fee_payer(self, data: dict) -> str | None:
        """Extract fee_payer from input_method_id encoding."""
        mid = data.get("input_method_id") or data.get("method_id", "")
        if not mid or "|" not in mid:
            return None
        parts = mid.split("|")
        fp = parts[0].strip()
        return fp if fp else None

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        # fee_payer → list of from_addresses that used it
        payer_senders: dict[str, list[str]] = defaultdict(list)
        # Count how many times each fee_payer appears
        payer_freq: Counter[str] = Counter()

        for u, v, data in G.edges(data=True):
            if u == v:
                continue
            fee_payer = self._parse_fee_payer(data)
            if not fee_payer:
                continue
            if fee_payer == u:   # self-paying — not evidence of shared control
                continue
            payer_freq[fee_payer] += 1
            payer_senders[fee_payer].append(u)

        # Exclude high-frequency fee payers (infrastructure)
        high_freq = {fp for fp, cnt in payer_freq.items() if cnt >= _HIGH_FREQ_THRESHOLD}

        links: List[ClusterEdge] = []
        seen: set[ClusterEdge] = set()

        for fee_payer, senders in payer_senders.items():
            if fee_payer in high_freq:
                continue
            unique_senders = sorted(set(senders))
            if len(unique_senders) < 2:
                continue
            # Require minimum tx count evidence
            if payer_freq[fee_payer] < _MIN_SHARED_TX:
                continue
            for i in range(len(unique_senders)):
                for j in range(i + 1, len(unique_senders)):
                    pair = (unique_senders[i], unique_senders[j])
                    if pair not in seen:
                        links.append(pair)
                        seen.add(pair)

        return links
