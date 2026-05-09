"""High-depth transaction-chaining detector."""

from __future__ import annotations

import math
import statistics
from typing import Any

import networkx as nx

from ..types import DetectorHit, DetectorOutput, EvidenceRecord, LayeringContext, clamp, iso_from_ts, stable_evidence_id


class HighDepthTransactionChainingDetector:
    detector_type = "high_depth_transaction_chaining"

    def detect(self, context: LayeringContext) -> DetectorOutput:
        output = DetectorOutput()
        max_hops = max(2, int(context.cfg.layering_depth_max_hops or 6))
        min_hops = max(2, int(context.cfg.layering_depth_min_hops or 4))
        branching_limit = max(1, int(context.cfg.layering_depth_branching_limit or 3))
        min_retention = max(0.05, float(context.cfg.layering_depth_min_value_retention or 0.55))
        max_latency = max(300, int(context.cfg.layering_depth_max_latency_seconds or 86400))
        min_score = max(0.01, float(context.cfg.layering_depth_min_score or 0.58))

        for seed in sorted(context.seeds.values(), key=lambda item: item.entity_id):
            relevant_nodes = self._expand_relevant_nodes(context, seed.addresses, max_hops=max_hops, max_nodes=80)
            graph = self._build_weighted_graph(context, relevant_nodes)
            if graph.number_of_edges() == 0:
                continue

            personalization = {
                address: 1.0 / len(seed.addresses)
                for address in seed.addresses
                if graph.has_node(address)
            }
            if not personalization:
                continue
            ppr = nx.pagerank(graph, alpha=0.85, personalization=personalization, weight="weight")

            paths: list[dict[str, Any]] = []
            for start in sorted(personalization):
                self._walk_paths(
                    context,
                    current=start,
                    visited=[start],
                    prior_value=None,
                    prior_ts=None,
                    ppr=ppr,
                    branching_limit=branching_limit,
                    max_hops=max_hops,
                    min_retention=min_retention,
                    max_latency=max_latency,
                    paths=paths,
                )

            qualifying = [path for path in paths if path["depth"] >= min_hops and path["score"] >= min_score]
            if not qualifying:
                continue

            qualifying.sort(key=lambda item: (item["score"], item["depth"], -item["average_branch_factor"]), reverse=True)
            top_paths = qualifying[:3]
            tx_hashes = sorted({tx_hash for path in top_paths for tx_hash in path["tx_hashes"]})
            earliest_ts = min(path["first_ts"] for path in top_paths)
            latest_ts = max(path["last_ts"] for path in top_paths)
            evidence_id = stable_evidence_id(seed.entity_id, self.detector_type, 1)
            metrics = {
                "max_depth": max(path["depth"] for path in top_paths),
                "path_count": len(qualifying),
                "average_hop_latency_seconds": round(
                    statistics.fmean(path["average_hop_latency_seconds"] for path in top_paths),
                    2,
                ),
                "average_branch_factor": round(
                    statistics.fmean(path["average_branch_factor"] for path in top_paths),
                    4,
                ),
                "top_paths": top_paths,
            }
            output.evidence.append(
                EvidenceRecord(
                    evidence_id=evidence_id,
                    entity_id=seed.entity_id,
                    detector_type=self.detector_type,
                    evidence_type="path",
                    title="High-depth forwarding chain",
                    summary=(
                        f"Detected {len(qualifying)} forwarding paths with depth up to {metrics['max_depth']} hops."
                    ),
                    entity_ids=[seed.entity_id],
                    tx_hashes=tx_hashes,
                    path=top_paths[0]["path"],
                    metrics=metrics,
                    first_seen_at=iso_from_ts(earliest_ts),
                    last_seen_at=iso_from_ts(latest_ts),
                )
            )
            output.hits.append(
                DetectorHit(
                    entity_id=seed.entity_id,
                    entity_type=seed.entity_type,
                    detector_type=self.detector_type,
                    confidence_score=round(top_paths[0]["score"], 4),
                    summary="Funds were forwarded through a long, value-retaining chain with consistent hop timing.",
                    score_components=top_paths[0]["score_components"],
                    metrics=metrics,
                    supporting_tx_hashes=tx_hashes,
                    evidence_ids=[evidence_id],
                    first_observed_at=iso_from_ts(earliest_ts),
                    last_observed_at=iso_from_ts(latest_ts),
                )
            )

        return output

    def _expand_relevant_nodes(
        self,
        context: LayeringContext,
        seed_addresses: list[str],
        max_hops: int,
        max_nodes: int,
    ) -> set[str]:
        frontier = list(seed_addresses)
        visited = {address.lower().strip() for address in seed_addresses if address}
        for _ in range(max_hops):
            next_frontier: list[str] = []
            for address in frontier:
                neighbors = [
                    str(edge.get("to_address") or "").lower().strip()
                    for edge in context.artifacts.outgoing_edges.get(address, [])
                ]
                for neighbor in neighbors:
                    if not neighbor or neighbor in visited:
                        continue
                    visited.add(neighbor)
                    next_frontier.append(neighbor)
                    if len(visited) >= max_nodes:
                        return visited
            frontier = next_frontier
            if not frontier:
                break
        return visited

    def _build_weighted_graph(self, context: LayeringContext, nodes: set[str]) -> nx.DiGraph:
        graph = nx.DiGraph()
        for tx in context.transactions:
            if tx.from_address not in nodes or tx.to_address not in nodes:
                continue
            existing = graph.get_edge_data(tx.from_address, tx.to_address, default={"weight": 0.0})
            graph.add_edge(
                tx.from_address,
                tx.to_address,
                weight=float(existing.get("weight") or 0.0) + float(tx.value_eth or 0.0) + 1.0,
            )
        return graph

    def _walk_paths(
        self,
        context: LayeringContext,
        current: str,
        visited: list[str],
        prior_value: float | None,
        prior_ts: float | None,
        ppr: dict[str, float],
        branching_limit: int,
        max_hops: int,
        min_retention: float,
        max_latency: int,
        paths: list[dict[str, Any]],
    ) -> None:
        if len(visited) - 1 >= max_hops:
            self._record_path(context, visited, ppr, paths)
            return

        candidates: list[tuple[float, dict[str, Any], float, float]] = []
        for edge in context.artifacts.outgoing_edges.get(current, []):
            target = str(edge.get("to_address") or "").lower().strip()
            if not target or target in visited:
                continue
            edge_value = float(edge.get("value_eth") or 0.0)
            edge_ts = float(edge.get("timestamp") or 0.0)
            if prior_value is not None:
                retention = edge_value / max(prior_value, 1e-9)
                if retention < min_retention:
                    continue
            else:
                retention = 1.0
            if prior_ts is not None:
                gap = edge_ts - prior_ts
                if gap < 0 or gap > max_latency:
                    continue
            else:
                gap = 0.0
            score = ppr.get(target, 0.0) * retention * math.exp(-gap / max_latency)
            candidates.append((score, edge, retention, gap))

        if not candidates:
            if len(visited) > 1:
                self._record_path(context, visited, ppr, paths)
            return

        candidates.sort(key=lambda item: (item[0], item[1].get("value_eth"), item[1].get("timestamp")), reverse=True)
        for _, edge, _, _ in candidates[:branching_limit]:
            target = str(edge.get("to_address") or "").lower().strip()
            self._walk_paths(
                context,
                current=target,
                visited=[*visited, target],
                prior_value=float(edge.get("value_eth") or 0.0),
                prior_ts=float(edge.get("timestamp") or 0.0),
                ppr=ppr,
                branching_limit=branching_limit,
                max_hops=max_hops,
                min_retention=min_retention,
                max_latency=max_latency,
                paths=paths,
            )

    def _record_path(
        self,
        context: LayeringContext,
        path: list[str],
        ppr: dict[str, float],
        paths: list[dict[str, Any]],
    ) -> None:
        if len(path) < 2:
            return
        tx_hashes: list[str] = []
        edge_values: list[float] = []
        latencies: list[float] = []
        branch_counts: list[int] = []
        timestamps: list[float] = []

        for source, target in zip(path, path[1:]):
            candidates = [
                edge
                for edge in context.artifacts.outgoing_edges.get(source, [])
                if str(edge.get("to_address") or "").lower().strip() == target
            ]
            if not candidates:
                return
            edge = sorted(
                candidates,
                key=lambda item: (float(item.get("timestamp") or 0.0), str(item.get("tx_hash") or "")),
            )[0]
            tx_hash = str(edge.get("tx_hash") or "")
            if tx_hash:
                tx_hashes.append(tx_hash)
            value = float(edge.get("value_eth") or 0.0)
            edge_values.append(value)
            timestamps.append(float(edge.get("timestamp") or 0.0))
            branch_counts.append(len(context.artifacts.outgoing_edges.get(source, [])))

        retentions = [
            edge_values[index] / max(edge_values[index - 1], 1e-9)
            for index in range(1, len(edge_values))
        ]
        latencies = [
            max(0.0, timestamps[index] - timestamps[index - 1])
            for index in range(1, len(timestamps))
        ]
        depth = len(path) - 1
        depth_score = min(1.0, depth / max(1, int(context.cfg.layering_depth_max_hops or 6)))
        retention_score = statistics.fmean(min(1.0, value) for value in retentions) if retentions else 1.0
        continuity_score = (
            statistics.fmean(math.exp(-latency / max(1, int(context.cfg.layering_depth_max_latency_seconds or 86400))) for latency in latencies)
            if latencies
            else 1.0
        )
        average_branch_factor = statistics.fmean(branch_counts) if branch_counts else 1.0
        forwarding_score = clamp(1.0 - max(0.0, average_branch_factor - 1.0) / max(1.0, float(context.cfg.layering_depth_branching_limit or 3)))
        max_ppr = max(ppr.values()) if ppr else 1.0
        ppr_score = statistics.fmean(ppr.get(node, 0.0) / max(max_ppr, 1e-9) for node in path)
        service_penalty = 0.75 if context.is_exchange_like(path[-1]) else 1.0
        score = clamp(
            (
                0.25 * depth_score
                + 0.25 * retention_score
                + 0.20 * continuity_score
                + 0.15 * forwarding_score
                + 0.15 * ppr_score
            )
            * service_penalty
        )

        paths.append(
            {
                "path": list(path),
                "depth": depth,
                "tx_hashes": tx_hashes,
                "first_ts": timestamps[0] if timestamps else 0.0,
                "last_ts": timestamps[-1] if timestamps else 0.0,
                "average_hop_latency_seconds": statistics.fmean(latencies) if latencies else 0.0,
                "average_branch_factor": average_branch_factor,
                "score": score,
                "score_components": {
                    "depth": round(depth_score, 4),
                    "value_retention": round(retention_score, 4),
                    "time_continuity": round(continuity_score, 4),
                    "forwarding_consistency": round(forwarding_score, 4),
                    "pagerank_relevance": round(ppr_score, 4),
                },
            }
        )
