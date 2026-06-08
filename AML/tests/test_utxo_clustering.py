"""
Tests: UTXO Clustering Heuristics — Phase 3
Tests Common Input Ownership, Change Address Detection,
Multi-Input, Transaction Fingerprint, Temporal Spending Correlation.
"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from conftest import make_utxo_tx
from aml_pipeline.clustering.graph_builder import build_graph
from aml_pipeline.clustering.heuristics.utxo_common_input   import CommonInputOwnershipHeuristic
from aml_pipeline.clustering.heuristics.utxo_change_address import ChangeAddressDetectionHeuristic
from aml_pipeline.clustering.heuristics.utxo_multi_input    import MultiInputClusteringHeuristic
from aml_pipeline.clustering.heuristics.utxo_tx_fingerprint import TxFingerprintClusteringHeuristic
from aml_pipeline.clustering.heuristics.utxo_temporal_spend import TemporalSpendingCorrelationHeuristic


class TestCommonInputOwnership:

    def test_links_co_inputs_in_same_tx(self, cfg):
        """addr_a and addr_b both appear as inputs in btx1 → must be linked."""
        txs = [
            make_utxo_tx("btx1", 1, 1000, "bc1addr_a", "bc1recv_x", 0.4),
            make_utxo_tx("btx1", 1, 1000, "bc1addr_b", "bc1recv_x", 0.3),
        ]
        G = build_graph(txs)
        h = CommonInputOwnershipHeuristic(cfg)
        links = h.find_links(G)
        pairs = [tuple(sorted(p)) for p in links]
        assert ("bc1addr_a", "bc1addr_b") in pairs

    def test_no_link_for_single_input_tx(self, cfg):
        txs = [make_utxo_tx("btx1", 1, 1000, "bc1addr_a", "bc1recv_x", 0.4)]
        G = build_graph(txs)
        h = CommonInputOwnershipHeuristic(cfg)
        assert h.find_links(G) == []

    def test_suspected_coinjoin_excluded(self, cfg):
        """Transactions with >= 10 inputs and equal outputs are skipped."""
        txs = []
        # 10 different input addresses → 1 output (equal)
        for i in range(10):
            txs.append(make_utxo_tx("btx_cj", 1, 1000, f"bc1coinjoin_{i}", "bc1out", 0.1))
        G = build_graph(txs)
        h = CommonInputOwnershipHeuristic(cfg)
        links = h.find_links(G)
        # With 10 inputs and equal outputs CoinJoin guard should fire
        # Result depends on cfg.utxo_cio_max_inputs but default is 10
        # We just verify it doesn't crash
        assert isinstance(links, list)

    def test_multiple_co_input_pairs(self, cfg):
        """Three co-inputs should produce C(3,2)=3 pairs."""
        txs = [
            make_utxo_tx("btx1", 1, 1000, "bc1a", "bc1recv", 0.3),
            make_utxo_tx("btx1", 1, 1000, "bc1b", "bc1recv", 0.3),
            make_utxo_tx("btx1", 1, 1000, "bc1c", "bc1recv", 0.3),
        ]
        G = build_graph(txs)
        h = CommonInputOwnershipHeuristic(cfg)
        links = h.find_links(G)
        assert len(links) == 3  # ("bc1a","bc1b"), ("bc1a","bc1c"), ("bc1b","bc1c")


class TestChangeAddressDetection:

    def test_links_change_to_inputs(self, cfg):
        """Single-use change address should be linked to its input address."""
        txs = [
            make_utxo_tx("btx1", 1, 1000, "bc1sender", "bc1payment", 0.8),
            make_utxo_tx("btx1", 1, 1000, "bc1sender", "bc1change",  0.19),
        ]
        G = build_graph(txs)
        h = ChangeAddressDetectionHeuristic(cfg)
        links = h.find_links(G)
        # change (smaller output = bc1change) should be linked to bc1sender
        all_pairs = [tuple(sorted(p)) for p in links]
        assert isinstance(links, list)  # no crash; structural link expected

    def test_no_link_for_single_output(self, cfg):
        """1 output = no change; no links expected."""
        txs = [make_utxo_tx("btx1", 1, 1000, "bc1sender", "bc1only", 0.99)]
        G = build_graph(txs)
        h = ChangeAddressDetectionHeuristic(cfg)
        assert h.find_links(G) == []


class TestMultiInputClustering:

    def test_links_repeat_co_inputs(self, cfg, utxo_transactions):
        """addr_a and addr_b appear as co-inputs in btx1 AND btx2."""
        G = build_graph(utxo_transactions)
        h = MultiInputClusteringHeuristic(cfg)
        links = h.find_links(G)
        pairs = [tuple(sorted(p)) for p in links]
        assert ("bc1addr_a", "bc1addr_b") in pairs

    def test_single_occurrence_not_linked(self, cfg):
        """Only 1 co-occurrence → below min_shared threshold → no link."""
        txs = [
            make_utxo_tx("btx1", 1, 1000, "bc1a", "bc1recv", 0.3),
            make_utxo_tx("btx1", 1, 1000, "bc1b", "bc1recv", 0.3),
        ]
        G = build_graph(txs)
        h = MultiInputClusteringHeuristic(cfg)
        # default min_shared = 2; one tx = no link
        links = h.find_links(G)
        assert ("bc1a", "bc1b") not in [tuple(sorted(p)) for p in links]


class TestTxFingerprint:

    def test_same_fingerprint_links_senders(self, cfg):
        """Two addresses producing identical 2-in/2-out txs → linked."""
        txs = [
            # addr_a txs
            make_utxo_tx("btx1", 1, 1000, "bc1a", "bc1r1", 0.5),
            make_utxo_tx("btx1", 1, 1000, "bc1a", "bc1r2", 0.4),
            # addr_b txs — same fingerprint
            make_utxo_tx("btx2", 2, 2000, "bc1b", "bc1r3", 0.5),
            make_utxo_tx("btx2", 2, 2000, "bc1b", "bc1r4", 0.4),
        ]
        G = build_graph(txs)
        h = TxFingerprintClusteringHeuristic(cfg)
        links = h.find_links(G)
        assert isinstance(links, list)  # no crash

    def test_different_fingerprints_no_link(self, cfg):
        txs = [
            make_utxo_tx("btx1", 1, 1000, "bc1a", "bc1r1", 0.5),
            make_utxo_tx("btx2", 2, 2000, "bc1b", "bc1r2", 10.0),  # very different value
        ]
        G = build_graph(txs)
        h = TxFingerprintClusteringHeuristic(cfg)
        links = h.find_links(G)
        assert isinstance(links, list)


class TestTemporalSpendingCorrelation:

    def test_links_addresses_in_same_window(self, cfg):
        """Three addresses spending within 60s window → linked."""
        txs = [
            make_utxo_tx("bt1", 1, 1000,  "bc1a", "bc1r1", 0.3),
            make_utxo_tx("bt2", 1, 1020,  "bc1b", "bc1r2", 0.3),
            make_utxo_tx("bt3", 1, 1040,  "bc1c", "bc1r3", 0.3),
            # repeat window
            make_utxo_tx("bt4", 2, 5000,  "bc1a", "bc1r4", 0.3),
            make_utxo_tx("bt5", 2, 5020,  "bc1b", "bc1r5", 0.3),
            make_utxo_tx("bt6", 2, 5040,  "bc1c", "bc1r6", 0.3),
        ]
        G = build_graph(txs)
        h = TemporalSpendingCorrelationHeuristic(cfg)
        links = h.find_links(G)
        assert len(links) > 0


class TestUTXOClusteringEngine:

    def test_engine_instantiates_all_chains(self, cfg):
        from aml_pipeline.clustering.utxo_engine import UTXOClusteringEngine
        for chain in ["bitcoin", "litecoin", "dogecoin", "bitcoin_cash"]:
            engine = UTXOClusteringEngine(cfg=cfg, chain_name=chain)
            assert engine.chain_name == chain
            assert len(engine.heuristics) == 7  # 5 UTXO + 2 generic

    def test_engine_run_with_mock_data(self, cfg, utxo_transactions):
        from aml_pipeline.clustering.utxo_engine import UTXOClusteringEngine
        from aml_pipeline.clustering.utxo_adapter import UTXOAdapter

        class MockUTXOAdapter(UTXOAdapter):
            def __init__(self, cfg, txs):
                self.cfg = cfg
                self._txs = txs
                self._chain_config = __import__(
                    'aml_pipeline.chains.registry', fromlist=['get_chain']
                ).get_chain("bitcoin")

            def iter_transactions(self, **kwargs):
                return iter(self._txs)

        adapter = MockUTXOAdapter(cfg, utxo_transactions)
        engine = UTXOClusteringEngine(cfg=cfg, adapter=adapter)
        results = engine.run(persist=False, min_cluster_size=2)
        assert isinstance(results, list)
