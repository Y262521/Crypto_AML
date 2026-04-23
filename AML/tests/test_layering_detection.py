from __future__ import annotations

from dataclasses import replace
import unittest

from aml_pipeline.analytics.layering import LayeringAnalysisEngine
from aml_pipeline.analytics.layering.service_profiles import ServiceRegistry
from aml_pipeline.clustering.base import TxRecord
from aml_pipeline.config import load_config


def _cfg():
    base = load_config()
    return replace(
        base,
        clustering_min_heuristic_support=10,
        clustering_max_pattern_size=20,
        layering_min_seed_confidence=0.0,
        layering_peel_min_hops=3,
        layering_peel_max_hops=5,
        layering_peel_min_decay_ratio=0.01,
        layering_peel_min_fragment_ratio=0.05,
        layering_peel_max_fragment_ratio=0.25,
        layering_peel_max_time_gap_seconds=300,
        layering_mixing_min_interactions=2,
        layering_mixing_min_repeated_denominations=2,
        layering_mixing_max_time_gap_seconds=300,
        layering_mixing_min_ego_density=0.1,
        layering_bridge_amount_tolerance_ratio=0.03,
        layering_bridge_max_latency_seconds=300,
        layering_bridge_min_pairs=1,
        layering_shell_window_seconds=120,
        layering_shell_min_community_size=4,
        layering_shell_min_internal_ratio=0.7,
        layering_shell_min_density=0.2,
        layering_shell_min_temporal_windows=2,
        layering_depth_max_hops=5,
        layering_depth_min_hops=4,
        layering_depth_branching_limit=2,
        layering_depth_min_value_retention=0.7,
        layering_depth_max_latency_seconds=300,
        layering_depth_min_score=0.5,
    )


def _tx(
    tx_hash: str,
    source: str,
    target: str,
    value_eth: float,
    timestamp: float,
    method_id: str = "",
) -> TxRecord:
    return TxRecord(
        tx_hash=tx_hash,
        block_number=1,
        timestamp=timestamp,
        from_address=source,
        to_address=target,
        value_eth=value_eth,
        input_method_id=method_id,
        is_contract_call=bool(method_id),
        gas_used=21000,
        status=1,
    )


class _StubAdapter:
    def __init__(self, transactions: list[TxRecord]):
        self.transactions = transactions

    def iter_transactions(self, **_kwargs):
        yield from self.transactions


class _LayeringEngineForTest(LayeringAnalysisEngine):
    def __init__(
        self,
        transactions: list[TxRecord],
        cluster_map: dict[str, str] | None = None,
        service_registry: ServiceRegistry | None = None,
    ):
        super().__init__(cfg=_cfg(), service_registry=service_registry)
        self.clustering_engine.adapter = _StubAdapter(transactions)
        self._cluster_map = cluster_map or {}

    def _load_existing_cluster_map(self) -> dict[str, str]:
        return dict(self._cluster_map)


class LayeringDetectionTests(unittest.TestCase):
    def test_peeling_chain_detector_flags_repeated_shaved_transfers(self) -> None:
        transactions = [
            _tx("p1", "seed", "main_1", 9.0, 10),
            _tx("p2", "seed", "frag_1", 1.0, 11),
            _tx("p3", "main_1", "main_2", 8.0, 100),
            _tx("p4", "main_1", "frag_2", 1.0, 101),
            _tx("p5", "main_2", "main_3", 7.0, 200),
            _tx("p6", "main_2", "frag_3", 1.0, 201),
        ]
        engine = _LayeringEngineForTest(
            transactions,
            cluster_map={"seed": "SEED"},
            service_registry=ServiceRegistry({}, {}, {}),
        )

        result = engine.run(seed_entity_ids=["SEED"])

        detectors = {(hit.entity_id, hit.detector_type) for hit in result.detections}
        self.assertIn(("SEED", "peeling_chain"), detectors)

    def test_mixing_detector_requires_repeated_service_interactions(self) -> None:
        transactions = [
            _tx("m1", "seed", "mixer", 10.0, 10),
            _tx("m2", "seed", "mixer", 10.0, 40),
            _tx("m3", "mixer", "fresh_1", 9.9, 80),
            _tx("m4", "mixer", "fresh_2", 9.8, 120),
        ]
        service_registry = ServiceRegistry(
            address_categories={"mixer": {"mixer"}},
            method_categories={},
            keywords={},
        )
        engine = _LayeringEngineForTest(
            transactions,
            cluster_map={"seed": "SEED"},
            service_registry=service_registry,
        )

        result = engine.run(seed_entity_ids=["SEED"])

        detectors = {(hit.entity_id, hit.detector_type) for hit in result.detections}
        self.assertIn(("SEED", "mixing_interaction"), detectors)

    def test_bridge_detector_creates_bridge_pairs(self) -> None:
        transactions = [
            _tx("b1", "seed", "bridge", 5.0, 10),
            _tx("b2", "bridge", "fresh_dest", 4.95, 100),
        ]
        service_registry = ServiceRegistry(
            address_categories={"bridge": {"bridge"}},
            method_categories={},
            keywords={},
        )
        engine = _LayeringEngineForTest(
            transactions,
            cluster_map={"seed": "SEED"},
            service_registry=service_registry,
        )

        result = engine.run(seed_entity_ids=["SEED"])

        detectors = {(hit.entity_id, hit.detector_type) for hit in result.detections}
        self.assertIn(("SEED", "bridge_hopping"), detectors)
        self.assertEqual(len(result.bridge_pairs), 1)

    def test_shell_wallet_network_detector_requires_temporal_community_persistence(self) -> None:
        transactions = [
            _tx("s1", "seed", "w1", 1.0, 10),
            _tx("s2", "w1", "w2", 0.9, 20),
            _tx("s3", "w2", "w3", 0.85, 30),
            _tx("s4", "w3", "seed", 0.8, 40),
            _tx("s5", "seed", "w2", 0.75, 200),
            _tx("s6", "w2", "w1", 0.7, 210),
            _tx("s7", "w1", "w3", 0.65, 220),
            _tx("s8", "w3", "seed", 0.6, 230),
        ]
        engine = _LayeringEngineForTest(
            transactions,
            cluster_map={"seed": "SEED"},
            service_registry=ServiceRegistry({}, {}, {}),
        )

        result = engine.run(seed_entity_ids=["SEED"])

        detectors = {(hit.entity_id, hit.detector_type) for hit in result.detections}
        self.assertIn(("SEED", "shell_wallet_network"), detectors)

    def test_high_depth_detector_flags_consistent_forwarding_chain(self) -> None:
        transactions = [
            _tx("d1", "seed", "a1", 5.0, 10),
            _tx("d2", "a1", "a2", 4.5, 20),
            _tx("d3", "a2", "a3", 4.0, 30),
            _tx("d4", "a3", "a4", 3.7, 40),
        ]
        engine = _LayeringEngineForTest(
            transactions,
            cluster_map={"seed": "SEED"},
            service_registry=ServiceRegistry({}, {}, {}),
        )

        result = engine.run(seed_entity_ids=["SEED"])

        detectors = {(hit.entity_id, hit.detector_type) for hit in result.detections}
        self.assertIn(("SEED", "high_depth_transaction_chaining"), detectors)


if __name__ == "__main__":
    unittest.main()
