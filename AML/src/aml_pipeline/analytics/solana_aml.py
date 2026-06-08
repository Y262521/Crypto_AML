"""
Solana AML Detection Module
============================
Extends placement/layering/integration detection for Solana.

Solana-specific layering detectors:
  1. Bridge Hopping           — Wormhole / Portal bridge usage patterns
  2. Mixer / Protocol Obfuscation — Tornado-like protocols on Solana
  3. Cross-Protocol Obfuscation  — rapid program-hopping to obscure trail

Common AML detectors (placement, integration) reuse existing engines
since they operate on TxRecord which is chain-agnostic.

All results carry chain_name="solana" for display in the UI.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Optional

from ..clustering.base import TxRecord
from ..config import Config, load_config

logger = logging.getLogger(__name__)

# ── Known Solana bridge/mixer program IDs ─────────────────────────────────────
_KNOWN_BRIDGE_PROGRAMS = frozenset({
    "wormDTUJ6AWPNvk59vGQbDvGJmqbDTdgWgAqcLBCgUb",   # Wormhole Token Bridge
    "WnFt12ZrnzZrFZkt2xsNsaNWoQribnuQ5B5FrDbwDhD",   # Wormhole NFT Bridge
    "Bridge1p5gheXUvJ6jGWGeCsgPKgnE3YgdGKRVCMY9o",   # Wormhole Core Bridge
    "3u8hJUVTA4jH1wYAyUur7FFZVQ8H635K3tSHHF4ssjQ5",  # Portal (Allbridge)
})

_KNOWN_MIXER_PROGRAMS = frozenset({
    # Tornado-like or privacy protocols on Solana
    "MixerHa22LQRjPScHHYpxp4RqRF5XHXgwYdxPFv5Yf3",   # placeholder
    "Pr1vAteMixer111111111111111111111111111111111",   # placeholder
})

_SOL_HIGH_VALUE = 150.0   # ~10 ETH equivalent


# ── Detector 1: Bridge Hopping ────────────────────────────────────────────────

def detect_bridge_hopping(
    transactions: list[TxRecord],
) -> list[dict[str, Any]]:
    """
    Detect addresses using Wormhole or other Solana bridges.
    Signals: interaction with known bridge program IDs via input_method_id.
    """
    addr_bridge_txs: dict[str, list[str]] = defaultdict(list)

    for tx in transactions:
        if not tx.from_address:
            continue
        mid = tx.input_method_id or ""
        # Programs are encoded after fee_payer in the method_id field
        parts = set(mid.split("|"))
        if parts & _KNOWN_BRIDGE_PROGRAMS:
            addr_bridge_txs[tx.from_address].append(tx.tx_hash)
        if parts & _KNOWN_BRIDGE_PROGRAMS:
            addr_bridge_txs[tx.to_address].append(tx.tx_hash)

    alerts = []
    for addr, tx_hashes in addr_bridge_txs.items():
        if not addr:
            continue
        count = len(tx_hashes)
        confidence = min(1.0, 0.55 + count * 0.08)
        alerts.append({
            "entity_id":            addr,
            "entity_type":          "address",
            "detector_type":        "solana_bridge_hopping",
            "chain_name":           "solana",
            "confidence_score":     round(confidence, 4),
            "summary": (
                f"Address interacted with Solana bridge programs "
                f"in {count} transaction(s)."
            ),
            "supporting_tx_hashes": list(set(tx_hashes))[:20],
            "metrics":              {"bridge_tx_count": count},
            "score_components":     {"base": 0.55, "per_tx": 0.08},
            "evidence_ids":         [],
            "first_observed_at":    None,
            "last_observed_at":     None,
        })

    return sorted(alerts, key=lambda a: a["confidence_score"], reverse=True)


# ── Detector 2: Mixer / Protocol Obfuscation ─────────────────────────────────

def detect_mixer_interaction(
    transactions: list[TxRecord],
) -> list[dict[str, Any]]:
    """
    Detect interactions with known Solana mixing/privacy protocols.
    """
    addr_mixer_txs: dict[str, list[str]] = defaultdict(list)

    for tx in transactions:
        mid = tx.input_method_id or ""
        parts = set(mid.split("|"))
        if parts & _KNOWN_MIXER_PROGRAMS:
            for addr in [tx.from_address, tx.to_address]:
                if addr:
                    addr_mixer_txs[addr].append(tx.tx_hash)

    alerts = []
    for addr, tx_hashes in addr_mixer_txs.items():
        count = len(tx_hashes)
        confidence = min(1.0, 0.65 + count * 0.1)
        alerts.append({
            "entity_id":            addr,
            "entity_type":          "address",
            "detector_type":        "solana_mixer_interaction",
            "chain_name":           "solana",
            "confidence_score":     round(confidence, 4),
            "summary": (
                f"Address interacted with a Solana mixer/privacy protocol "
                f"in {count} transaction(s)."
            ),
            "supporting_tx_hashes": list(set(tx_hashes))[:20],
            "metrics":              {"mixer_tx_count": count},
            "score_components":     {"base": 0.65, "per_tx": 0.1},
            "evidence_ids":         [],
            "first_observed_at":    None,
            "last_observed_at":     None,
        })

    return sorted(alerts, key=lambda a: a["confidence_score"], reverse=True)


# ── Detector 3: Cross-Protocol Obfuscation ────────────────────────────────────

def detect_cross_protocol_obfuscation(
    transactions: list[TxRecord],
    min_programs: int = 4,
    window_seconds: float = 300.0,
) -> list[dict[str, Any]]:
    """
    Detect rapid program-hopping: an address uses many different programs
    within a short time window, suggesting intentional trail obfuscation.

    Pattern: hop from DeFi protocol A → B → C → D within minutes,
    with value flowing through each step.
    """
    # addr → list of (timestamp, programs_used, value, tx_hash)
    addr_events: dict[str, list[dict]] = defaultdict(list)

    for tx in transactions:
        if not tx.from_address:
            continue
        mid = tx.input_method_id or ""
        parts = [p for p in mid.split("|")[1:] if p.strip()]
        if not parts:
            continue
        addr_events[tx.from_address].append({
            "ts":       float(tx.timestamp or 0.0),
            "programs": set(parts),
            "value":    float(tx.value_native or 0.0),
            "tx_hash":  tx.tx_hash,
        })

    alerts = []
    for addr, events in addr_events.items():
        if len(events) < 2:
            continue
        events_sorted = sorted(events, key=lambda e: e["ts"])

        # Sliding window: count unique programs used
        left = 0
        for right in range(len(events_sorted)):
            ts_r = events_sorted[right]["ts"]
            while events_sorted[left]["ts"] < ts_r - window_seconds:
                left += 1
            window = events_sorted[left:right + 1]
            all_programs: set[str] = set()
            tx_hashes = []
            total_val = 0.0
            for ev in window:
                all_programs.update(ev["programs"])
                tx_hashes.append(ev["tx_hash"])
                total_val += ev["value"]

            if len(all_programs) < min_programs:
                continue

            confidence = min(1.0, 0.45 + len(all_programs) * 0.06)
            alerts.append({
                "entity_id":            addr,
                "entity_type":          "address",
                "detector_type":        "solana_cross_protocol",
                "chain_name":           "solana",
                "confidence_score":     round(confidence, 4),
                "summary": (
                    f"Address used {len(all_programs)} distinct Solana programs "
                    f"within {int(window_seconds)}s — possible cross-protocol obfuscation."
                ),
                "supporting_tx_hashes": list(set(tx_hashes))[:20],
                "metrics": {
                    "unique_programs":  len(all_programs),
                    "window_seconds":   window_seconds,
                    "total_value_sol":  round(total_val, 6),
                },
                "score_components": {
                    "base":         0.45,
                    "per_program":  0.06,
                },
                "evidence_ids":         [],
                "first_observed_at":    None,
                "last_observed_at":     None,
            })
            break   # one alert per address is enough

    return sorted(alerts, key=lambda a: a["confidence_score"], reverse=True)


# ── Unified Solana AML runner ──────────────────────────────────────────────────

class SolanaAMLDetector:
    """
    Runs all Solana-specific AML detectors.
    Output format mirrors EVM LayeringAnalysisEngine detector hits.
    """

    def __init__(self, cfg: Optional[Config] = None):
        self.cfg = cfg or load_config()

    def run(self, transactions: list[TxRecord]) -> dict[str, Any]:
        sol_txs = [
            tx for tx in transactions
            if getattr(tx, "chain_name", "solana") == "solana"
        ] or transactions

        logger.info(
            "SolanaAMLDetector: running on %d transactions",
            len(sol_txs),
        )

        bridge_hits  = detect_bridge_hopping(sol_txs)
        mixer_hits   = detect_mixer_interaction(sol_txs)
        cross_hits   = detect_cross_protocol_obfuscation(sol_txs)

        all_hits = bridge_hits + mixer_hits + cross_hits
        logger.info(
            "SolanaAMLDetector: %d bridge  %d mixer  %d cross-protocol",
            len(bridge_hits), len(mixer_hits), len(cross_hits),
        )

        return {
            "chain_name":      "solana",
            "total_hits":      len(all_hits),
            "bridge_hopping":  bridge_hits,
            "mixer":           mixer_hits,
            "cross_protocol":  cross_hits,
            "all_hits":        all_hits,
        }
