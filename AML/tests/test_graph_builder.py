"""
Tests: Graph Builder chain-awareness — Phase 1
Verifies nodes and edges carry correct chain metadata.
"""
import pytest
from aml_pipeline.clustering.base import TxRecord
from aml_pipeline.clustering.graph_builder import build_graph, build_graph_artifacts


def _make_tx(tx_hash, frm, to, value, chain_name, chain_id, btype, asset, ts=1000.0):
    return TxRecord(
        tx_hash=tx_hash,
        block_number=1,
        timestamp=ts,
        from_address=frm,
        to_address=to,
        value_eth=value,
        value_native=value,
        chain_name=chain_name,
        chain_id=chain_id,
        blockchain_type=btype,
        native_asset=asset,
    )


class TestGraphBuilder:

    def test_ethereum_nodes_tagged(self):
        txs = [_make_tx("0x1", "0xaaa", "0xbbb", 1.0, "ethereum", 1, "EVM", "ETH")]
        G = build_graph(txs)
        for node, data in G.nodes(data=True):
            assert data["chain_name"] == "ethereum"
            assert data["blockchain_type"] == "EVM"

    def test_bitcoin_nodes_tagged(self):
        txs = [_make_tx("btx1", "bc1aaaa", "bc1bbbb", 0.5, "bitcoin", 0, "UTXO", "BTC")]
        G = build_graph(txs)
        for node, data in G.nodes(data=True):
            assert data["chain_name"] == "bitcoin"
            assert data["blockchain_type"] == "UTXO"
            assert data["native_asset"] == "BTC"

    def test_solana_nodes_tagged(self):
        txs = [_make_tx("stx1", "sol_a", "sol_b", 2.0, "solana", 900, "ACCOUNT_BASED", "SOL")]
        G = build_graph(txs)
        for node, data in G.nodes(data=True):
            assert data["chain_name"] == "solana"
            assert data["blockchain_type"] == "ACCOUNT_BASED"

    def test_edges_carry_chain_name(self):
        txs = [_make_tx("0x1", "0xaaa", "0xbbb", 1.0, "ethereum", 1, "EVM", "ETH")]
        G = build_graph(txs)
        for u, v, data in G.edges(data=True):
            assert data["chain_name"] == "ethereum"
            assert data["value_native"] == pytest.approx(1.0)

    def test_multi_chain_graph(self):
        """ETH and BTC transactions can coexist in the same graph."""
        txs = [
            _make_tx("0x1", "0xaaa", "0xbbb", 1.0, "ethereum", 1,   "EVM",  "ETH"),
            _make_tx("btx1", "bc1a",  "bc1b",  0.5, "bitcoin",  0,   "UTXO", "BTC"),
        ]
        G = build_graph(txs)
        assert G.number_of_nodes() == 4
        assert G.number_of_edges() == 2
        chain_names = {data["chain_name"] for _, _, data in G.edges(data=True)}
        assert chain_names == {"ethereum", "bitcoin"}

    def test_artifacts_adjacency_has_chain_fields(self):
        txs = [
            _make_tx("0x1", "0xaaa", "0xbbb", 1.0, "ethereum", 1, "EVM", "ETH"),
            _make_tx("0x2", "0xbbb", "0xccc", 0.5, "ethereum", 1, "EVM", "ETH"),
        ]
        artifacts = build_graph_artifacts(txs)
        for edges in artifacts.outgoing_edges.values():
            for edge in edges:
                assert "chain_name" in edge
                assert edge["chain_name"] == "ethereum"

    def test_skips_empty_addresses(self):
        """TxRecords with empty from/to should not create nodes."""
        txs = [
            TxRecord("0x1", 1, 1000.0, "", "0xbbb", 1.0),
            TxRecord("0x2", 1, 1000.0, "0xaaa", "", 1.0),
            _make_tx("0x3", "0xaaa", "0xbbb", 1.0, "ethereum", 1, "EVM", "ETH"),
        ]
        G = build_graph(txs)
        assert G.number_of_edges() == 1
