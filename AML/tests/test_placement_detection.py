from __future__ import annotations

from dataclasses import replace
import unittest

from aml_pipeline.analytics.placement import PlacementAnalysisEngine
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
        placement_funneling_min_in_degree=4,
        placement_funneling_min_in_out_ratio=2.0,
        placement_immediate_max_holding_seconds=600,
        placement_immediate_min_cycles=2,
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

    def test_funneling_detection_flags_high_in_degree_low_out_degree_entity(self) -> None:
        transactions = [
            _tx("f1", "u1", "hub", 0.6, 10),
            _tx("f1b", "u1", "peer_1", 0.2, 12),
            _tx("f2", "u2", "hub", 0.8, 200),
            _tx("f2b", "u2", "peer_2", 0.2, 22),
            _tx("f3", "u3", "hub", 1.0, 400),
            _tx("f3b", "u3", "peer_3", 0.2, 32),
            _tx("f4", "u4", "hub", 1.2, 600),
            _tx("f4b", "u4", "peer_4", 0.2, 42),
            _tx("f5", "hub", "cashout", 3.0, 50),
        ]
        engine = _PlacementEngineForTest(transactions)

        result = engine.run()

        behaviors = {(behavior.entity_id, behavior.behavior_type) for behavior in result.behaviors}
        self.assertIn(("hub", "funneling"), behaviors)

    def test_immediate_utilization_flags_fast_receive_to_send_cycles(self) -> None:
        transactions = [
            _tx("i1", "src1", "wallet", 1.0, 10),
            _tx("i2", "wallet", "sink1", 0.9, 70),
            _tx("i3", "src2", "wallet", 1.0, 120),
            _tx("i4", "wallet", "sink2", 0.9, 180),
        ]
        engine = _PlacementEngineForTest(transactions)

        result = engine.run()

        behaviors = {(behavior.entity_id, behavior.behavior_type) for behavior in result.behaviors}
        self.assertIn(("wallet", "immediate_utilization"), behaviors)

    def test_run_identifies_placement_origin_label_and_poi(self) -> None:
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
        self.assertTrue(result.pois)
        self.assertGreaterEqual(placement.confidence_score, 0.55)


if __name__ == "__main__":
    unittest.main()
