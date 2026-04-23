"""Shell-wallet community detector."""

from __future__ import annotations

from collections import deque
import math
import statistics
from typing import Any

import networkx as nx

from ..types import DetectorHit, DetectorOutput, EvidenceRecord, LayeringContext, clamp, iso_from_ts, stable_evidence_id


class ShellWalletNetworkDetector:
    detector_type = "shell_wallet_network"

    def detect(self, context: LayeringContext) -> DetectorOutput:
        output = DetectorOutput()
        window_seconds = max(60, int(context.cfg.layering_shell_window_seconds or 43200))
        min_size = max(3, int(context.cfg.layering_shell_min_community_size or 4))
        min_internal_ratio = max(0.5, float(context.cfg.layering_shell_min_internal_ratio or 0.72))
        min_density = max(0.05, float(context.cfg.layering_shell_min_density or 0.28))
        min_windows = max(1, int(context.cfg.layering_shell_min_temporal_windows or 2))
        pass_through_window = max(300, int(context.cfg.clustering_pass_through_window_seconds or 1800))

        for seed in sorted(context.seeds.values(), key=lambda item: item.entity_id):
            neighborhood = self._seed_neighborhood(context, seed.addresses, max_hops=2, max_nodes=60)
            if len(neighborhood) < min_size:
                continue
            relevant_txs = [
                tx
                for tx in context.transactions
                if tx.from_address in neighborhood
                and tx.to_address in neighborhood
                and not context.is_service_address(tx.from_address)
                and not context.is_service_address(tx.to_address)
            ]
            if len(relevant_txs) < min_size:
                continue

            timestamps = sorted(float(tx.timestamp or 0.0) for tx in relevant_txs)
            if not timestamps:
                continue
            windows = self._build_windows(timestamps, window_seconds)
            candidates: list[dict[str, Any]] = []
            for window_start, window_end in windows:
                window_txs = [
                    tx
                    for tx in relevant_txs
                    if window_start <= float(tx.timestamp or 0.0) <= window_end
                ]
                if len(window_txs) < min_size:
                    continue
                community = self._find_seed_community(
                    context,
                    seed_addresses=set(seed.addresses),
                    window_txs=window_txs,
                    min_size=min_size,
                    pass_through_window=pass_through_window,
                )
                if community is None:
                    continue
                if community["internal_ratio"] < min_internal_ratio or community["density"] < min_density:
                    continue
                candidates.append(community)

            grouped = self._group_candidates(candidates)
            best_group = None
            for group in grouped:
                if group["windows"] < min_windows:
                    continue
                if best_group is None or group["score"] > best_group["score"]:
                    best_group = group
            if best_group is None:
                continue

            temporal_score = min(1.0, best_group["windows"] / max(1, len(windows)))
            density_score = clamp(best_group["density"] / min_density)
            internal_ratio_score = clamp(best_group["internal_ratio"] / min_internal_ratio)
            movement_score = clamp(best_group["layering_motion"] / 0.5)
            size_score = min(1.0, len(best_group["community"]) / float(min_size + 2))
            confidence = clamp(
                0.30 * internal_ratio_score
                + 0.25 * density_score
                + 0.20 * temporal_score
                + 0.15 * movement_score
                + 0.10 * size_score
            )

            evidence_id = stable_evidence_id(seed.entity_id, self.detector_type, 1)
            supporting_tx_hashes = sorted(best_group["tx_hashes"])
            output.evidence.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    entity_id=seed.entity_id,
                    detector_type=self.detector_type,
                    evidence_type="community",
                    title="Dense shell-wallet community",
                    summary=(
                        f"Detected a {len(best_group['community'])}-wallet community with high internal transfer density across {best_group['windows']} windows."
                    ),
                    entity_ids=[seed.entity_id],
                    tx_hashes=supporting_tx_hashes,
                    path=sorted(best_group["community"])[:12],
                    metrics={
                        "community_size": len(best_group["community"]),
                        "internal_ratio": round(best_group["internal_ratio"], 4),
                        "density": round(best_group["density"], 4),
                        "layering_motion": round(best_group["layering_motion"], 4),
                        "temporal_windows": best_group["windows"],
                    },
                    first_seen_at=iso_from_ts(best_group["first_ts"]),
                    last_seen_at=iso_from_ts(best_group["last_ts"]),
                )
            )
            output.hits.append(
                DetectorHit(
                    entity_id=seed.entity_id,
                    entity_type=seed.entity_type,
                    detector_type=self.detector_type,
                    confidence_score=round(confidence, 4),
                    summary="Seed entity is embedded in a dense, temporally persistent shell-wallet network.",
                    score_components={
                        "internal_ratio": round(internal_ratio_score, 4),
                        "density": round(density_score, 4),
                        "temporal_consistency": round(temporal_score, 4),
                        "layering_motion": round(movement_score, 4),
                    },
                    metrics={
                        "community_size": len(best_group["community"]),
                        "community_addresses": sorted(best_group["community"]),
                        "temporal_windows": best_group["windows"],
                        "internal_ratio": round(best_group["internal_ratio"], 4),
                        "density": round(best_group["density"], 4),
                    },
                    supporting_tx_hashes=supporting_tx_hashes,
                    evidence_ids=[evidence_id],
                    first_observed_at=iso_from_ts(best_group["first_ts"]),
                    last_observed_at=iso_from_ts(best_group["last_ts"]),
                )
            )

        return output

    def _seed_neighborhood(
        self,
        context: LayeringContext,
        seed_addresses: list[str],
        max_hops: int,
        max_nodes: int,
    ) -> set[str]:
        queue = deque((address.lower().strip(), 0) for address in seed_addresses)
        visited = {address.lower().strip() for address in seed_addresses if address}
        while queue and len(visited) < max_nodes:
            current, depth = queue.popleft()
            if depth >= max_hops:
                continue
            neighbors = {
                str(edge.get("to_address") or "").lower().strip()
                for edge in context.artifacts.outgoing_edges.get(current, [])
            } | {
                str(edge.get("from_address") or "").lower().strip()
                for edge in context.artifacts.incoming_edges.get(current, [])
            }
            for neighbor in sorted(neighbors):
                if not neighbor or neighbor in visited:
                    continue
                if context.is_service_address(neighbor) and neighbor not in seed_addresses:
                    continue
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))
                if len(visited) >= max_nodes:
                    break
        return visited

    def _build_windows(self, timestamps: list[float], window_seconds: int) -> list[tuple[float, float]]:
        if not timestamps:
            return []
        start = timestamps[0]
        end = timestamps[-1]
        if end - start <= window_seconds:
            return [(start, end)]
        windows: list[tuple[float, float]] = []
        step = max(window_seconds // 2, 1)
        current = start
        while current <= end:
            windows.append((current, current + window_seconds))
            current += step
        return windows

    def _find_seed_community(
        self,
        context: LayeringContext,
        seed_addresses: set[str],
        window_txs: list[Any],
        min_size: int,
        pass_through_window: int,
    ) -> dict[str, Any] | None:
        undirected = nx.Graph()
        for tx in window_txs:
            left = tx.from_address
            right = tx.to_address
            if not left or not right or left == right:
                continue
            existing = undirected.get_edge_data(left, right, default={"weight": 0.0})
            undirected.add_edge(
                left,
                right,
                weight=float(existing.get("weight") or 0.0) + 1.0 + math.log1p(float(tx.value_eth or 0.0)),
            )

        if undirected.number_of_nodes() < min_size or undirected.number_of_edges() < min_size - 1:
            return None

        try:
            communities = list(nx.community.louvain_communities(undirected, weight="weight", seed=0))
        except Exception:
            communities = list(nx.community.greedy_modularity_communities(undirected, weight="weight"))
        communities.extend(nx.connected_components(undirected))

        best: dict[str, Any] | None = None
        for community in communities:
            community_nodes = {str(node).lower().strip() for node in community}
            if len(community_nodes) < min_size:
                continue
            if not community_nodes & seed_addresses:
                continue
            internal_txs = [
                tx
                for tx in window_txs
                if tx.from_address in community_nodes and tx.to_address in community_nodes
            ]
            external_txs = [
                tx
                for tx in window_txs
                if (tx.from_address in community_nodes) ^ (tx.to_address in community_nodes)
            ]
            internal_value = sum(float(tx.value_eth or 0.0) for tx in internal_txs)
            external_value = sum(float(tx.value_eth or 0.0) for tx in external_txs)
            density = len(internal_txs) / max(1, len(community_nodes) * max(1, len(community_nodes) - 1))
            internal_ratio = internal_value / max(internal_value + external_value, 1e-9)
            motion = self._layering_motion(community_nodes, window_txs, pass_through_window)
            score = (0.45 * internal_ratio) + (0.35 * density) + (0.20 * motion)
            candidate = {
                "community": community_nodes,
                "internal_ratio": internal_ratio,
                "density": density,
                "layering_motion": motion,
                "score": score,
                "tx_hashes": {
                    str(tx.tx_hash or "")
                    for tx in internal_txs
                    if str(tx.tx_hash or "").strip()
                },
                "first_ts": min((float(tx.timestamp or 0.0) for tx in internal_txs), default=0.0),
                "last_ts": max((float(tx.timestamp or 0.0) for tx in internal_txs), default=0.0),
            }
            if best is None or candidate["score"] > best["score"]:
                best = candidate

        return best

    def _layering_motion(self, community_nodes: set[str], window_txs: list[Any], pass_through_window: int) -> float:
        forwardable = 0
        internal_txs = [
            tx
            for tx in window_txs
            if tx.from_address in community_nodes and tx.to_address in community_nodes
        ]
        for tx in internal_txs:
            recipient = tx.to_address
            tx_ts = float(tx.timestamp or 0.0)
            if any(
                candidate.from_address == recipient
                and candidate.to_address in community_nodes
                and 0 <= float(candidate.timestamp or 0.0) - tx_ts <= pass_through_window
                for candidate in window_txs
            ):
                forwardable += 1
        if not internal_txs:
            return 0.0
        return forwardable / len(internal_txs)

    def _group_candidates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        groups: list[dict[str, Any]] = []
        for candidate in sorted(candidates, key=lambda item: item["score"], reverse=True):
            placed = False
            for group in groups:
                overlap = len(candidate["community"] & group["community"])
                union = len(candidate["community"] | group["community"])
                jaccard = overlap / max(1, union)
                if jaccard < 0.5:
                    continue
                group["community"].update(candidate["community"])
                group["windows"] += 1
                group["score"] += candidate["score"]
                group["internal_ratio_values"].append(candidate["internal_ratio"])
                group["density_values"].append(candidate["density"])
                group["motion_values"].append(candidate["layering_motion"])
                group["tx_hashes"].update(candidate["tx_hashes"])
                group["first_ts"] = min(group["first_ts"], candidate["first_ts"])
                group["last_ts"] = max(group["last_ts"], candidate["last_ts"])
                placed = True
                break
            if placed:
                continue
            groups.append(
                {
                    "community": set(candidate["community"]),
                    "windows": 1,
                    "score": candidate["score"],
                    "internal_ratio_values": [candidate["internal_ratio"]],
                    "density_values": [candidate["density"]],
                    "motion_values": [candidate["layering_motion"]],
                    "tx_hashes": set(candidate["tx_hashes"]),
                    "first_ts": candidate["first_ts"],
                    "last_ts": candidate["last_ts"],
                }
            )

        for group in groups:
            group["internal_ratio"] = statistics.fmean(group["internal_ratio_values"])
            group["density"] = statistics.fmean(group["density_values"])
            group["layering_motion"] = statistics.fmean(group["motion_values"])
        return groups
