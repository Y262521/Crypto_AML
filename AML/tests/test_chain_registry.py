"""
Tests: ChainRegistry — Phase 1
Verifies all 10 chains are registered with correct metadata.
"""
import pytest
from aml_pipeline.chains.registry import (
    get_registry, get_chain,
    EVM_CHAIN_NAMES, UTXO_CHAIN_NAMES, ACCOUNT_CHAIN_NAMES, ALL_CHAIN_NAMES,
    BLOCKCHAIN_TYPE_EVM, BLOCKCHAIN_TYPE_UTXO, BLOCKCHAIN_TYPE_ACCOUNT,
)


class TestChainRegistry:

    def test_registry_has_all_10_chains(self):
        r = get_registry()
        assert len(r.all_chains()) == 10

    def test_all_chain_names_set(self):
        expected = {
            "ethereum", "bnb", "polygon", "arbitrum", "base",
            "bitcoin", "litecoin", "dogecoin", "bitcoin_cash",
            "solana",
        }
        assert ALL_CHAIN_NAMES == expected

    def test_evm_chains(self):
        assert EVM_CHAIN_NAMES == {"ethereum", "bnb", "polygon", "arbitrum", "base"}
        r = get_registry()
        for name in EVM_CHAIN_NAMES:
            c = r.get(name)
            assert c.blockchain_type == BLOCKCHAIN_TYPE_EVM, f"{name} should be EVM"
            assert c.is_evm

    def test_utxo_chains(self):
        assert UTXO_CHAIN_NAMES == {"bitcoin", "litecoin", "dogecoin", "bitcoin_cash"}
        r = get_registry()
        for name in UTXO_CHAIN_NAMES:
            c = r.get(name)
            assert c.blockchain_type == BLOCKCHAIN_TYPE_UTXO
            assert c.is_utxo
            assert not c.supports_contracts

    def test_account_chains(self):
        assert ACCOUNT_CHAIN_NAMES == {"solana"}
        sol = get_chain("solana")
        assert sol.blockchain_type == BLOCKCHAIN_TYPE_ACCOUNT
        assert sol.is_account_based
        assert sol.native_asset == "SOL"

    def test_ethereum_metadata(self):
        eth = get_chain("ethereum")
        assert eth.chain_id == 1
        assert eth.native_asset == "ETH"
        assert "alchemy" in eth.rpc_url_template.lower()

    def test_bitcoin_metadata(self):
        btc = get_chain("bitcoin")
        assert btc.chain_id == 0
        assert btc.native_asset == "BTC"
        assert btc.high_value_threshold_native == pytest.approx(0.5)

    def test_rpc_url_filled_with_key(self):
        eth = get_chain("ethereum")
        url = eth.rpc_url("MYKEY123")
        assert "MYKEY123" in url
        assert url.startswith("https://")

    def test_require_raises_on_unknown(self):
        with pytest.raises(ValueError, match="Unknown chain"):
            get_chain("xrp")

    def test_chain_id_lookup(self):
        r = get_registry()
        eth = r.get_by_chain_id(1)
        assert eth is not None
        assert eth.chain_name == "ethereum"

    @pytest.mark.parametrize("chain_name", list(ALL_CHAIN_NAMES))
    def test_every_chain_has_required_fields(self, chain_name):
        c = get_chain(chain_name)
        assert c.chain_name
        assert c.display_name
        assert c.native_asset
        assert c.blockchain_type in (
            BLOCKCHAIN_TYPE_EVM, BLOCKCHAIN_TYPE_UTXO, BLOCKCHAIN_TYPE_ACCOUNT
        )
        assert c.alchemy_network
        assert "{api_key}" in c.rpc_url_template
