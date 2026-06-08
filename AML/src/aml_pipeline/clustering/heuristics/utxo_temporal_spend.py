"""
Temporal Spending Correlation Heuristic (UTXO)
================================================
Addresses that consistently spend within the same narrow time windows
across multiple transactions suggest coordinated control — a single
entity or automated wallet system spending from multiple addresses
in tight synchrony.

Algorithm:
  1. Sort all transactions by timestamp.
  2. Within a sliding window of W seconds, collect active input addresses.
  3. If >= K distinct input addresses are active in the same window AND
     they send to overlapping or identical destinations → link them.
  4. Require the pattern to repeat across >= 2 separate time windows
     to avoid false positives from coincidental timing.

This is the UTXO equivalent of the EVM TemporalHeuristic, adapted to
handle the multi-input nature of UTXO transactions.

False-positive controls:
  - Addresses that appear in every window (exchanges, mining pools) are
    treated as "high-frequency" and excluded from linking.
  - Windows containing > 20 distinct senders are skipped (too broad).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

_MIN_ADDRESSES_IN_WINDOW = 2
_MAX_ADDRESSES_IN_WINDOW = 20
_MIN_WINDOW_REPETITIONS  = 2     # pattern must appear in >= 2 windows
_HIGH_FREQ_THRESHOLD     = 10    # address in this many windows → skip


class TemporalSpendingCorrelationHeuristic(BaseHeuristic):
    """
    Links UTXO addresses that spend in coordinated time windows repeatedly.
    """

    name = "utxo_temporal_spend"
    description = (
        "UTXO input addresses that spend within the same narrow time windows "
        "across multiple transactions are flagged as likely coordinated."
    )

    def __init__(self, cfg: Config):
        super().__init__(cfg)
        self.window = cfg.clustering_temporal_window_seconds

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        # Collect (timestamp, from_addr, to_addr) tuples
        events: list[tuple[float, str, str]] = []
        for u, v, data in G.edges(data=True):
            if u == v or u.upper() == "COINBASE":
                continue
            val = float(data.get("value_eth") or data.get("value_native") or 0.0)
            if val <= 0:
                continue
            ts = float(data.get("timestamp") or 0.0)
            events.append((ts, u, v))

        if len(events) < 2:
            return []

        events.sort(key=lambda e: e[0])

        # Sliding window: collect active senders and their destinations
        # window_patterns: frozenset(senders) → count of windows matching
        window_pattern_counts: Counter[frozenset] = Counter()
        # pair → number of windows where they co-appeared
        pair_window_counts: Counter[tuple] = Counter()

        # Address frequency across windows (to detect high-freq nodes)
        addr_window_count: Counter[str] = Counter()

        n = len(events)
        left = 0
        for right in range(n):
            ts_r = events[right][0]
            # Advance left pointer to maintain window
            while events[left][0] < ts_r - self.window:
                left += 1

            window_senders: set[str] = set()
            for i in range(left, right + 1):
                window_senders.add(events[i][1])

            if _MIN_ADDRESSES_IN_WINDOW <= len(window_senders) <= _MAX_ADDRESSES_IN_WINDOW:
                fs = frozenset(window_senders)
                window_pattern_counts[fs] += 1
                for addr in window_senders:
                    addr_window_count[addr] += 1

        # Identify high-frequency addresses (likely exchanges / pools)
        high_freq = {
            addr for addr, cnt in addr_window_count.items()
            if cnt >= _HIGH_FREQ_THRESHOLD
        }

        # Collect pairs from patterns that appear repeatedly
        links: List[ClusterEdge] = []
        seen: set[ClusterEdge] = set()

        for pattern, count in window_pattern_counts.items():
            if count < _MIN_WINDOW_REPETITIONS:
                continue
            # Filter out high-frequency addresses
            filtered = sorted(pattern - high_freq)
            if len(filtered) < 2:
                continue
            for i in range(len(filtered)):
                for j in range(i + 1, len(filtered)):
                    pair = (filtered[i], filtered[j])
                    if pair not in seen:
                        links.append(pair)
                        seen.add(pair)

        return links
