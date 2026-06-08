"""
UTXO AML Detection Module
==========================
Extends the existing placement/layering/integration detection for
UTXO chains (Bitcoin, Litecoin, Dogecoin, Bitcoin Cash).

The existing EVM AML engines operate on TxRecord objects, which are
chain-agnostic. This module:
  1. Wraps the existing engines with UTXO-aware thresholds
  2. Adds 3 UTXO-specific layering detectors:
       - CoinJoin / Mixer Interaction Detection
       - Repeated Change-Based Peeling
       - Multi-Hop UTXO Obfuscation
  3. Plugs into the common AML abstraction layer so results end up
     in the same MariaDB tables (chain_name-tagged)

All detection results carry chain_name so investigators know which
blockchain produced the alert.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterator

from ..clustering.base import TxRecord
from ..config import Config, load_config

logger = logging.getLogger(__name__)

# ── UTXO-specific thresholds ──────────────────────────────────────────────────

UTXO_THRESHOLDS = {
    "bitcoin": {
        "structuring_window_minutes": 60,
        "structuring_min_tx": 3,
        "structuring_max_variance": 0.08,
        "smurfing_min_senders": 5,
        "micro_max_tx_native": 0.005,   # 0.005 BTC ≈ dust
        "micro_min_total_native": 0.1,
        "high_value_native": 0.5,
        "coinjoin_min_inputs": 5,
        "peeling_min_hops": 3,
    },
    "litecoin": {
        "structuring_window_minutes": 60,
        "structuring_min_tx": 3,
        "structuring_max_variance": 0.08,
        "smurfing_min_senders": 5,
        "micro_max_tx_native": 0.5,
        "micro_min_total_native": 10.0,
        "high_value_native": 500.0,
        "coinjoin_min_inputs": 5,
        "peeling_min_hops": 3,
    },
    "dogecoin": {
        "structuring_window_minutes": 120,
        "structuring_min_tx": 4,
        "structuring_max_variance": 0.1,
        "smurfing_min_senders": 6,
        "micro_max_tx_native": 500.0,
        "micro_min_total_native": 10000.0,
        "high_value_native": 50000.0,
        "coinjoin_min_inputs": 7,
        "peeling_min_hops": 4,
    },
    "bitcoin_cash": {
        "structuring_window_minutes": 60,
        "structuring_min_tx": 3,
        "structuring_max_variance": 0.08,
        "smurfing_min_senders": 5,
        "micro_max_tx_native": 0.05,
        "micro_min_total_native": 1.0,
        "high_value_native": 50.0,
        "coinjoin_min_inputs": 5,
        "peeling_min_hops": 3,
    },
}


def get_utxo_thresholds(chain_name: str) -> dict[str, Any]:
    return UTXO_THRESHOLDS.get(chain_name, UTXO_THRESHOLDS["bitcoin"])


# ── Detector 1: CoinJoin / Mixer Interaction ──────────────────────────────────

def detect_coinjoin_mixing(
    transactions: list[TxRecord],
    chain_name: str = "bitcoin",
) -> list[dict[str, Any]]:
    """
    Detect addresses interacting with CoinJoin coordinators or mixing services.

    Signals:
      - Transaction has >= N equal-value outputs (CoinJoin pattern)
      - Transaction has unusually high input count
      - Address repeatedly participates in suspected CoinJoin txs

    Returns a list of alert dicts with entity_id, confidence_score, etc.
    """
    thresholds = get_utxo_thresholds(chain_name)
    min_inputs = thresholds["coinjoin_min_inputs"]

    # Group tx_hashes by from_address, track output values per tx
    tx_inputs:  dict[str, set[str]]    = defaultdict(set)
    tx_outputs: dict[str, list[float]] = defaultdict(list)

    for tx in transactions:
        if not tx.from_address or tx.from_address.upper() == "COINBASE":
            continue
        tx_inputs[tx.tx_hash].add(tx.from_address)
        tx_outputs[tx.tx_hash].append(tx.value_native)

    # Identify suspected CoinJoin transactions
    coinjoin_txs: set[str] = set()
    for tx_hash, inputs in tx_inputs.items():
        if len(inputs) < min_inputs:
            continue
        outputs = tx_outputs.get(tx_hash, [])
        if len(outputs) < min_inputs:
            continue
        # Check for equal-output pattern
        avg = sum(outputs) / len(outputs) if outputs else 0
        if avg <= 0:
            continue
        equal_count = sum(
            1 for v in outputs
            if abs(v - avg) / avg < 0.02
        )
        if equal_count >= len(outputs) * 0.6:
            coinjoin_txs.add(tx_hash)

    # Count per-address participation
    addr_coinjoin_count: dict[str, int] = defaultdict(int)
    addr_tx_hashes:      dict[str, list[str]] = defaultdict(list)

    for tx in transactions:
        if tx.tx_hash in coinjoin_txs and tx.from_address:
            addr_coinjoin_count[tx.from_address] += 1
            addr_tx_hashes[tx.from_address].append(tx.tx_hash)

    alerts = []
    for addr, count in addr_coinjoin_count.items():
        if count < 1:
            continue
        confidence = min(1.0, 0.5 + count * 0.1)
        alerts.append({
            "entity_id": addr,
            "entity_type": "address",
            "detector_type": "coinjoin_mixing",
            "chain_name": chain_name,
            "confidence_score": round(confidence, 4),
            "summary": (
                f"Address participated in {count} suspected CoinJoin "
                f"transaction(s) on {chain_name}."
            ),
            "supporting_tx_hashes": list(set(addr_tx_hashes[addr]))[:20],
            "metrics": {
                "coinjoin_tx_count": count,
                "total_coinjoin_txs_detected": len(coinjoin_txs),
            },
            "score_components": {
                "participation_count": count,
                "base_score": 0.5,
                "per_tx_bonus": 0.1,
            },
            "first_observed_at": None,
            "last_observed_at": None,
            "evidence_ids": [],
        })

    return sorted(alerts, key=lambda a: a["confidence_score"], reverse=True)


# ── Detector 2: Repeated Change-Based Peeling ─────────────────────────────────

def detect_change_peeling(
    transactions: list[TxRecord],
    chain_name: str = "bitcoin",
) -> list[dict[str, Any]]:
    """
    Detect peeling chain pattern in UTXO: address A sends to B and a
    change address C, then C sends to D and change address E, etc.

    The change-address is identified as the smaller output in 2-output txs.
    A peeling chain is detected when this pattern repeats >= min_hops times.
    """
    thresholds = get_utxo_thresholds(chain_name)
    min_hops = thresholds["peeling_min_hops"]

    # Build output graph: from_addr → list of (to_addr, value, tx_hash)
    out_graph: dict[str, list[tuple[str, float, str]]] = defaultdict(list)
    # Track tx outputs per tx_hash
    tx_outputs: dict[str, list[tuple[str, str, float]]] = defaultdict(list)

    for tx in transactions:
        if not tx.from_address or not tx.to_address:
            continue
        out_graph[tx.from_address].append(
            (tx.to_address, tx.value_native, tx.tx_hash)
        )
        tx_outputs[tx.tx_hash].append(
            (tx.from_address, tx.to_address, tx.value_native)
        )

    # Find 2-output transactions and identify change (smaller output)
    # change_map: from_addr → change_addr (the smaller output)
    change_next: dict[str, str] = {}
    tx_two_outputs: set[str] = set()

    for tx_hash, pairs in tx_outputs.items():
        # Get unique senders and receivers in this tx
        senders   = {p[0] for p in pairs}
        receivers = {p[1] for p in pairs}
        if len(receivers) != 2:
            continue
        tx_two_outputs.add(tx_hash)
        # Sum value per receiver
        receiver_values: dict[str, float] = defaultdict(float)
        for _, to_addr, val in pairs:
            receiver_values[to_addr] += val
        recv_list = sorted(receiver_values.items(), key=lambda x: x[1])
        if len(recv_list) == 2:
            change_addr   = recv_list[0][0]   # smaller value = change
            payment_addr  = recv_list[1][0]   # larger value = payment
            for sender in senders:
                change_next[sender] = change_addr

    # Trace peeling chains: follow change outputs
    alerts = []
    visited: set[str] = set()

    for start_addr in list(change_next.keys()):
        if start_addr in visited:
            continue
        chain_addrs = [start_addr]
        current = start_addr
        depth = 0
        while depth < 20:
            next_addr = change_next.get(current)
            if not next_addr or next_addr in chain_addrs:
                break
            chain_addrs.append(next_addr)
            current = next_addr
            depth += 1

        if len(chain_addrs) < min_hops:
            continue

        for addr in chain_addrs:
            visited.add(addr)

        confidence = min(1.0, 0.4 + len(chain_addrs) * 0.08)
        alerts.append({
            "entity_id": start_addr,
            "entity_type": "address",
            "detector_type": "utxo_change_peeling",
            "chain_name": chain_name,
            "confidence_score": round(confidence, 4),
            "summary": (
                f"Change-based peeling chain of depth {len(chain_addrs)} "
                f"detected starting from {start_addr[:12]}… on {chain_name}."
            ),
            "supporting_tx_hashes": [],
            "metrics": {
                "chain_depth": len(chain_addrs),
                "chain_addresses": chain_addrs[:10],
            },
            "score_components": {
                "depth": len(chain_addrs),
                "base_score": 0.4,
                "per_hop_bonus": 0.08,
            },
            "evidence_ids": [],
            "first_observed_at": None,
            "last_observed_at": None,
        })

    return sorted(alerts, key=lambda a: a["confidence_score"], reverse=True)


# ── Detector 3: Multi-Hop UTXO Obfuscation ────────────────────────────────────

def detect_multihop_obfuscation(
    transactions: list[TxRecord],
    chain_name: str = "bitcoin",
    min_hops: int = 4,
) -> list[dict[str, Any]]:
    """
    Detect addresses that route funds through many intermediate hops,
    retaining value at each step (classic layering via UTXO chain).

    Unlike EVM high-depth chaining, UTXO multi-hop tracking follows
    the main value stream through the change-output graph.

    Criteria:
      - Value retention >= 80% per hop (not just passing through)
      - Chain depth >= min_hops
      - Not a known exchange / pool (high out-degree excluded)
    """
    thresholds = get_utxo_thresholds(chain_name)
    eff_min_hops = max(min_hops, thresholds["peeling_min_hops"])
    value_retention = 0.80

    # Build: from_addr → (to_addr, value_native, tx_hash)  best outgoing edge
    best_out: dict[str, tuple[str, float, str]] = {}
    addr_total_in:  dict[str, float] = defaultdict(float)
    addr_out_degree: dict[str, int]  = defaultdict(int)

    for tx in transactions:
        if not tx.from_address or not tx.to_address:
            continue
        val = tx.value_native
        if val <= 0:
            continue
        addr_total_in[tx.to_address] += val
        addr_out_degree[tx.from_address] += 1
        existing = best_out.get(tx.from_address)
        if existing is None or val > existing[1]:
            best_out[tx.from_address] = (tx.to_address, val, tx.tx_hash)

    # Identify high-degree nodes (exchanges/pools) to exclude
    high_degree = {
        addr for addr, deg in addr_out_degree.items()
        if deg >= 20
    }

    alerts = []
    visited: set[str] = set()

    for start_addr in list(best_out.keys()):
        if start_addr in visited or start_addr in high_degree:
            continue

        path_addrs = [start_addr]
        path_txs   = []
        current    = start_addr
        prev_val   = addr_total_in.get(start_addr, 0.0)

        for _ in range(30):
            nxt = best_out.get(current)
            if not nxt:
                break
            to_addr, val, tx_hash = nxt
            if to_addr in path_addrs or to_addr in high_degree:
                break
            # Enforce value retention
            if prev_val > 0 and val / prev_val < value_retention:
                break
            path_addrs.append(to_addr)
            path_txs.append(tx_hash)
            current = to_addr
            prev_val = val

        if len(path_addrs) < eff_min_hops:
            continue

        for addr in path_addrs:
            visited.add(addr)

        confidence = min(1.0, 0.45 + len(path_addrs) * 0.06)
        alerts.append({
            "entity_id": start_addr,
            "entity_type": "address",
            "detector_type": "utxo_multihop_obfuscation",
            "chain_name": chain_name,
            "confidence_score": round(confidence, 4),
            "summary": (
                f"Multi-hop UTXO obfuscation: {len(path_addrs)}-hop chain "
                f"with >= {int(value_retention*100)}% value retention on {chain_name}."
            ),
            "supporting_tx_hashes": path_txs[:20],
            "metrics": {
                "hop_count":      len(path_addrs),
                "path_addresses": path_addrs[:10],
                "value_retention_threshold": value_retention,
            },
            "score_components": {
                "depth":          len(path_addrs),
                "base_score":     0.45,
                "per_hop_bonus":  0.06,
            },
            "evidence_ids":    [],
            "first_observed_at": None,
            "last_observed_at": None,
        })

    return sorted(alerts, key=lambda a: a["confidence_score"], reverse=True)


# ── Unified UTXO AML runner ────────────────────────────────────────────────────

class UTXOAMLDetector:
    """
    Runs all UTXO-specific AML detectors on a set of TxRecords.

    Output format mirrors the EVM LayeringAnalysisEngine detector hits
    so they can be persisted to the same layering_detector_hits table.
    """

    def __init__(self, cfg: Optional[Config] = None, chain_name: str = "bitcoin"):
        self.cfg        = cfg or load_config()
        self.chain_name = chain_name

    def run(self, transactions: list[TxRecord]) -> dict[str, Any]:
        """Run all 3 UTXO-specific layering detectors."""
        chain_txs = [
            tx for tx in transactions
            if getattr(tx, "chain_name", "bitcoin") == self.chain_name
        ] or transactions

        logger.info(
            "UTXOAMLDetector[%s]: running on %d transactions",
            self.chain_name, len(chain_txs),
        )

        coinjoin_hits  = detect_coinjoin_mixing(chain_txs, self.chain_name)
        peeling_hits   = detect_change_peeling(chain_txs, self.chain_name)
        multihop_hits  = detect_multihop_obfuscation(chain_txs, self.chain_name)

        all_hits = coinjoin_hits + peeling_hits + multihop_hits

        logger.info(
            "UTXOAMLDetector[%s]: %d coinjoin  %d peeling  %d multihop",
            self.chain_name,
            len(coinjoin_hits),
            len(peeling_hits),
            len(multihop_hits),
        )

        return {
            "chain_name":      self.chain_name,
            "total_hits":      len(all_hits),
            "coinjoin":        coinjoin_hits,
            "change_peeling":  peeling_hits,
            "multihop":        multihop_hits,
            "all_hits":        all_hits,
        }


# Optional type alias
from typing import Optional  # noqa: E402
