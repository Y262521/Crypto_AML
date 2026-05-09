"""Mixer and anonymity-tool interaction detector."""

from __future__ import annotations

from collections import Counter
import math
import statistics
from typing import Any

import networkx as nx

from ..types import DetectorHit, DetectorOutput, EvidenceRecord, LayeringContext, clamp, iso_from_ts, stable_evidence_id


class MixingInteractionDetector:
    detector_type = "mixing_interaction"

    def detect(self, context: LayeringContext) -> DetectorOutput:
        output = DetectorOutput()
        min_interactions = max(2, int(context.cfg.layering_mixing_min_interactions or 2))
        min_repeat_denoms = max(1, int(context.cfg.layering_mixing_min_repeated_denominations or 2))
        max_gap = max(300, int(context.cfg.layering_mixing_max_time_gap_seconds or 21600))
        min_ego_density = max(0.01, float(context.cfg.layering_mixing_min_ego_density or 0.18))
        amount_tolerance = max(0.001, float(context.cfg.layering_bridge_amount_tolerance_ratio or 0.03))

        for seed in sorted(context.seeds.values(), key=lambda item: item.entity_id):
            seed_addresses = set(seed.addresses)
            interactions: list[dict[str, Any]] = []
            for tx in context.transactions:
                if tx.from_address not in seed_addresses and tx.to_address not in seed_addresses:
                    continue
                counterparty = tx.to_address if tx.from_address in seed_addresses else tx.from_address
                categories = (
                    context.labels_for_address(counterparty)
                    | context.service_registry.categories_for_method(tx.input_method_id)
                )
                if "mixer" not in categories:
                    continue
                interactions.append(
                    {
                        "tx_hash": tx.tx_hash,
                        "source": tx.from_address,
                        "target": tx.to_address,
                        "counterparty": counterparty,
                        "timestamp": float(tx.timestamp or 0.0),
                        "value_eth": float(tx.value_eth or 0.0),
                    }
                )

            if len(interactions) < min_interactions:
                continue

            denominations = Counter(
                round(float(item["value_eth"] or 0.0), 3)
                for item in interactions
                if float(item["value_eth"] or 0.0) > 0
            )
            repeated_buckets = {
                denom: count
                for denom, count in denominations.items()
                if count >= 2
            }
            repeated_denom_count = sum(1 for count in repeated_buckets.values() if count >= min_repeat_denoms)
            unique_mixers = sorted({item["counterparty"] for item in interactions})
            ego_density, ego_node_count = self._ego_density(context, unique_mixers)
            concealment_edges = self._find_follow_on_concealment(
                context,
                interactions=interactions,
                seed_addresses=seed_addresses,
                max_gap=max_gap,
                amount_tolerance=amount_tolerance,
            )

            if (
                repeated_denom_count < 1
                and not concealment_edges
                and len(unique_mixers) < 2
                and ego_density < min_ego_density
            ):
                continue

            registry_score = 1.0 if unique_mixers else 0.0
            interaction_score = min(1.0, len(interactions) / float(min_interactions + 1))
            denomination_score = min(1.0, repeated_denom_count / float(max(1, min_repeat_denoms)))
            topology_score = clamp(ego_density / min_ego_density)
            concealment_score = min(1.0, len(concealment_edges) / 2.0)
            delay_score = self._delay_score(interactions, max_gap=max_gap)
            confidence = clamp(
                0.30 * registry_score
                + 0.25 * interaction_score
                + 0.20 * max(denomination_score, concealment_score)
                + 0.15 * topology_score
                + 0.10 * delay_score
            )

            supporting_tx_hashes = sorted(
                {
                    *(item["tx_hash"] for item in interactions if item["tx_hash"]),
                    *(edge["tx_hash"] for edge in concealment_edges if edge["tx_hash"]),
                }
            )
            first_ts = min((item["timestamp"] for item in interactions), default=0.0)
            last_ts = max(
                [item["timestamp"] for item in interactions]
                + [float(edge.get("timestamp") or 0.0) for edge in concealment_edges]
            ) if interactions else 0.0
            evidence_id = stable_evidence_id(seed.entity_id, self.detector_type, 1)
            metrics = {
                "interaction_count": len(interactions),
                "unique_mixer_count": len(unique_mixers),
                "unique_mixers": unique_mixers,
                "repeated_denominations": {str(key): value for key, value in repeated_buckets.items()},
                "ego_network_density": round(ego_density, 4),
                "ego_network_nodes": ego_node_count,
                "follow_on_fresh_forward_count": len(concealment_edges),
                "follow_on_fresh_forwards": concealment_edges,
            }
            output.evidence.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    entity_id=seed.entity_id,
                    detector_type=self.detector_type,
                    evidence_type="ego_network",
                    title="Repeated mixer interaction",
                    summary=(
                        f"Detected {len(interactions)} mixer interactions with repeated denomination or concealment signals."
                    ),
                    entity_ids=[seed.entity_id],
                    tx_hashes=supporting_tx_hashes,
                    path=unique_mixers[:6],
                    metrics=metrics,
                    first_seen_at=iso_from_ts(first_ts),
                    last_seen_at=iso_from_ts(last_ts),
                )
            )
            output.hits.append(
                DetectorHit(
                    entity_id=seed.entity_id,
                    entity_type=seed.entity_type,
                    detector_type=self.detector_type,
                    confidence_score=round(confidence, 4),
                    summary="Repeated mixer interaction followed by concealment-oriented behavior.",
                    score_components={
                        "registry_match": round(registry_score, 4),
                        "interaction_repetition": round(interaction_score, 4),
                        "denomination_repetition": round(denomination_score, 4),
                        "topology_density": round(topology_score, 4),
                        "timing_consistency": round(delay_score, 4),
                    },
                    metrics=metrics,
                    supporting_tx_hashes=supporting_tx_hashes,
                    evidence_ids=[evidence_id],
                    first_observed_at=iso_from_ts(first_ts),
                    last_observed_at=iso_from_ts(last_ts),
                )
            )

        return output

    def _ego_density(self, context: LayeringContext, mixer_addresses: list[str]) -> tuple[float, int]:
        nodes: set[str] = set()
        for address in mixer_addresses:
            nodes.add(address)
            nodes.update(str(item.get("to_address") or "").lower().strip() for item in context.artifacts.outgoing_edges.get(address, []))
            nodes.update(str(item.get("from_address") or "").lower().strip() for item in context.artifacts.incoming_edges.get(address, []))
        nodes.discard("")
        if len(nodes) < 2:
            return 0.0, len(nodes)
        subgraph = nx.Graph(context.artifacts.graph.subgraph(nodes))
        return nx.density(subgraph), len(nodes)

    def _find_follow_on_concealment(
        self,
        context: LayeringContext,
        interactions: list[dict[str, Any]],
        seed_addresses: set[str],
        max_gap: int,
        amount_tolerance: float,
    ) -> list[dict[str, Any]]:
        concealment_edges: list[dict[str, Any]] = []
        for interaction in interactions:
            counterparty = interaction["counterparty"]
            interaction_amount = float(interaction["value_eth"] or 0.0)
            interaction_ts = float(interaction["timestamp"] or 0.0)
            if interaction["target"] in seed_addresses:
                candidate_edges = context.artifacts.outgoing_edges.get(interaction["target"], [])
            else:
                candidate_edges = context.artifacts.outgoing_edges.get(counterparty, [])
            for edge in candidate_edges:
                edge_ts = float(edge.get("timestamp") or 0.0)
                if edge_ts < interaction_ts or edge_ts > interaction_ts + max_gap:
                    continue
                target = str(edge.get("to_address") or "").lower().strip()
                if target in seed_addresses or context.is_service_address(target):
                    continue
                value_eth = float(edge.get("value_eth") or 0.0)
                if interaction_amount > 0:
                    relative_diff = abs(value_eth - interaction_amount) / max(interaction_amount, 1e-9)
                    if relative_diff > amount_tolerance:
                        continue
                if not context.is_fresh_address(
                    target,
                    observed_at=edge_ts,
                    max_age_seconds=max_gap,
                ):
                    continue
                concealment_edges.append(
                    {
                        "tx_hash": str(edge.get("tx_hash") or ""),
                        "from_address": str(edge.get("from_address") or "").lower().strip(),
                        "to_address": target,
                        "value_eth": round(value_eth, 8),
                        "timestamp": edge_ts,
                    }
                )
        return concealment_edges

    def _delay_score(self, interactions: list[dict[str, Any]], max_gap: int) -> float:
        if len(interactions) < 2:
            return 0.5
        ordered = sorted(interactions, key=lambda item: (item["timestamp"], item["tx_hash"]))
        gaps = [
            max(0.0, float(ordered[index]["timestamp"]) - float(ordered[index - 1]["timestamp"]))
            for index in range(1, len(ordered))
        ]
        if not gaps:
            return 0.5
        return statistics.fmean(math.exp(-gap / max_gap) for gap in gaps)
