"""Peeling-chain detector."""

from __future__ import annotations

from collections import defaultdict
import math
import statistics
from typing import Any

from ..types import (
    DetectorHit,
    DetectorOutput,
    EvidenceRecord,
    LayeringContext,
    clamp,
    iso_from_ts,
    stable_evidence_id,
)


class PeelingChainDetector:
    detector_type = "peeling_chain"

    def detect(self, context: LayeringContext) -> DetectorOutput:
        output = DetectorOutput()
        min_hops = max(2, int(context.cfg.layering_peel_min_hops or 3))
        max_hops = max(min_hops, int(context.cfg.layering_peel_max_hops or 6))
        max_gap = max(60, int(context.cfg.layering_peel_max_time_gap_seconds or 7200))
        min_decay = max(0.0, float(context.cfg.layering_peel_min_decay_ratio or 0.02))
        min_fragment_ratio = max(0.0, float(context.cfg.layering_peel_min_fragment_ratio or 0.01))
        max_fragment_ratio = max(min_fragment_ratio, float(context.cfg.layering_peel_max_fragment_ratio or 0.35))

        for seed in sorted(context.seeds.values(), key=lambda item: item.entity_id):
            candidates: list[dict[str, Any]] = []
            for address in seed.addresses:
                chain = self._extract_chain(
                    context,
                    start_address=address,
                    min_hops=min_hops,
                    max_hops=max_hops,
                    max_gap=max_gap,
                    min_decay=min_decay,
                    min_fragment_ratio=min_fragment_ratio,
                    max_fragment_ratio=max_fragment_ratio,
                )
                if chain is not None:
                    candidates.append(chain)

            if not candidates:
                continue

            best = max(
                candidates,
                key=lambda item: (
                    float(item["confidence"]),
                    int(item["hop_count"]),
                    -float(item["average_hop_gap_seconds"]),
                ),
            )
            evidence_id = stable_evidence_id(seed.entity_id, self.detector_type, 1)
            output.evidence.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    entity_id=seed.entity_id,
                    detector_type=self.detector_type,
                    evidence_type="path",
                    title="Repeated peeling chain",
                    summary=(
                        f"Main value stream continues across {best['hop_count']} hops while smaller fragments are repeatedly shaved off."
                    ),
                    entity_ids=[seed.entity_id],
                    tx_hashes=best["supporting_tx_hashes"],
                    path=best["path"],
                    metrics=best["metrics"],
                    first_seen_at=best["first_observed_at"],
                    last_seen_at=best["last_observed_at"],
                )
            )
            output.hits.append(
                DetectorHit(
                    entity_id=seed.entity_id,
                    entity_type=seed.entity_type,
                    detector_type=self.detector_type,
                    confidence_score=best["confidence"],
                    summary=f"Peeling pattern observed across {best['hop_count']} hops.",
                    score_components=best["score_components"],
                    metrics=best["metrics"],
                    supporting_tx_hashes=best["supporting_tx_hashes"],
                    evidence_ids=[evidence_id],
                    first_observed_at=best["first_observed_at"],
                    last_observed_at=best["last_observed_at"],
                )
            )

        return output

    def _extract_chain(
        self,
        context: LayeringContext,
        start_address: str,
        min_hops: int,
        max_hops: int,
        max_gap: int,
        min_decay: float,
        min_fragment_ratio: float,
        max_fragment_ratio: float,
    ) -> dict[str, Any] | None:
        current = start_address.lower().strip()
        path = [current]
        visited = {current}
        hops: list[dict[str, Any]] = []
        prior_main_value: float | None = None
        prior_timestamp = 0.0

        while len(hops) < max_hops:
            outgoing = [
                edge
                for edge in context.artifacts.outgoing_edges.get(current, [])
                if float(edge.get("timestamp") or 0.0) >= prior_timestamp
            ]
            if not outgoing:
                break

            anchor_ts = float(outgoing[0].get("timestamp") or 0.0)
            window = [
                edge
                for edge in outgoing
                if float(edge.get("timestamp") or 0.0) <= anchor_ts + max_gap
            ]
            grouped: dict[str, dict[str, Any]] = defaultdict(
                lambda: {"value_eth": 0.0, "tx_hashes": [], "edges": []}
            )
            for edge in window:
                target = str(edge.get("to_address") or "").lower().strip()
                if not target:
                    continue
                grouped[target]["value_eth"] += float(edge.get("value_eth") or 0.0)
                grouped[target]["tx_hashes"].append(str(edge.get("tx_hash") or ""))
                grouped[target]["edges"].append(edge)

            if len(grouped) < 2:
                break

            ranked = sorted(
                grouped.items(),
                key=lambda item: (
                    float(item[1]["value_eth"]),
                    -min(float(edge.get("timestamp") or 0.0) for edge in item[1]["edges"]),
                    item[0],
                ),
                reverse=True,
            )
            main_target, main_data = ranked[0]
            if main_target in visited:
                break

            fragment_items = ranked[1:]
            main_value = float(main_data["value_eth"] or 0.0)
            fragment_total = sum(float(item[1]["value_eth"] or 0.0) for item in fragment_items)
            if main_value <= 0 or fragment_total <= 0:
                break

            fragment_ratio = fragment_total / max(main_value, 1e-9)
            if fragment_ratio < min_fragment_ratio or fragment_ratio > max_fragment_ratio:
                break
            if prior_main_value is not None and main_value > prior_main_value * (1.0 - min_decay):
                break

            main_edge = sorted(
                main_data["edges"],
                key=lambda edge: (
                    float(edge.get("timestamp") or 0.0),
                    str(edge.get("tx_hash") or ""),
                ),
            )[0]
            hop = {
                "source": current,
                "main_target": main_target,
                "main_value_eth": main_value,
                "main_tx_hash": str(main_edge.get("tx_hash") or ""),
                "timestamp": float(main_edge.get("timestamp") or 0.0),
                "dominant_share": main_value / max(main_value + fragment_total, 1e-9),
                "fragment_ratio": fragment_ratio,
                "fragments": [
                    {
                        "target": target,
                        "value_eth": float(data["value_eth"] or 0.0),
                        "tx_hashes": list(data["tx_hashes"]),
                    }
                    for target, data in fragment_items
                ],
            }
            hops.append(hop)
            path.append(main_target)
            visited.add(main_target)
            current = main_target
            prior_main_value = main_value
            prior_timestamp = float(main_edge.get("timestamp") or 0.0)

        if len(hops) < min_hops:
            return None

        main_values = [float(hop["main_value_eth"]) for hop in hops]
        fragment_ratios = [float(hop["fragment_ratio"]) for hop in hops]
        dominant_shares = [float(hop["dominant_share"]) for hop in hops]
        time_gaps = [
            max(0.0, float(hops[index]["timestamp"]) - float(hops[index - 1]["timestamp"]))
            for index in range(1, len(hops))
        ]
        decay_count = sum(
            1
            for index in range(1, len(main_values))
            if main_values[index] < main_values[index - 1]
        )
        decay_score = 1.0 if len(main_values) == 1 else decay_count / max(1, len(main_values) - 1)
        fragment_mean = statistics.fmean(fragment_ratios) if fragment_ratios else 0.0
        fragment_cv = (
            statistics.pstdev(fragment_ratios) / fragment_mean
            if len(fragment_ratios) > 1 and fragment_mean > 0
            else 0.0
        )
        repetition_score = min(1.0, len(hops) / float(min_hops + 1))
        consistency_score = clamp(1.0 - fragment_cv)
        continuity_score = (
            statistics.fmean(math.exp(-gap / max_gap) for gap in time_gaps)
            if time_gaps
            else 1.0
        )
        dominant_share_score = statistics.fmean(dominant_shares) if dominant_shares else 0.0
        terminal_penalty = 0.8 if context.is_exchange_like(path[-1]) else 1.0
        confidence = clamp(
            (
                0.30 * repetition_score
                + 0.25 * decay_score
                + 0.20 * consistency_score
                + 0.15 * continuity_score
                + 0.10 * dominant_share_score
            )
            * terminal_penalty
        )

        supporting_tx_hashes = [
            tx_hash
            for hop in hops
            for tx_hash in [hop["main_tx_hash"], *[tx for fragment in hop["fragments"] for tx in fragment["tx_hashes"]]]
            if tx_hash
        ]
        first_observed_ts = context.tx_by_hash.get(supporting_tx_hashes[0]).timestamp if supporting_tx_hashes else None
        last_observed_ts = context.tx_by_hash.get(supporting_tx_hashes[-1]).timestamp if supporting_tx_hashes else None

        return {
            "path": path,
            "hop_count": len(hops),
            "confidence": round(confidence, 4),
            "supporting_tx_hashes": supporting_tx_hashes,
            "score_components": {
                "repetition": round(repetition_score, 4),
                "monotonic_decay": round(decay_score, 4),
                "fragment_consistency": round(consistency_score, 4),
                "time_continuity": round(continuity_score, 4),
                "dominant_share": round(dominant_share_score, 4),
            },
            "metrics": {
                "main_values_eth": [round(value, 8) for value in main_values],
                "fragment_ratios": [round(value, 4) for value in fragment_ratios],
                "average_fragment_ratio": round(fragment_mean, 4),
                "average_dominant_share": round(dominant_share_score, 4),
                "average_hop_gap_seconds": round(statistics.fmean(time_gaps), 2) if time_gaps else 0.0,
                "hops": hops,
            },
            "average_hop_gap_seconds": round(statistics.fmean(time_gaps), 2) if time_gaps else 0.0,
            "first_observed_at": iso_from_ts(first_observed_ts),
            "last_observed_at": iso_from_ts(last_observed_ts),
        }
