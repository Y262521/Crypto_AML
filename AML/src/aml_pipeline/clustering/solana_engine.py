"""
Solana Clustering Engine
=========================
Orchestrates the full clustering pipeline for Solana.

Uses 5 Solana-specific heuristics:
  1. CommonFeePayerHeuristic              — shared fee payer
  2. SharedProgramInteractionHeuristic    — same program set
  3. SharedTokenAccountFundingHeuristic   — same ATA funder
  4. CoordinatedAccountActivationHeuristic — batch activation
  5. RepeatedProgramInvocationHeuristic   — same program sequence

Also reuses 4 chain-agnostic heuristics from the EVM engine:
  - BehavioralSimilarityHeuristic  — shared counterparties
  - TemporalHeuristic              — temporal coordination
  - FanPatternHeuristic            — fan-in / fan-out
  - CommonFunderHeuristic          — shared source + sink

Architecture: wraps ClusteringEngine with Solana-specific defaults.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from ..config import Config, load_config
from .base import BlockchainAdapter
from .engine import ClusteringEngine
from .solana_adapter import SolanaAdapter
from .heuristics.solana_fee_payer              import CommonFeePayerHeuristic
from .heuristics.solana_program_interaction    import SharedProgramInteractionHeuristic
from .heuristics.solana_token_account_funding  import SharedTokenAccountFundingHeuristic
from .heuristics.solana_coordinated_activation import CoordinatedAccountActivationHeuristic
from .heuristics.solana_repeated_program       import RepeatedProgramInvocationHeuristic
from .heuristics.behavioral                    import BehavioralSimilarityHeuristic
from .heuristics.temporal                      import TemporalHeuristic
from .heuristics.fan                           import FanPatternHeuristic
from .heuristics.common_funder                 import CommonFunderHeuristic

logger = logging.getLogger(__name__)

_SOLANA_HEURISTICS = [
    # Solana-specific (most precise first)
    CommonFeePayerHeuristic,
    SharedTokenAccountFundingHeuristic,
    RepeatedProgramInvocationHeuristic,
    CoordinatedAccountActivationHeuristic,
    SharedProgramInteractionHeuristic,
    # Chain-agnostic (reused from EVM)
    BehavioralSimilarityHeuristic,
    CommonFunderHeuristic,
    TemporalHeuristic,
    FanPatternHeuristic,
]


class SolanaClusteringEngine(ClusteringEngine):
    """
    Clustering engine configured for Solana.

    Uses Solana-specific heuristics that understand fee_payer,
    program invocations, and token account patterns, plus reuses
    the existing chain-agnostic EVM heuristics.
    """

    def __init__(
        self,
        cfg: Optional[Config] = None,
        adapter: Optional[BlockchainAdapter] = None,
        heuristics: Optional[List[type]] = None,
    ):
        cfg = cfg or load_config()
        super().__init__(
            cfg=cfg,
            adapter=adapter or SolanaAdapter(cfg=cfg),
            heuristics=heuristics or _SOLANA_HEURISTICS,
        )
        logger.info(
            "SolanaClusteringEngine ready: %d heuristics",
            len(self.heuristics),
        )
