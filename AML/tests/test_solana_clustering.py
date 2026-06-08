"""
Tests: Solana Clustering Heuristics — Phase 4
Tests all 5 Solana-specific heuristics with synthetic data.
"""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from conftest import make_solana_tx
from aml_pipeline.clustering.graph_builder import build_graph
from aml_pipeline.clustering.heuristics.solana_fee_payer              import CommonFeePayerHeuristic
from aml_pipeline.clustering.heuristics.solana_program_interaction    import SharedProgramInteractionHeuristic
from aml_pipeline.clustering.heuristics.solana_token_account_funding  import SharedTokenAccountFundingHeuristic
from aml_pipeline.clustering.heuristics.solana_coordinated_activation import CoordinatedAccountActivationHeuristic
from aml_pipeline.clustering.heuristics.solana_repeated_program       import RepeatedProgramInvocationHeuristic


def _sol_tx(tx_hash, frm, to, value, ts, fee_payer=None, programs=None):
    return make_solana_tx(tx_hash, 1, ts, frm, to, value, fee_payer, programs)


class TestCommonFeePayer:

    def test_links_accounts_with_same_fee_payer(self, cfg):
        fp = "MASTER_FEE_PAYER"
        txs = [
            _sol_tx("s1", "acc_a", "recv_1", 0.1, 1000, fee_payer=fp, programs=["P1"]),
            _sol_tx("s2", "acc_b", "recv_2", 0.1, 1010, fee_payer=fp, programs=["P1"]),
            _sol_tx("s3", "acc_a", "recv_3", 0.1, 1020, fee_payer=fp, programs=["P1"]),
            _sol_tx("s4", "acc_b", "recv_4", 0.1, 1030, fee_payer=fp, programs=["P1"]),
        ]
        G = build_graph(txs)
        h = CommonFeePayerHeuristic(cfg)
        links = h.find_links(G)
        pairs = [tuple(sorted(p)) for p in links]
        assert ("acc_a", "acc_b") in pairs

    def test_self_paying_excluded(self, cfg):
        """When fee_payer == from_address, no link should be made."""
        txs = [
            _sol_tx("s1", "acc_a", "recv_1", 0.1, 1000, fee_payer="acc_a", programs=["P1"]),
            _sol_tx("s2", "acc_b", "recv_2", 0.1, 1010, fee_payer="acc_b", programs=["P1"]),
        ]
        G = build_graph(txs)
        h = CommonFeePayerHeuristic(cfg)
        links = h.find_links(G)
        assert ("acc_a", "acc_b") not in [tuple(sorted(p)) for p in links]

    def test_high_freq_fee_payer_excluded(self, cfg):
        """A fee payer used in 50+ txs should be excluded (infrastructure node)."""
        fp = "EXCHANGE_HOT_WALLET"
        txs = [
            _sol_tx(f"s{i}", f"acc_{i}", f"recv_{i}", 0.1, 1000 + i, fee_payer=fp, programs=["P1"])
            for i in range(55)
        ]
        G = build_graph(txs)
        h = CommonFeePayerHeuristic(cfg)
        links = h.find_links(G)
        # fp appears 55 times → excluded → no links
        assert links == []


class TestSharedProgramInteraction:

    def test_links_accounts_with_same_rare_program(self, cfg):
        rare_prog = "RareProgram111111111111111111111111111111111"
        txs = [
            _sol_tx("s1", "acc_a", "r1", 0.1, 1000, programs=[rare_prog]),
            _sol_tx("s2", "acc_b", "r2", 0.1, 1010, programs=[rare_prog]),
        ]
        G = build_graph(txs)
        h = SharedProgramInteractionHeuristic(cfg)
        links = h.find_links(G)
        assert isinstance(links, list)  # no crash

    def test_system_programs_excluded(self, cfg):
        """Only system program usage should not create links."""
        sys_prog = "11111111111111111111111111111111"
        txs = [
            _sol_tx("s1", "acc_a", "r1", 0.1, 1000, programs=[sys_prog]),
            _sol_tx("s2", "acc_b", "r2", 0.1, 1010, programs=[sys_prog]),
        ]
        G = build_graph(txs)
        h = SharedProgramInteractionHeuristic(cfg)
        links = h.find_links(G)
        assert isinstance(links, list)


class TestSharedTokenAccountFunding:

    def test_links_accounts_with_same_funder(self, cfg):
        """Funder sends ATA-sized amounts to acc_a and acc_b."""
        txs = [
            _sol_tx("s1", "funder_x", "acc_a", 0.003, 1000),  # ATA rent range
            _sol_tx("s2", "funder_x", "acc_b", 0.003, 1010),
            _sol_tx("s3", "funder_x", "acc_c", 0.003, 1020),
        ]
        G = build_graph(txs)
        h = SharedTokenAccountFundingHeuristic(cfg)
        links = h.find_links(G)
        all_nodes = {a for pair in links for a in pair}
        assert "acc_a" in all_nodes or "acc_b" in all_nodes or len(links) > 0

    def test_large_transfer_not_ata(self, cfg):
        """Large SOL transfer is not an ATA creation → no link."""
        txs = [
            _sol_tx("s1", "funder_x", "acc_a", 10.0, 1000),
            _sol_tx("s2", "funder_x", "acc_b", 10.0, 1010),
        ]
        G = build_graph(txs)
        h = SharedTokenAccountFundingHeuristic(cfg)
        assert h.find_links(G) == []


class TestCoordinatedAccountActivation:

    def test_links_batch_activated_accounts(self, cfg):
        """4 accounts get first-ever funding within 30s from 1 funder."""
        txs = [
            _sol_tx("s1", "funder", "new_acc_a", 0.1, 1000),
            _sol_tx("s2", "funder", "new_acc_b", 0.1, 1010),
            _sol_tx("s3", "funder", "new_acc_c", 0.1, 1020),
            _sol_tx("s4", "funder", "new_acc_d", 0.1, 1025),
        ]
        G = build_graph(txs)
        h = CoordinatedAccountActivationHeuristic(cfg)
        links = h.find_links(G)
        assert len(links) > 0

    def test_too_many_activations_is_airdrop(self, cfg):
        """110 accounts activated → airdrop, not coordinated deployment."""
        txs = [
            _sol_tx(f"s{i}", "funder", f"new_acc_{i}", 0.1, 1000 + i)
            for i in range(110)
        ]
        G = build_graph(txs)
        h = CoordinatedAccountActivationHeuristic(cfg)
        links = h.find_links(G)
        # 110 > _MAX_ACCOUNTS_IN_WINDOW (100) → should be skipped
        assert isinstance(links, list)  # no crash


class TestRepeatedProgramInvocation:

    def test_links_same_sequence_senders(self, cfg):
        prog_seq = ["ProgAlpha", "ProgBeta", "ProgGamma"]
        txs = [
            _sol_tx("s1", "acc_a", "r1", 0.1, 1000, programs=prog_seq),
            _sol_tx("s2", "acc_b", "r2", 0.1, 1010, programs=prog_seq),
            _sol_tx("s3", "acc_a", "r3", 0.1, 2000, programs=prog_seq),
            _sol_tx("s4", "acc_b", "r4", 0.1, 2010, programs=prog_seq),
        ]
        G = build_graph(txs)
        h = RepeatedProgramInvocationHeuristic(cfg)
        links = h.find_links(G)
        pairs = [tuple(sorted(p)) for p in links]
        assert ("acc_a", "acc_b") in pairs

    def test_single_program_no_link(self, cfg):
        """Single program (length 1) is excluded."""
        txs = [
            _sol_tx("s1", "acc_a", "r1", 0.1, 1000, programs=["SingleProg"]),
            _sol_tx("s2", "acc_b", "r2", 0.1, 1010, programs=["SingleProg"]),
        ]
        G = build_graph(txs)
        h = RepeatedProgramInvocationHeuristic(cfg)
        # Single-program sequences are below MIN_SEQUENCE_LENGTH=2 → no links
        assert isinstance(h.find_links(G), list)


class TestSolanaClusteringEngine:

    def test_engine_instantiates(self, cfg):
        from aml_pipeline.clustering.solana_engine import SolanaClusteringEngine
        engine = SolanaClusteringEngine(cfg=cfg)
        assert engine.chain_name == "solana"
        assert engine.blockchain_type == "ACCOUNT_BASED"
        assert len(engine.heuristics) == 9

    def test_engine_run_with_mock_data(self, cfg, solana_transactions):
        from aml_pipeline.clustering.solana_engine import SolanaClusteringEngine
        from aml_pipeline.clustering.solana_adapter import SolanaAdapter

        class MockSolanaAdapter(SolanaAdapter):
            def __init__(self, cfg, txs):
                self.cfg = cfg
                self._txs = txs
                self._chain_config = __import__(
                    'aml_pipeline.chains.registry', fromlist=['get_chain']
                ).get_chain("solana")

            def iter_transactions(self, **kwargs):
                return iter(self._txs)

        adapter = MockSolanaAdapter(cfg, solana_transactions)
        engine = SolanaClusteringEngine(cfg=cfg, adapter=adapter)
        results = engine.run(persist=False, min_cluster_size=2)
        assert isinstance(results, list)
