"""
Shared pytest fixtures for the multi-chain AML test suite.
All tests run against in-memory or synthetic data — no live RPC or DB required.
"""
from __future__ import annotations
import sys
import os
from pathlib import Path

# ── Add src to path ───────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Load .env from backend-py if present (non-fatal)
try:
    from dotenv import load_dotenv
    env_path = ROOT.parent / "crypto-aml-tracker" / "backend-py" / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except Exception:
    pass

import pytest
from aml_pipeline.clustering.base import TxRecord


# ── TxRecord factory helpers ──────────────────────────────────────────────────

def make_evm_tx(tx_hash, block, ts, frm, to, value, chain="ethereum"):
    """Create an EVM-chain TxRecord."""
    from aml_pipeline.chains.registry import get_chain
    c = get_chain(chain)
    return TxRecord(
        tx_hash=tx_hash,
        block_number=block,
        timestamp=float(ts),
        from_address=frm.lower(),
        to_address=to.lower(),
        value_eth=value,
        value_native=value,
        is_contract_call=False,
        chain_name=c.chain_name,
        chain_id=c.chain_id,
        blockchain_type=c.blockchain_type,
        native_asset=c.native_asset,
    )


def make_utxo_tx(tx_hash, block, ts, frm, to, value, chain="bitcoin"):
    """Create a UTXO-chain TxRecord."""
    from aml_pipeline.chains.registry import get_chain
    c = get_chain(chain)
    return TxRecord(
        tx_hash=tx_hash,
        block_number=block,
        timestamp=float(ts),
        from_address=frm,
        to_address=to,
        value_eth=value,
        value_native=value,
        is_contract_call=False,
        chain_name=c.chain_name,
        chain_id=c.chain_id,
        blockchain_type=c.blockchain_type,
        native_asset=c.native_asset,
    )


def make_solana_tx(tx_hash, slot, ts, frm, to, value, fee_payer=None, programs=None):
    """Create a Solana TxRecord with encoded fee_payer and programs."""
    mid = "|".join(filter(None, [fee_payer or frm] + (programs or [])))
    return TxRecord(
        tx_hash=tx_hash,
        block_number=slot,
        timestamp=float(ts),
        from_address=frm,
        to_address=to,
        value_eth=value,
        value_native=value,
        is_contract_call=bool(programs),
        input_method_id=mid,
        chain_name="solana",
        chain_id=900,
        blockchain_type="ACCOUNT_BASED",
        native_asset="SOL",
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def cfg():
    from aml_pipeline.config import load_config
    return load_config()


@pytest.fixture
def evm_transactions():
    """A set of ETH transactions that contain co-clustering evidence."""
    return [
        make_evm_tx("0xA1", 1, 1000, "0xsender1", "0xaddr_a", 1.0),
        make_evm_tx("0xA2", 1, 1010, "0xsender1", "0xaddr_b", 0.5),
        make_evm_tx("0xA3", 2, 2000, "0xaddr_a",  "0xexchange", 0.9),
        make_evm_tx("0xA4", 2, 2010, "0xaddr_b",  "0xexchange", 0.4),
        make_evm_tx("0xA5", 3, 3000, "0xaddr_c",  "0xaddr_d",   2.0),
    ]


@pytest.fixture
def utxo_transactions():
    """Bitcoin-style TxRecords with co-input evidence."""
    return [
        # tx1: two co-inputs (addr_a, addr_b) → two outputs
        make_utxo_tx("btx1", 840001, 1700000000, "bc1addr_a", "bc1recv_x", 0.4, "bitcoin"),
        make_utxo_tx("btx1", 840001, 1700000000, "bc1addr_b", "bc1recv_x", 0.3, "bitcoin"),
        make_utxo_tx("btx1", 840001, 1700000000, "bc1addr_a", "bc1change", 0.1, "bitcoin"),
        make_utxo_tx("btx1", 840001, 1700000000, "bc1addr_b", "bc1change", 0.2, "bitcoin"),
        # tx2: same co-inputs again (multi-input evidence)
        make_utxo_tx("btx2", 840002, 1700000060, "bc1addr_a", "bc1recv_y", 0.5, "bitcoin"),
        make_utxo_tx("btx2", 840002, 1700000060, "bc1addr_b", "bc1recv_y", 0.3, "bitcoin"),
    ]


@pytest.fixture
def solana_transactions():
    """Solana-style TxRecords with fee-payer evidence."""
    fp = "FEE_PAYER_MASTER"
    prog = ["ProgA", "ProgB"]
    return [
        make_solana_tx("stx1", 300000001, 1700000000, "sol_acc_a", "sol_recv_1", 0.1, fp, prog),
        make_solana_tx("stx2", 300000001, 1700000010, "sol_acc_b", "sol_recv_2", 0.1, fp, prog),
        make_solana_tx("stx3", 300000002, 1700000060, "sol_acc_a", "sol_recv_3", 0.2, fp, prog),
        make_solana_tx("stx4", 300000002, 1700000070, "sol_acc_b", "sol_recv_4", 0.2, fp, prog),
    ]
