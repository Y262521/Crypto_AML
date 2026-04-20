from __future__ import annotations

from dataclasses import replace
import unittest

from aml_pipeline.analytics.placement import PlacementAnalysisEngine, _select_behavior_highlights
from aml_pipeline.clustering.base import TxRecord
from aml_pipeline.config import load_config


def _cfg():
    base = load_config()
    return replace(
        base,
        high_value_threshold_eth=1.0,
        clustering_min_heuristic_support=1,
        placement_structuring_window_minutes=30,
        placement_structuring_min_tx_count=4,
        placement_structuring_max_relative_variance=0.1,
        placement_smurfing_min_unique_senders=4,
        placement_smurfing_max_wallet_age_seconds=7200,
        placement_micro_max_tx_eth=0.1,
        placement_micro_min_tx_count=6,
        placement_micro_min_total_eth=0.4,
        placement_origin_max_hops=3,
        placement_origin_branching_limit=4,
        placement_origin_service_tx_count=100,
        placement_origin_service_degree=50,
    )


def _tx(tx_hash: str, source: str, target: str, value_eth: float, timestamp: float) -> TxRecord:
    return TxRecord(
        tx_hash=tx_hash,
        block_number=1,
        timestamp=timestamp,
        from_address=source,
        to_address=target,
        value_eth=value_eth,
        is_contract_call=False,
        gas_used=21000,
        status=1,
    )


class _StubAdapter:
    def __init__(self, transactions: list[TxRecord]):
        self.transactions = transactions

    def iter_transactions(self, **_kwargs):
        yield from self.transactions


class _PlacementEngineForTest(PlacementAnalysisEngine):
    def __init__(self, transactions: list[TxRecord], cluster_map: dict[str, str] | None = None):
        super().__init__(cfg=_cfg())
        self.clustering_engine.adapter = _StubAdapter(transactions)
        self._cluster_map = cluster_map or {}

    def _load_existing_cluster_map(self) -> dict[str, str]:
        return dict(self._cluster_map)


class PlacementDetectionTests(unittest.TestCase):
    def test_existing_clusters_are_enhanced_only_when_validation_finds_split_entities(self) -> None:
        transactions = [
            _tx("t1", "a1", "sink_a", 1.0, 10),
            _tx("t2", "a1", "sink_b", 1.0, 20),
            _tx("t3", "a2", "sink_a", 1.0, 30),
            _tx("t4", "a2", "sink_b", 1.0, 40),
        ]
        engine = _PlacementEngineForTest(
            transactions,
            cluster_map={
                "a1": "C-ONE",
                "a2": "C-TWO",
                "sink_a": "C-SINK-A",
                "sink_b": "C-SINK-B",
            },
        )

        result = engine.run()

        merged = next(
            entity
            for entity in result.entities
            if sorted(entity.addresses) == ["a1", "a2"]
        )
        self.assertEqual(merged.validation_status, "enhanced")
        self.assertEqual(merged.source_kind, "enhanced")
        self.assertGreaterEqual(merged.validation_confidence, 0.72)

    def test_structuring_detection_flags_low_variance_inflows(self) -> None:
        transactions = [
            _tx("s1", "fund_1", "collector", 0.49, 100),
            _tx("s2", "fund_2", "collector", 0.50, 160),
            _tx("s3", "fund_3", "collector", 0.51, 220),
            _tx("s4", "fund_4", "collector", 0.50, 280),
        ]
        engine = _PlacementEngineForTest(transactions)

        result = engine.run()

        behaviors = {(behavior.entity_id, behavior.behavior_type) for behavior in result.behaviors}
        self.assertIn(("collector", "structuring"), behaviors)

    def test_smurfing_detection_flags_many_unique_senders(self) -> None:
        transactions = [
            _tx("m1", "s1", "wallet", 0.4, 100),
            _tx("m2", "s2", "wallet", 0.4, 150),
            _tx("m3", "s3", "wallet", 0.4, 200),
            _tx("m4", "s4", "wallet", 0.4, 250),
        ]
        engine = _PlacementEngineForTest(transactions)

        result = engine.run()

        behaviors = {(behavior.entity_id, behavior.behavior_type) for behavior in result.behaviors}
        self.assertIn(("wallet", "smurfing"), behaviors)

    def test_micro_funding_detection_flags_accumulated_small_deposits(self) -> None:
        transactions = [
            _tx("micro1", "a1", "wallet", 0.07, 10),
            _tx("micro2", "a2", "wallet", 0.07, 20),
            _tx("micro3", "a3", "wallet", 0.07, 30),
            _tx("micro4", "a4", "wallet", 0.07, 40),
            _tx("micro5", "a5", "wallet", 0.07, 50),
            _tx("micro6", "a6", "wallet", 0.07, 60),
            _tx("micro7", "a7", "wallet", 0.07, 70),
            _tx("micro8", "a8", "wallet", 0.07, 80),
        ]
        engine = _PlacementEngineForTest(transactions)

        result = engine.run()

        behaviors = {(behavior.entity_id, behavior.behavior_type) for behavior in result.behaviors}
        self.assertIn(("wallet", "micro_funding"), behaviors)

    def test_behavior_highlight_selection_prefers_single_dominant_signal(self) -> None:
        highlighted, mode = _select_behavior_highlights(
            [
                {"behavior_type": "structuring", "confidence_score": 0.91},
                {"behavior_type": "smurfing", "confidence_score": 0.70},
                {"behavior_type": "micro_funding", "confidence_score": 0.66},
            ]
        )

        self.assertEqual(mode, "dominant")
        self.assertEqual([item["behavior_type"] for item in highlighted], ["structuring"])

    def test_behavior_highlight_selection_prefers_pair_when_third_trails(self) -> None:
        highlighted, mode = _select_behavior_highlights(
            [
                {"behavior_type": "smurfing", "confidence_score": 0.88},
                {"behavior_type": "structuring", "confidence_score": 0.84},
                {"behavior_type": "micro_funding", "confidence_score": 0.62},
            ]
        )

        self.assertEqual(mode, "paired")
        self.assertEqual(
            [item["behavior_type"] for item in highlighted],
            ["smurfing", "structuring"],
        )

    def test_behavior_highlight_selection_shows_all_when_scores_are_near_tied(self) -> None:
        highlighted, mode = _select_behavior_highlights(
            [
                {"behavior_type": "smurfing", "confidence_score": 0.91},
                {"behavior_type": "structuring", "confidence_score": 0.89},
                {"behavior_type": "micro_funding", "confidence_score": 0.86},
            ]
        )

        self.assertEqual(mode, "balanced")
        self.assertEqual(
            [item["behavior_type"] for item in highlighted],
            ["smurfing", "structuring", "micro_funding"],
        )

    def test_run_identifies_placement_origin_label_and_behavior_profile(self) -> None:
        transactions = [
            _tx("p1", "p1", "collector", 0.6, 10),
            _tx("p2", "p2", "collector", 0.6, 20),
            _tx("p3", "p3", "collector", 0.6, 30),
            _tx("p4", "p4", "collector", 0.6, 40),
            _tx("p5", "collector", "cashout", 2.2, 90),
        ]
        cluster_map = {
            "p1": "C-PLACEMENT",
            "p2": "C-PLACEMENT",
            "p3": "C-PLACEMENT",
            "p4": "C-PLACEMENT",
            "collector": "C-COLLECTOR",
            "cashout": "C-CASHOUT",
        }
        engine = _PlacementEngineForTest(transactions, cluster_map=cluster_map)

        result = engine.run()

        placement_ids = {placement.entity_id for placement in result.placements}
        self.assertIn("C-PLACEMENT", placement_ids)
        placement = next(placement for placement in result.placements if placement.entity_id == "C-PLACEMENT")
        self.assertIn("placement_origin", {label.label for label in result.labels if label.entity_id == "C-PLACEMENT"})
        behavior_profile = placement.metrics.get("behavior_profile", {})
        self.assertEqual(behavior_profile.get("primary_behavior"), "structuring")
        self.assertIn("display_behaviors", behavior_profile)
        self.assertNotIn("pois", result.summary)
        self.assertGreaterEqual(placement.confidence_score, 0.55)


if __name__ == "__main__":
    unittest.main()
