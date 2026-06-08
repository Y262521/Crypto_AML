"""
Common Fee Payer Heuristic (Solana)
=====================================
In Solana, every transaction has a fee_payer — the account that pays
the transaction fee in SOL. If one address pays fees for transactions
initiated by multiple other accounts, those accounts are likely controlled
by the same entity (same wallet infrastructure or automated system).

This is the Solana equivalent of the UTXO Common Input Ownership heuristic.

The fee_payer is stored in forensics.fee_payer in the flat MongoDB docs,
and propagated into TxRecord.input_method_id[:44] during ingestion.

Signal:
  address A pays fees for transactions where address B is the primary signer.
  If A pays for >= 2 distinct signers → link those signers together.

False-positive controls:
  - Known fee-payer programs (e.g. fee relayers) with very high counts
    (>= 50 distinct accounts) are excluded from linking.
"""

from __future__ import annotations

from collections import defaultdict
from typing import List

import networkx as nx

from ...config import Config
from .base_heuristic import BaseHeuristic, ClusterEdge

_MIN_FUNDED_ACCOUNTS   = 2
_MAX_FEE_PAYER_DEGREE  = 50   # exclude mass fee payers (relayers, exchanges)


class CommonFeePayerHeuristic(BaseHeuristic):
    """
    Links Solana accounts that share the same fee payer across transactions.
    """

    name = "solana_common_fee_payer"
    description = (
        "Solana accounts whose transactions are paid for by the same fee payer "
        "are likely controlled by the same entity."
    )

    def find_links(self, G: nx.MultiDiGraph) -> List[ClusterEdge]:
        # fee_payer → set of primary signers (from_address)
        fee_payer_signers: dict[str, set[str]] = defaultdict(set)

        for u, v, data in G.edges(data=True):
            if u == v:
                continue
            val = float(data.get("value_eth") or data.get("value_native") or 0.0)
            # fee_payer is stored in input_method_id prefix (first 10 chars)
            fee_payer = (data.get("input_method_id") or "").strip()
            if not fee_payer or fee_payer in ("0x", ""):
                continue
            # Only use as fee_payer if it looks like a Solana pubkey (>=32 chars)
            if len(fee_payer) < 10:
                continue
            fee_payer_signers[fee_payer].add(u)

        links: List[ClusterEdge] = []
        seen: set[ClusterEdge] = set()

        for fee_payer, signers in fee_payer_signers.items():
            if len(signers) < _MIN_FUNDED_ACCOUNTS:
                continue
            if len(signers) > _MAX_FEE_PAYER_DEGREE:
                # Likely a mass fee-relayer — skip
                continue
            signer_list = sorted(signers)
            for i in range(len(signer_list)):
                for j in range(i + 1, len(signer_list)):
                    pair = (signer_list[i], signer_list[j])
                    if pair not in seen:
                        links.append(pair)
                        seen.add(pair)

        return links
