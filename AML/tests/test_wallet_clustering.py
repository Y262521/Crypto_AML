from __future__ import annotations

from dataclasses import replace
import unittest

import networkx as nx

from aml_pipeline.config import load_config
from aml_pipeline.clustering.engine import _compute_indicators
from aml_pipeline.clustering.heuristics.behavioral import BehavioralSimilarityHeuristic
from aml_pipeline.clustering.heuristics.cashout import CoordinatedCashoutHeuristic
from aml_pipeline.clustering.heuristics.common_funder import CommonFunderHeuristic
from aml_pipeline.clustering.heuristics.deposit_reuse import DepositAddressReuseHeuristic


def _cfg():
    base = load_config()
    return replace(
        base,
        clustering_min_shared_counterparties=3,
        clustering_cashout_window_seconds=300,
        clustering_pass_through_window_seconds=1800,
        clustering_amount_similarity_ratio=0.05,
        clustering_forwarding_value_tolerance_eth=0.01,
        clustering_max_pattern_size=20,
        clustering_min_transfer_value_eth=0.001,
    )


def _graph(edges: list[tuple[str, str, float, float]]) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    for index, (source, target, value_eth, timestamp) in enumerate(edges):
        graph.add_edge(
            source,
            target,
            key=f"tx-{index}",
            value_eth=value_eth,
            timestamp=timestamp,
            is_contract_call=False,
            gas_used=21000,
            status=1,
        )
    return graph


class WalletClusteringHeuristicTests(unittest.TestCase):
    def test_coordinated_cashout_links_similar_cashouts_to_same_sink(self) -> None:
        heuristic = CoordinatedCashoutHeuristic(_cfg())
        graph = _graph(
            [
                ("a1", "collector", 1.0000, 10),
                ("a2", "collector", 1.0200, 40),
                ("other", "collector", 4.0000, 500),
            ]
        )

        self.assertIn(("a1", "a2"), heuristic.find_links(graph))

    def test_common_funder_requires_shared_funder_and_shared_sink(self) -> None:
        heuristic = CommonFunderHeuristic(_cfg())
        graph = _graph(
            [
                ("treasury", "a1", 2.0, 10),
                ("treasury", "a2", 2.0, 11),
                ("a1", "sink", 1.0, 20),
                ("a2", "sink", 1.1, 21),
            ]
        )

        self.assertIn(("a1", "a2"), heuristic.find_links(graph))

    def test_deposit_reuse_links_sources_using_same_forwarding_address(self) -> None:
        heuristic = DepositAddressReuseHeuristic(_cfg())
        graph = _graph(
            [
                ("u1", "deposit", 1.0000, 10),
                ("deposit", "exchange", 0.9950, 20),
                ("u2", "deposit", 1.0050, 30),
                ("deposit", "exchange", 1.0000, 40),
            ]
        )

        self.assertIn(("u1", "u2"), heuristic.find_links(graph))

    def test_behavioral_similarity_allows_high_overlap_pairs_below_raw_shared_threshold(self) -> None:
        heuristic = BehavioralSimilarityHeuristic(_cfg())
        graph = _graph(
            [
                ("a1", "x", 1.0, 1),
                ("a1", "y", 1.0, 2),
                ("a2", "x", 1.0, 3),
                ("a2", "y", 1.0, 4),
            ]
        )

        self.assertIn(("a1", "a2"), heuristic.find_links(graph))

    def test_cluster_indicators_track_only_internal_member_flow(self) -> None:
        graph = _graph(
            [
                ("a1", "a2", 1.25, 10),
                ("a2", "external", 0.50, 20),
                ("external", "a1", 0.75, 30),
            ]
        )

        indicators = _compute_indicators(["a1", "a2"], graph, _cfg())

        self.assertEqual(indicators["internal_eth_volume"], 1.25)
        self.assertEqual(indicators["internal_tx_count"], 1)
        self.assertEqual(indicators["total_eth_volume"], 2.5)


if __name__ == "__main__":
    unittest.main()
