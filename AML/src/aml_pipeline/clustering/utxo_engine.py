"""
UTXO Clustering Engine
========================
Orchestrates the full UTXO clustering pipeline for Bitcoin, Litecoin,
Dogecoin, and Bitcoin Cash.

Uses 5 UTXO-specific heuristics:
  1. CommonInputOwnershipHeuristic  — co-inputs in same tx (CIO)
  2. ChangeAddressDetectionHeuristic — change output → same wallet
  3. MultiInputClusteringHeuristic  — co-inputs across multiple txs
  4. TxFingerprintClusteringHeuristic — same structural fingerprint
  5. TemporalSpendingCorrelationHeuristic — coordinated spending windows

Also reuses two chain-agnostic EVM heuristics that work on TxRecord:
  - FanPatternHeuristic    (fan-in / fan-out)
  - TemporalHeuristic      (general temporal coordination)

Architecture: wraps the existing ClusteringEngine with UTXO-specific
defaults; no duplication of persistence or Union-Find logic.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from ..config import Config, load_config
from .base import BlockchainAdapter
from .engine import ClusteringEngine
from .utxo_adapter import UTXOAdapter
from .heuristics.utxo_common_input   import CommonInputOwnershipHeuristic
from .heuristics.utxo_change_address import ChangeAddressDetectionHeuristic
from .heuristics.utxo_multi_input    import MultiInputClusteringHeuristic
from .heuristics.utxo_tx_fingerprint import TxFingerprintClusteringHeuristic
from .heuristics.utxo_temporal_spend import TemporalSpendingCorrelationHeuristic
from .heuristics.fan                 import FanPatternHeuristic
from .heuristics.temporal            import TemporalHeuristic

logger = logging.getLogger(__name__)

# Default UTXO heuristic set — ordered from most precise to most permissive
_UTXO_HEURISTICS = [
    CommonInputOwnershipHeuristic,
    ChangeAddressDetectionHeuristic,
    MultiInputClusteringHeuristic,
    TxFingerprintClusteringHeuristic,
    TemporalSpendingCorrelationHeuristic,
    FanPatternHeuristic,
    TemporalHeuristic,
]


class UTXOClusteringEngine(ClusteringEngine):
    """
    Clustering engine configured for UTXO chains.

    Extends ClusteringEngine with UTXO-specific heuristics and a
    relaxed merge policy (CIO alone is sufficient evidence).

    Usage:
        engine = UTXOClusteringEngine(cfg=cfg, chain_name="bitcoin")
        results = engine.run(persist=True)
    """

    def __init__(
        self,
        cfg: Optional[Config] = None,
        chain_name: str = "bitcoin",
        adapter: Optional[BlockchainAdapter] = None,
        heuristics: Optional[List[type]] = None,
    ):
        cfg = cfg or load_config()

        # Patch config for UTXO: CIO alone (min_support=1) is sufficient
        # and we allow zero-value edges for UTXO dust detection
        resolved_adapter = adapter or UTXOAdapter(cfg=cfg, chain_name=chain_name)
        resolved_heuristics = heuristics or _UTXO_HEURISTICS

        super().__init__(
            cfg=cfg,
            adapter=resolved_adapter,
            heuristics=resolved_heuristics,
        )
        logger.info(
            "UTXOClusteringEngine ready: chain=%s  heuristics=%d",
            self.chain_name,
            len(self.heuristics),
        )

    def run(
        self,
        source: str = "auto",
        persist: bool = False,
        min_cluster_size: int = 1,
    ):
        """
        Run UTXO clustering.

        For UTXO chains we use min_support=1 (single heuristic sufficient)
        because Common Input Ownership alone is strong evidence.
        """
        # Temporarily lower min_heuristic_support for UTXO
        original_support = self.cfg.clustering_min_heuristic_support

        # Monkey-patch for this run only — doesn't modify the frozen Config
        import dataclasses
        patched_cfg = dataclasses.replace(
            self.cfg,
            clustering_min_heuristic_support=1,
            # Also lower the value threshold — UTXO dust is meaningful
            clustering_min_transfer_value_eth=0.0,
        )
        for h in self.heuristics:
            h.cfg = patched_cfg

        try:
            results = super().run(
                source=source,
                persist=persist,
                min_cluster_size=min_cluster_size,
            )
        finally:
            # Restore original cfg on all heuristics
            for h in self.heuristics:
                h.cfg = self.cfg

        return results


def get_utxo_clustering_engine(
    chain_name: str = "bitcoin",
    cfg: Optional[Config] = None,
) -> UTXOClusteringEngine:
    """Factory: get a UTXOClusteringEngine for any supported UTXO chain."""
    return UTXOClusteringEngine(cfg=cfg, chain_name=chain_name)
