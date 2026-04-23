"""Bridge-hopping detector."""

from __future__ import annotations

from collections import defaultdict
import math
import statistics
from typing import Any

from ..types import (
    BridgePairRecord,
    DetectorHit,
    DetectorOutput,
    EvidenceRecord,
    LayeringContext,
    clamp,
    iso_from_ts,
    stable_evidence_id,
)


class BridgeHoppingDetector:
    detector_type = "bridge_hopping"

    def detect(self, context: LayeringContext) -> DetectorOutput:
        output = DetectorOutput()
        tolerance_ratio = max(0.001, float(context.cfg.layering_bridge_amount_tolerance_ratio or 0.03))
        max_latency = max(300, int(context.cfg.layering_bridge_max_latency_seconds or 86400))
        min_pairs = max(1, int(context.cfg.layering_bridge_min_pairs or 1))

        deposits: list[dict[str, Any]] = []
        withdrawals: list[dict[str, Any]] = []
        for tx in context.transactions:
            categories = context.service_registry.categories_for_method(tx.input_method_id)
            to_labels = context.labels_for_address(tx.to_address) | categories
            from_labels = context.labels_for_address(tx.from_address)
            if "bridge" in to_labels and float(tx.value_eth or 0.0) > 0:
                deposits.append(
                    {
                        "tx_hash": tx.tx_hash,
                        "bridge_contract": tx.to_address,
                        "user_address": tx.from_address,
                        "timestamp": float(tx.timestamp or 0.0),
                        "amount": float(tx.value_eth or 0.0),
                    }
                )
            elif "bridge" in from_labels and float(tx.value_eth or 0.0) > 0:
                withdrawals.append(
                    {
                        "tx_hash": tx.tx_hash,
                        "bridge_contract": tx.from_address,
                        "user_address": tx.to_address,
                        "timestamp": float(tx.timestamp or 0.0),
                        "amount": float(tx.value_eth or 0.0),
                    }
                )

        paired_by_seed: dict[str, list[BridgePairRecord]] = defaultdict(list)
        evidence_metrics: dict[str, list[dict[str, Any]]] = defaultdict(list)
        used_withdrawals: set[int] = set()

        for deposit in sorted(deposits, key=lambda item: (item["timestamp"], item["tx_hash"])):
            candidates: list[tuple[float, int, dict[str, Any]]] = []
            for index, withdrawal in enumerate(withdrawals):
                if index in used_withdrawals:
                    continue
                if withdrawal["bridge_contract"] != deposit["bridge_contract"]:
                    continue
                latency = float(withdrawal["timestamp"]) - float(deposit["timestamp"])
                if latency < 0 or latency > max_latency:
                    continue
                amount = float(deposit["amount"] or 0.0)
                diff_ratio = abs(float(withdrawal["amount"] or 0.0) - amount) / max(amount, 1e-9)
                if diff_ratio > tolerance_ratio:
                    continue
                score = diff_ratio + (latency / max_latency)
                candidates.append((score, index, withdrawal))

            if not candidates:
                continue

            _, withdrawal_index, withdrawal = sorted(candidates, key=lambda item: (item[0], item[2]["timestamp"], item[2]["tx_hash"]))[0]
            used_withdrawals.add(withdrawal_index)
            latency_seconds = float(withdrawal["timestamp"]) - float(deposit["timestamp"])
            amount_similarity = 1.0 - (
                abs(float(withdrawal["amount"] or 0.0) - float(deposit["amount"] or 0.0))
                / max(float(deposit["amount"] or 0.0), 1e-9)
            )
            latency_score = math.exp(-latency_seconds / max_latency)
            freshness_score = 1.0 if context.is_fresh_address(withdrawal["user_address"], withdrawal["timestamp"], max_age_seconds=max_latency) else 0.45
            confidence = clamp(
                0.40 * amount_similarity
                + 0.30 * latency_score
                + 0.20 * 1.0
                + 0.10 * freshness_score
            )

            seed_ids = {
                seed_id
                for seed_id in (
                    context.entity_for_address(deposit["user_address"]),
                    context.entity_for_address(withdrawal["user_address"]),
                )
                if seed_id in context.seeds
            }
            if not seed_ids:
                continue

            for seed_id in sorted(seed_ids):
                pair = BridgePairRecord(
                    entity_id=seed_id,
                    source_tx=str(deposit["tx_hash"] or ""),
                    destination_tx=str(withdrawal["tx_hash"] or ""),
                    bridge_contract=str(deposit["bridge_contract"] or "").lower().strip(),
                    token="ETH",
                    amount=round(float(deposit["amount"] or 0.0), 8),
                    latency_seconds=round(latency_seconds, 2),
                    confidence_score=round(confidence, 4),
                    source_address=str(deposit["user_address"] or "").lower().strip(),
                    destination_address=str(withdrawal["user_address"] or "").lower().strip(),
                    details={
                        "amount_similarity": round(amount_similarity, 4),
                        "latency_score": round(latency_score, 4),
                        "fresh_destination": freshness_score > 0.9,
                    },
                )
                paired_by_seed[seed_id].append(pair)
                evidence_metrics[seed_id].append(
                    {
                        "source_tx": pair.source_tx,
                        "destination_tx": pair.destination_tx,
                        "bridge_contract": pair.bridge_contract,
                        "amount": pair.amount,
                        "latency_seconds": pair.latency_seconds,
                        "confidence_score": pair.confidence_score,
                    }
                )
                output.bridge_pairs.append(pair)

        for seed_id, pairs in sorted(paired_by_seed.items()):
            if len(pairs) < min_pairs:
                continue
            avg_confidence = statistics.fmean(pair.confidence_score for pair in pairs)
            if avg_confidence < 0.45 and len(pairs) < 2:
                continue
            seed = context.seeds[seed_id]
            evidence_id = stable_evidence_id(seed_id, self.detector_type, 1)
            tx_hashes = sorted({pair.source_tx for pair in pairs} | {pair.destination_tx for pair in pairs})
            earliest_ts = min(context.tx_by_hash[tx_hash].timestamp for tx_hash in tx_hashes if tx_hash in context.tx_by_hash)
            latest_ts = max(context.tx_by_hash[tx_hash].timestamp for tx_hash in tx_hashes if tx_hash in context.tx_by_hash)
            metrics = {
                "pair_count": len(pairs),
                "average_latency_seconds": round(statistics.fmean(pair.latency_seconds for pair in pairs), 2),
                "bridge_contracts": sorted({pair.bridge_contract for pair in pairs}),
                "pairs": evidence_metrics[seed_id],
            }
            output.evidence.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    entity_id=seed_id,
                    detector_type=self.detector_type,
                    evidence_type="bridge_pair",
                    title="Matched bridge hop pairs",
                    summary=f"Matched {len(pairs)} bridge deposit/withdrawal pairs with amount and latency consistency.",
                    entity_ids=[seed_id],
                    tx_hashes=tx_hashes,
                    path=[pairs[0].source_address, pairs[0].bridge_contract, pairs[0].destination_address] if pairs else [],
                    metrics=metrics,
                    first_seen_at=iso_from_ts(earliest_ts),
                    last_seen_at=iso_from_ts(latest_ts),
                )
            )
            output.hits.append(
                DetectorHit(
                    entity_id=seed_id,
                    entity_type=seed.entity_type,
                    detector_type=self.detector_type,
                    confidence_score=round(avg_confidence, 4),
                    summary="Bridge interaction matched to a likely re-entry transfer.",
                    score_components={
                        "pair_count": round(min(1.0, len(pairs) / max(1, min_pairs)), 4),
                        "average_pair_confidence": round(avg_confidence, 4),
                    },
                    metrics=metrics,
                    supporting_tx_hashes=tx_hashes,
                    evidence_ids=[evidence_id],
                    first_observed_at=iso_from_ts(earliest_ts),
                    last_observed_at=iso_from_ts(latest_ts),
                )
            )

        return output
