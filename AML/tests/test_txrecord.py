"""
Tests: TxRecord chain fields — Phase 1
Verifies chain identity fields are correctly set and defaulted.
"""
import pytest
from aml_pipeline.clustering.base import TxRecord, BlockchainAdapter


class TestTxRecord:

    def test_default_chain_is_ethereum(self):
        tx = TxRecord("0x1", 1, 1000.0, "0xfrom", "0xto", 1.0)
        assert tx.chain_name == "ethereum"
        assert tx.chain_id == 1
        assert tx.blockchain_type == "EVM"
        assert tx.native_asset == "ETH"

    def test_value_native_set_from_value_eth(self):
        tx = TxRecord("0x1", 1, 1000.0, "0xfrom", "0xto", 2.5)
        assert tx.value_native == pytest.approx(2.5)

    def test_explicit_chain_fields(self):
        tx = TxRecord(
            tx_hash="btx1",
            block_number=840001,
            timestamp=1700000000.0,
            from_address="bc1qaaa",
            to_address="bc1qbbb",
            value_eth=0.5,
            value_native=0.5,
            chain_name="bitcoin",
            chain_id=0,
            blockchain_type="UTXO",
            native_asset="BTC",
        )
        assert tx.chain_name == "bitcoin"
        assert tx.chain_id == 0
        assert tx.blockchain_type == "UTXO"
        assert tx.native_asset == "BTC"
        assert tx.value_native == pytest.approx(0.5)

    def test_solana_chain_fields(self):
        tx = TxRecord(
            tx_hash="stx1",
            block_number=300000001,
            timestamp=1700000000.0,
            from_address="sol_acc_a",
            to_address="sol_acc_b",
            value_eth=0.1,
            value_native=0.1,
            chain_name="solana",
            chain_id=900,
            blockchain_type="ACCOUNT_BASED",
            native_asset="SOL",
        )
        assert tx.chain_name == "solana"
        assert tx.blockchain_type == "ACCOUNT_BASED"
        assert tx.native_asset == "SOL"

    @pytest.mark.parametrize("chain,cid,btype,asset", [
        ("ethereum",     1,     "EVM",           "ETH"),
        ("bnb",          56,    "EVM",           "BNB"),
        ("polygon",      137,   "EVM",           "POL"),
        ("arbitrum",     42161, "EVM",           "ETH"),
        ("base",         8453,  "EVM",           "ETH"),
        ("bitcoin",      0,     "UTXO",          "BTC"),
        ("litecoin",     2,     "UTXO",          "LTC"),
        ("dogecoin",     3,     "UTXO",          "DOGE"),
        ("bitcoin_cash", 145,   "UTXO",          "BCH"),
        ("solana",       900,   "ACCOUNT_BASED", "SOL"),
    ])
    def test_all_chain_combinations(self, chain, cid, btype, asset):
        tx = TxRecord(
            tx_hash="tx",
            block_number=1,
            timestamp=1000.0,
            from_address="addr_a",
            to_address="addr_b",
            value_eth=1.0,
            value_native=1.0,
            chain_name=chain,
            chain_id=cid,
            blockchain_type=btype,
            native_asset=asset,
        )
        assert tx.chain_name == chain
        assert tx.chain_id == cid
        assert tx.blockchain_type == btype
        assert tx.native_asset == asset
