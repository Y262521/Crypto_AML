"""Placement-only AML analytics for Ethereum transaction flows."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from itertools import combinations
import json
import logging
import math
from typing import Any

import networkx as nx
from sqlalchemy import text

from ..clustering.base import TxRecord
from ..clustering.engine import ClusteringEngine
from ..clustering.graph_builder import GraphArtifacts, build_graph_artifacts
from ..clustering.policy import should_merge_pair
from ..clustering.union_find import UnionFind
from ..config import Config, load_config
from ..etl.load.mariadb_loader import create_tables_if_not_exist
from ..utils.connections import get_maria_engine

logger = logging.getLogger(__name__)

_SUSPICIOUS_BEHAVIOR_THRESHOLD = 0.55
_ACTIONABLE_POI_THRESHOLD = 0.65
_TRACE_MIN_CONFIDENCE = 0.25


@dataclass
class PlacementEntity:
    entity_id: str
    entity_type: str
    addresses: list[str]
    validation_status: str
    validation_confidence: float
    source_kind: str
    source_cluster_ids: list[str]
    first_seen_at: float = 0.0
    last_seen_at: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityTransaction:
    tx_hash: str
    from_address: str
    to_address: str
    source_entity_id: str
    target_entity_id: str
    value_eth: float
    timestamp: float
    block_number: int


@dataclass
class EntityEdge:
    source_entity_id: str
    target_entity_id: str
    tx_hashes: list[str]
    total_value_eth: float
    tx_count: int
    first_seen_at: float
    last_seen_at: float


@dataclass
class EntityProfile:
    entity: PlacementEntity
    incoming_transactions: list[EntityTransaction] = field(default_factory=list)
    outgoing_transactions: list[EntityTransaction] = field(default_factory=list)
    internal_transactions: list[EntityTransaction] = field(default_factory=list)
    incoming_entities: set[str] = field(default_factory=set)
    outgoing_entities: set[str] = field(default_factory=set)
    total_in: float = 0.0
    total_out: float = 0.0
    total_internal: float = 0.0

    @property
    def total_tx_count(self) -> int:
        return (
            len(self.incoming_transactions)
            + len(self.outgoing_transactions)
            + len(self.internal_transactions)
        )


@dataclass
class BehaviorDetection:
    entity_id: str
    entity_type: str
    behavior_type: str
    confidence_score: float
    supporting_metrics: dict[str, Any]
    supporting_tx_hashes: list[str]
    first_observed_at: str | None
    last_observed_at: str | None


@dataclass
class TracePath:
    root_entity_id: str
    origin_entity_id: str
    entity_ids: list[str]
    score: float
    terminal_reason: str
    edge_tx_hashes: list[list[str]]
    path_index: int = 0


@dataclass
class PlacementDetection:
    entity_id: str
    entity_type: str
    addresses: list[str]
    confidence_score: float
    placement_score: float
    behavior_score: float
    graph_position_score: float
    temporal_score: float
    behaviors: list[str]
    reasons: list[str]
    linked_root_entities: list[str]
    trace_path_count: int
    supporting_tx_hashes: list[str]
    validation_status: str
    validation_confidence: float
    first_seen_at: str | None
    last_seen_at: str | None
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityLabel:
    entity_id: str
    entity_type: str
    label: str
    source: str
    confidence_score: float
    explanation: str


@dataclass
class InvestigationPoi:
    poi_id: str
    entity_id: str
    entity_type: str
    risk_score: float
    reason: str
    linked_behaviors: list[str]
    supporting_evidence: dict[str, Any]


@dataclass
class PlacementAnalysisResult:
    run_id: str
    generated_at: str
    summary: dict[str, Any]
    entities: list[PlacementEntity]
    behaviors: list[BehaviorDetection]
    trace_paths: list[TracePath]
    placements: list[PlacementDetection]
    labels: list[EntityLabel]
    pois: list[InvestigationPoi]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "summary": self.summary,
            "entities": [_serialize_entity(entity) for entity in self.entities],
            "behaviors": [_serialize_behavior(behavior) for behavior in self.behaviors],
            "trace_paths": [_serialize_trace(path) for path in self.trace_paths],
            "placements": [_serialize_placement(placement) for placement in self.placements],
            "labels": [_serialize_label(label) for label in self.labels],
            "pois": [_serialize_poi(poi) for poi in self.pois],
        }


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _dt_from_ts(value: float | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(float(value), tz=timezone.utc).replace(tzinfo=None)


def _iso_from_ts(value: float | None) -> str | None:
    if not value:
        return None
    return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _chunked(items: list[Any], size: int = 500):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _stable_cluster_id(addresses: list[str], prefix: str = "PCL") -> str:
    digest = hashlib.sha1("|".join(sorted(addresses)).encode()).hexdigest()[:12].upper()
    return f"{prefix}-{digest}"


def _stable_run_id(generated_at: datetime) -> str:
    seed = generated_at.isoformat()
    digest = hashlib.sha1(seed.encode()).hexdigest()[:8].upper()
    return f"PLR-{generated_at.strftime('%Y%m%d%H%M%S')}-{digest}"


def _relative_variance(values: list[float]) -> float:
    clean = [float(value) for value in values if float(value) > 0]
    if len(clean) < 2:
        return 0.0
    avg = sum(clean) / len(clean)
    if avg <= 0:
        return 0.0
    variance = sum((value - avg) ** 2 for value in clean) / len(clean)
    return math.sqrt(variance) / avg


def _behavior_sort_key(detection: BehaviorDetection) -> tuple[float, str]:
    return (detection.confidence_score, detection.behavior_type)


def _serialize_entity(entity: PlacementEntity) -> dict[str, Any]:
    return {
        "entity_id": entity.entity_id,
        "entity_type": entity.entity_type,
        "addresses": entity.addresses,
        "validation_status": entity.validation_status,
        "validation_confidence": entity.validation_confidence,
        "source_kind": entity.source_kind,
        "source_cluster_ids": entity.source_cluster_ids,
        "first_seen_at": _iso_from_ts(entity.first_seen_at),
        "last_seen_at": _iso_from_ts(entity.last_seen_at),
        "metrics": entity.metrics,
    }


def _serialize_behavior(behavior: BehaviorDetection) -> dict[str, Any]:
    return {
        "entity_id": behavior.entity_id,
        "entity_type": behavior.entity_type,
        "behavior_type": behavior.behavior_type,
        "confidence_score": behavior.confidence_score,
        "supporting_metrics": behavior.supporting_metrics,
        "supporting_tx_hashes": behavior.supporting_tx_hashes,
        "first_observed_at": behavior.first_observed_at,
        "last_observed_at": behavior.last_observed_at,
    }


def _serialize_trace(path: TracePath) -> dict[str, Any]:
    return {
        "path_index": path.path_index,
        "root_entity_id": path.root_entity_id,
        "origin_entity_id": path.origin_entity_id,
        "entity_ids": path.entity_ids,
        "score": path.score,
        "terminal_reason": path.terminal_reason,
        "edge_tx_hashes": path.edge_tx_hashes,
    }


def _serialize_placement(placement: PlacementDetection) -> dict[str, Any]:
    return {
        "entity_id": placement.entity_id,
        "entity_type": placement.entity_type,
        "addresses": placement.addresses,
        "confidence_score": placement.confidence_score,
        "placement_score": placement.placement_score,
        "behavior_score": placement.behavior_score,
        "graph_position_score": placement.graph_position_score,
        "temporal_score": placement.temporal_score,
        "behaviors": placement.behaviors,
        "reasons": placement.reasons,
        "linked_root_entities": placement.linked_root_entities,
        "trace_path_count": placement.trace_path_count,
        "supporting_tx_hashes": placement.supporting_tx_hashes,
        "validation_status": placement.validation_status,
        "validation_confidence": placement.validation_confidence,
        "first_seen_at": placement.first_seen_at,
        "last_seen_at": placement.last_seen_at,
        "metrics": placement.metrics,
    }


def _serialize_label(label: EntityLabel) -> dict[str, Any]:
    return {
        "entity_id": label.entity_id,
        "entity_type": label.entity_type,
        "label": label.label,
        "source": label.source,
        "confidence_score": label.confidence_score,
        "explanation": label.explanation,
    }


def _serialize_poi(poi: InvestigationPoi) -> dict[str, Any]:
    return {
        "poi_id": poi.poi_id,
        "entity_id": poi.entity_id,
        "entity_type": poi.entity_type,
        "risk_score": poi.risk_score,
        "reason": poi.reason,
        "linked_behaviors": poi.linked_behaviors,
        "supporting_evidence": poi.supporting_evidence,
    }


class PlacementAnalysisEngine:
    """Run the placement-only AML pipeline on Ethereum transaction flows."""

    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or load_config()
        self.clustering_engine = ClusteringEngine(cfg=self.cfg)

    def run(self, source: str = "auto", persist: bool = False) -> PlacementAnalysisResult:
        transactions = self._load_transactions(source=source)
        generated_at = datetime.now(timezone.utc)
        run_id = _stable_run_id(generated_at)

        if not transactions:
            result = PlacementAnalysisResult(
                run_id=run_id,
                generated_at=generated_at.isoformat(),
                summary={
                    "source": source,
                    "transactions": 0,
                    "entities": 0,
                    "behaviors": {},
                    "placements": 0,
                    "pois": 0,
                },
                entities=[],
                behaviors=[],
                trace_paths=[],
                placements=[],
                labels=[],
                pois=[],
            )
            if persist:
                self._persist(result, {}, {}, [])
            return result

        artifacts = build_graph_artifacts(transactions)
        entities, address_to_entity = self._resolve_entities(transactions, artifacts)
        profiles, entity_edges, incoming_entity_edges, outgoing_entity_edges = self._build_entity_profiles(
            transactions,
            entities,
            address_to_entity,
        )
        behaviors = self._detect_behaviors(profiles)
        behavior_map: dict[str, list[BehaviorDetection]] = defaultdict(list)
        for detection in behaviors:
            behavior_map[detection.entity_id].append(detection)
        for entity_detections in behavior_map.values():
            entity_detections.sort(key=_behavior_sort_key, reverse=True)

        trace_paths = self._trace_suspicious_entities(
            profiles,
            behavior_map,
            incoming_entity_edges,
            outgoing_entity_edges,
        )
        for index, path in enumerate(trace_paths, start=1):
            path.path_index = index

        placements = self._identify_placements(
            profiles,
            behavior_map,
            trace_paths,
            incoming_entity_edges,
        )
        labels = self._assign_labels(profiles, behavior_map, trace_paths, placements)
        pois = self._build_pois(placements)
        summary = self._build_summary(
            source=source,
            transactions=transactions,
            entities=entities,
            behaviors=behaviors,
            placements=placements,
            labels=labels,
            pois=pois,
        )

        result = PlacementAnalysisResult(
            run_id=run_id,
            generated_at=generated_at.isoformat(),
            summary=summary,
            entities=sorted(entities.values(), key=lambda entity: (entity.entity_type, entity.entity_id)),
            behaviors=sorted(behaviors, key=_behavior_sort_key, reverse=True),
            trace_paths=sorted(trace_paths, key=lambda path: (path.score, len(path.entity_ids)), reverse=True),
            placements=sorted(
                placements,
                key=lambda placement: (placement.placement_score, placement.confidence_score, placement.entity_id),
                reverse=True,
            ),
            labels=sorted(labels, key=lambda label: (label.label, label.entity_id)),
            pois=sorted(pois, key=lambda poi: (poi.risk_score, poi.entity_id), reverse=True),
        )

        if persist:
            self._persist(result, profiles, entity_edges, trace_paths)

        return result

    def _load_transactions(self, source: str) -> list[TxRecord]:
        transactions = list(self.clustering_engine.adapter.iter_transactions(source=source))
        transactions.sort(key=lambda tx: (float(tx.timestamp or 0.0), tx.tx_hash))
        logger.info("Placement analysis loaded %d transactions", len(transactions))
        return transactions

    def _load_existing_cluster_map(self) -> dict[str, str]:
        try:
            engine = get_maria_engine(self.cfg)
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        """
                        SELECT address, cluster_id
                        FROM addresses
                        WHERE cluster_id IS NOT NULL
                          AND cluster_id <> ''
                        """
                    )
                ).mappings().all()
            return {
                str(row["address"]).lower().strip(): str(row["cluster_id"])
                for row in rows
                if row.get("address") and row.get("cluster_id")
            }
        except Exception as exc:
            logger.info("Placement analysis could not load existing clusters: %s", exc)
            return {}
        finally:
            if "engine" in locals():
                engine.dispose()

    def _resolve_entities(
        self,
        transactions: list[TxRecord],
        artifacts: GraphArtifacts,
    ) -> tuple[dict[str, PlacementEntity], dict[str, str]]:
        addresses = sorted(
            {
                address
                for tx in transactions
                for address in (tx.from_address, tx.to_address)
                if address
            }
        )
        existing_cluster_map = self._load_existing_cluster_map()
        seed_members: dict[str, set[str]] = defaultdict(set)
        seed_for_address: dict[str, str] = {}

        for address in addresses:
            cluster_id = existing_cluster_map.get(address)
            seed_id = cluster_id or f"ADDR::{address}"
            seed_for_address[address] = seed_id
            seed_members[seed_id].add(address)

        merge_signals: dict[tuple[str, str], set[str]] = defaultdict(set)
        pair_heuristics = self.clustering_engine._find_pair_heuristics(artifacts.graph)
        for (left, right), heuristics in pair_heuristics.items():
            if left not in seed_for_address or right not in seed_for_address:
                continue
            if not should_merge_pair(
                heuristics,
                min_support=self.cfg.clustering_min_heuristic_support,
            ):
                continue
            left_seed = seed_for_address[left]
            right_seed = seed_for_address[right]
            if left_seed == right_seed:
                continue
            merge_signals[tuple(sorted((left_seed, right_seed)))].update(heuristics)

        max_component_size = max(10, int(self.cfg.clustering_max_pattern_size or 100))
        for component in nx.strongly_connected_components(artifacts.graph):
            members = [address for address in component if address in seed_for_address]
            if len(members) < 2 or len(members) > max_component_size:
                continue
            seeds = sorted({seed_for_address[address] for address in members})
            if len(seeds) < 2:
                continue
            for left_seed, right_seed in combinations(seeds, 2):
                merge_signals[(left_seed, right_seed)].add("strong_connectivity")

        uf = UnionFind(sorted(seed_members))
        accepted_signals: dict[tuple[str, str], set[str]] = {}
        for seed_pair, signals in merge_signals.items():
            if self._should_merge_validation_pair(signals):
                uf.union(seed_pair[0], seed_pair[1])
                accepted_signals[seed_pair] = set(signals)

        grouped_addresses: dict[str, set[str]] = defaultdict(set)
        grouped_source_clusters: dict[str, set[str]] = defaultdict(set)
        grouped_signals: dict[str, set[str]] = defaultdict(set)
        original_cluster_members: dict[str, set[str]] = defaultdict(set)
        for address, cluster_id in existing_cluster_map.items():
            if address in seed_for_address:
                original_cluster_members[cluster_id].add(address)

        for address, seed_id in seed_for_address.items():
            root = uf.find(seed_id)
            grouped_addresses[root].add(address)
            if seed_id.startswith("ADDR::"):
                continue
            grouped_source_clusters[root].add(seed_id)

        for (left_seed, right_seed), signals in accepted_signals.items():
            root = uf.find(left_seed)
            grouped_signals[root].update(signals)

        entities: dict[str, PlacementEntity] = {}
        address_to_entity: dict[str, str] = {}

        for root, grouped in grouped_addresses.items():
            member_addresses = sorted(grouped)
            source_cluster_ids = sorted(grouped_source_clusters.get(root, set()))
            signal_count = len(grouped_signals.get(root, set()))
            if not source_cluster_ids and len(member_addresses) == 1:
                entity_id = member_addresses[0]
                entity_type = "address"
                source_kind = "address_fallback"
                validation_status = "address_fallback"
            elif source_cluster_ids and len(source_cluster_ids) == 1:
                source_cluster_id = source_cluster_ids[0]
                original_members = sorted(original_cluster_members.get(source_cluster_id, set()))
                if original_members == member_addresses:
                    entity_id = source_cluster_id
                    entity_type = "cluster"
                    source_kind = "existing"
                    validation_status = "validated"
                else:
                    entity_id = _stable_cluster_id(member_addresses)
                    entity_type = "cluster"
                    source_kind = "enhanced"
                    validation_status = "enhanced"
            else:
                entity_id = _stable_cluster_id(member_addresses)
                entity_type = "cluster"
                source_kind = "enhanced" if source_cluster_ids else "generated"
                validation_status = "enhanced" if source_cluster_ids else "generated"

            validation_confidence = round(
                self._validation_confidence(
                    source_kind=source_kind,
                    cluster_size=len(member_addresses),
                    signal_count=signal_count,
                ),
                4,
            )
            entity = PlacementEntity(
                entity_id=entity_id,
                entity_type=entity_type,
                addresses=member_addresses,
                validation_status=validation_status,
                validation_confidence=validation_confidence,
                source_kind=source_kind,
                source_cluster_ids=source_cluster_ids,
                metrics={
                    "address_count": len(member_addresses),
                    "supporting_signals": sorted(grouped_signals.get(root, set())),
                    "source_cluster_count": len(source_cluster_ids),
                },
            )
            entities[entity.entity_id] = entity
            for address in member_addresses:
                address_to_entity[address] = entity.entity_id

        logger.info(
            "Placement entity resolution produced %d entities (%d existing clusters reused)",
            len(entities),
            sum(1 for entity in entities.values() if entity.source_kind == "existing"),
        )
        return entities, address_to_entity

    def _should_merge_validation_pair(self, signals: set[str]) -> bool:
        if should_merge_pair(signals, min_support=self.cfg.clustering_min_heuristic_support):
            return True
        return "strong_connectivity" in signals and len(signals) >= 2

    def _validation_confidence(self, source_kind: str, cluster_size: int, signal_count: int) -> float:
        base = {
            "existing": 0.82,
            "enhanced": 0.72,
            "generated": 0.64,
            "address_fallback": 0.48,
        }.get(source_kind, 0.6)
        size_bonus = min(0.12, max(0, cluster_size - 1) * 0.02)
        signal_bonus = min(0.16, signal_count * 0.04)
        return _clamp(base + size_bonus + signal_bonus)

    def _build_entity_profiles(
        self,
        transactions: list[TxRecord],
        entities: dict[str, PlacementEntity],
        address_to_entity: dict[str, str],
    ) -> tuple[
        dict[str, EntityProfile],
        dict[tuple[str, str], EntityEdge],
        dict[str, list[EntityEdge]],
        dict[str, list[EntityEdge]],
    ]:
        profiles = {
            entity_id: EntityProfile(entity=entity)
            for entity_id, entity in entities.items()
        }
        entity_edges: dict[tuple[str, str], EntityEdge] = {}

        for tx in transactions:
            if not tx.from_address or not tx.to_address:
                continue
            source_entity_id = address_to_entity.get(tx.from_address)
            target_entity_id = address_to_entity.get(tx.to_address)
            if not source_entity_id or not target_entity_id:
                continue

            entity_tx = EntityTransaction(
                tx_hash=tx.tx_hash,
                from_address=tx.from_address,
                to_address=tx.to_address,
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id,
                value_eth=float(tx.value_eth or 0.0),
                timestamp=float(tx.timestamp or 0.0),
                block_number=int(tx.block_number or 0),
            )
            source_profile = profiles[source_entity_id]
            target_profile = profiles[target_entity_id]

            for profile in (source_profile, target_profile):
                if profile.entity.first_seen_at == 0.0 or entity_tx.timestamp < profile.entity.first_seen_at:
                    profile.entity.first_seen_at = entity_tx.timestamp
                if entity_tx.timestamp > profile.entity.last_seen_at:
                    profile.entity.last_seen_at = entity_tx.timestamp

            if source_entity_id == target_entity_id:
                source_profile.internal_transactions.append(entity_tx)
                source_profile.total_internal += entity_tx.value_eth
                continue

            source_profile.outgoing_transactions.append(entity_tx)
            source_profile.outgoing_entities.add(target_entity_id)
            source_profile.total_out += entity_tx.value_eth

            target_profile.incoming_transactions.append(entity_tx)
            target_profile.incoming_entities.add(source_entity_id)
            target_profile.total_in += entity_tx.value_eth

            edge_key = (source_entity_id, target_entity_id)
            existing_edge = entity_edges.get(edge_key)
            if existing_edge is None:
                entity_edges[edge_key] = EntityEdge(
                    source_entity_id=source_entity_id,
                    target_entity_id=target_entity_id,
                    tx_hashes=[tx.tx_hash],
                    total_value_eth=entity_tx.value_eth,
                    tx_count=1,
                    first_seen_at=entity_tx.timestamp,
                    last_seen_at=entity_tx.timestamp,
                )
            else:
                existing_edge.tx_hashes.append(tx.tx_hash)
                existing_edge.total_value_eth += entity_tx.value_eth
                existing_edge.tx_count += 1
                existing_edge.first_seen_at = min(existing_edge.first_seen_at, entity_tx.timestamp)
                existing_edge.last_seen_at = max(existing_edge.last_seen_at, entity_tx.timestamp)

        incoming_entity_edges: dict[str, list[EntityEdge]] = defaultdict(list)
        outgoing_entity_edges: dict[str, list[EntityEdge]] = defaultdict(list)
        for edge in entity_edges.values():
            incoming_entity_edges[edge.target_entity_id].append(edge)
            outgoing_entity_edges[edge.source_entity_id].append(edge)

        for profile in profiles.values():
            profile.incoming_transactions.sort(key=lambda tx: (tx.timestamp, tx.tx_hash))
            profile.outgoing_transactions.sort(key=lambda tx: (tx.timestamp, tx.tx_hash))
            profile.internal_transactions.sort(key=lambda tx: (tx.timestamp, tx.tx_hash))
            profile.entity.metrics.update(
                {
                    "total_in": round(profile.total_in, 8),
                    "total_out": round(profile.total_out, 8),
                    "total_internal": round(profile.total_internal, 8),
                    "incoming_entity_count": len(profile.incoming_entities),
                    "outgoing_entity_count": len(profile.outgoing_entities),
                    "total_tx_count": profile.total_tx_count,
                }
            )

        for edge_list in incoming_entity_edges.values():
            edge_list.sort(key=lambda edge: (edge.first_seen_at, -edge.total_value_eth, edge.source_entity_id))
        for edge_list in outgoing_entity_edges.values():
            edge_list.sort(key=lambda edge: (edge.first_seen_at, -edge.total_value_eth, edge.target_entity_id))

        return profiles, entity_edges, dict(incoming_entity_edges), dict(outgoing_entity_edges)

    def _detect_behaviors(self, profiles: dict[str, EntityProfile]) -> list[BehaviorDetection]:
        detections: list[BehaviorDetection] = []
        for profile in profiles.values():
            candidates = [
                self._detect_structuring(profile),
                self._detect_smurfing(profile),
                self._detect_micro_funding(profile),
                self._detect_funneling(profile),
                self._detect_immediate_utilization(profile),
            ]
            detections.extend([candidate for candidate in candidates if candidate is not None])
        return detections

    def _detect_structuring(self, profile: EntityProfile) -> BehaviorDetection | None:
        incoming = profile.incoming_transactions
        min_tx = max(2, int(self.cfg.placement_structuring_min_tx_count or 4))
        if len(incoming) < min_tx:
            return None
        window_seconds = max(60, int(self.cfg.placement_structuring_window_minutes or 30) * 60)
        max_variance = max(0.001, float(self.cfg.placement_structuring_max_relative_variance or 0.05))
        best: dict[str, Any] | None = None
        left = 0

        for right in range(len(incoming)):
            while left < right and incoming[right].timestamp - incoming[left].timestamp > window_seconds:
                left += 1
            subset = incoming[left:right + 1]
            if len(subset) < min_tx:
                continue
            values = [tx.value_eth for tx in subset if tx.value_eth > 0]
            if len(values) < min_tx:
                continue
            rel_variance = _relative_variance(values)
            if rel_variance > max_variance:
                continue
            unique_senders = len({tx.source_entity_id for tx in subset})
            support_factor = min(1.0, len(subset) / float(min_tx * 2))
            variance_factor = 1.0 - min(1.0, rel_variance / max_variance)
            amount_factor = min(1.0, sum(values) / max(self.cfg.high_value_threshold_eth, 1.0))
            confidence = _clamp(
                0.35 * support_factor + 0.35 * variance_factor + 0.30 * amount_factor
                + (0.05 if unique_senders >= 3 else 0.0)
            )
            metrics = {
                "tx_count": len(subset),
                "unique_senders": unique_senders,
                "total_value_eth": round(sum(values), 8),
                "avg_value_eth": round(sum(values) / len(values), 8),
                "relative_variance": round(rel_variance, 6),
                "window_seconds": int(subset[-1].timestamp - subset[0].timestamp),
            }
            if best is None or confidence > best["confidence"]:
                best = {
                    "confidence": confidence,
                    "metrics": metrics,
                    "tx_hashes": [tx.tx_hash for tx in subset],
                    "first": subset[0].timestamp,
                    "last": subset[-1].timestamp,
                }

        if best is None or best["confidence"] < _SUSPICIOUS_BEHAVIOR_THRESHOLD:
            return None
        return BehaviorDetection(
            entity_id=profile.entity.entity_id,
            entity_type=profile.entity.entity_type,
            behavior_type="structuring",
            confidence_score=round(best["confidence"], 4),
            supporting_metrics=best["metrics"],
            supporting_tx_hashes=best["tx_hashes"],
            first_observed_at=_iso_from_ts(best["first"]),
            last_observed_at=_iso_from_ts(best["last"]),
        )

    def _detect_smurfing(self, profile: EntityProfile) -> BehaviorDetection | None:
        incoming = profile.incoming_transactions
        if not incoming:
            return None
        min_unique = max(2, int(self.cfg.placement_smurfing_min_unique_senders or 6))
        unique_senders = {tx.source_entity_id for tx in incoming}
        if len(unique_senders) < min_unique:
            return None
        wallet_age = max(0.0, profile.entity.last_seen_at - profile.entity.first_seen_at)
        max_age = max(60, int(self.cfg.placement_smurfing_max_wallet_age_seconds or 604800))
        if wallet_age > max_age:
            return None
        sender_counts = Counter(tx.source_entity_id for tx in incoming)
        distributed_ratio = sum(1 for count in sender_counts.values() if count == 1) / max(1, len(unique_senders))
        sender_factor = min(1.0, len(unique_senders) / float(min_unique * 2))
        age_factor = 1.0 - min(1.0, wallet_age / max_age)
        distributed_factor = min(1.0, distributed_ratio)
        confidence = _clamp(
            0.45 * sender_factor + 0.35 * age_factor + 0.20 * distributed_factor
        )
        if confidence < _SUSPICIOUS_BEHAVIOR_THRESHOLD:
            return None
        tx_hashes = [tx.tx_hash for tx in incoming[: min(len(incoming), 25)]]
        return BehaviorDetection(
            entity_id=profile.entity.entity_id,
            entity_type=profile.entity.entity_type,
            behavior_type="smurfing",
            confidence_score=round(confidence, 4),
            supporting_metrics={
                "unique_senders": len(unique_senders),
                "wallet_age_seconds": int(wallet_age),
                "distributed_sender_ratio": round(distributed_ratio, 4),
                "incoming_tx_count": len(incoming),
                "total_in_eth": round(profile.total_in, 8),
            },
            supporting_tx_hashes=tx_hashes,
            first_observed_at=_iso_from_ts(incoming[0].timestamp),
            last_observed_at=_iso_from_ts(incoming[-1].timestamp),
        )

    def _detect_micro_funding(self, profile: EntityProfile) -> BehaviorDetection | None:
        incoming = profile.incoming_transactions
        if not incoming:
            return None
        max_tx_value = max(0.000001, float(self.cfg.placement_micro_max_tx_eth or 0.1))
        small_incoming = [tx for tx in incoming if 0 < tx.value_eth <= max_tx_value]
        min_count = max(2, int(self.cfg.placement_micro_min_tx_count or 8))
        if len(small_incoming) < min_count:
            return None
        total_small = sum(tx.value_eth for tx in small_incoming)
        min_total = max(0.000001, float(self.cfg.placement_micro_min_total_eth or 1.0))
        if total_small < min_total:
            return None
        count_factor = min(1.0, len(small_incoming) / float(min_count * 2))
        total_factor = min(1.0, total_small / max(min_total * 3, min_total))
        consistency_factor = 1.0 - min(1.0, _relative_variance([tx.value_eth for tx in small_incoming]) / 0.5)
        confidence = _clamp(
            0.40 * count_factor + 0.40 * total_factor + 0.20 * consistency_factor
        )
        if confidence < _SUSPICIOUS_BEHAVIOR_THRESHOLD:
            return None
        return BehaviorDetection(
            entity_id=profile.entity.entity_id,
            entity_type=profile.entity.entity_type,
            behavior_type="micro_funding",
            confidence_score=round(confidence, 4),
            supporting_metrics={
                "small_tx_count": len(small_incoming),
                "small_tx_total_eth": round(total_small, 8),
                "small_tx_max_eth": round(max_tx_value, 8),
                "incoming_tx_count": len(incoming),
            },
            supporting_tx_hashes=[tx.tx_hash for tx in small_incoming[:25]],
            first_observed_at=_iso_from_ts(small_incoming[0].timestamp),
            last_observed_at=_iso_from_ts(small_incoming[-1].timestamp),
        )

    def _detect_funneling(self, profile: EntityProfile) -> BehaviorDetection | None:
        in_degree = len(profile.incoming_entities)
        out_degree = max(1, len(profile.outgoing_entities))
        min_in_degree = max(2, int(self.cfg.placement_funneling_min_in_degree or 5))
        min_ratio = max(1.0, float(self.cfg.placement_funneling_min_in_out_ratio or 3.0))
        ratio = in_degree / float(out_degree)
        if in_degree < min_in_degree or ratio < min_ratio:
            return None
        sender_factor = min(1.0, in_degree / float(min_in_degree * 2))
        ratio_factor = min(1.0, ratio / float(min_ratio * 2))
        value_factor = min(1.0, profile.total_in / max(self.cfg.high_value_threshold_eth, 1.0))
        confidence = _clamp(
            0.45 * sender_factor + 0.35 * ratio_factor + 0.20 * value_factor
        )
        if confidence < _SUSPICIOUS_BEHAVIOR_THRESHOLD:
            return None
        supporting_txs = sorted(profile.incoming_transactions, key=lambda tx: tx.value_eth, reverse=True)
        return BehaviorDetection(
            entity_id=profile.entity.entity_id,
            entity_type=profile.entity.entity_type,
            behavior_type="funneling",
            confidence_score=round(confidence, 4),
            supporting_metrics={
                "incoming_entity_count": in_degree,
                "outgoing_entity_count": len(profile.outgoing_entities),
                "in_out_ratio": round(ratio, 4),
                "total_in_eth": round(profile.total_in, 8),
                "total_out_eth": round(profile.total_out, 8),
            },
            supporting_tx_hashes=[tx.tx_hash for tx in supporting_txs[:25]],
            first_observed_at=_iso_from_ts(profile.incoming_transactions[0].timestamp if profile.incoming_transactions else None),
            last_observed_at=_iso_from_ts(profile.outgoing_transactions[-1].timestamp if profile.outgoing_transactions else profile.incoming_transactions[-1].timestamp),
        )

    def _detect_immediate_utilization(self, profile: EntityProfile) -> BehaviorDetection | None:
        incoming = profile.incoming_transactions
        outgoing = profile.outgoing_transactions
        if not incoming or not outgoing:
            return None
        max_holding = max(60, int(self.cfg.placement_immediate_max_holding_seconds or 3600))
        min_cycles = max(1, int(self.cfg.placement_immediate_min_cycles or 3))
        matched_cycles: list[tuple[EntityTransaction, EntityTransaction, float]] = []
        out_index = 0

        for in_tx in incoming:
            while out_index < len(outgoing) and outgoing[out_index].timestamp < in_tx.timestamp:
                out_index += 1
            if out_index >= len(outgoing):
                break
            out_tx = outgoing[out_index]
            delta = out_tx.timestamp - in_tx.timestamp
            if delta <= max_holding:
                matched_cycles.append((in_tx, out_tx, delta))
                out_index += 1

        if len(matched_cycles) < min_cycles:
            return None
        delays = [cycle[2] for cycle in matched_cycles]
        median_delay = sorted(delays)[len(delays) // 2]
        cycle_factor = min(1.0, len(matched_cycles) / float(min_cycles * 2))
        delay_factor = 1.0 - min(1.0, median_delay / max_holding)
        forwarded_total = sum(cycle[1].value_eth for cycle in matched_cycles)
        value_factor = min(1.0, forwarded_total / max(self.cfg.high_value_threshold_eth, 1.0))
        confidence = _clamp(
            0.45 * cycle_factor + 0.35 * delay_factor + 0.20 * value_factor
        )
        if confidence < _SUSPICIOUS_BEHAVIOR_THRESHOLD:
            return None
        tx_hashes = []
        for in_tx, out_tx, _delta in matched_cycles[:15]:
            tx_hashes.extend([in_tx.tx_hash, out_tx.tx_hash])
        return BehaviorDetection(
            entity_id=profile.entity.entity_id,
            entity_type=profile.entity.entity_type,
            behavior_type="immediate_utilization",
            confidence_score=round(confidence, 4),
            supporting_metrics={
                "matched_cycles": len(matched_cycles),
                "median_holding_seconds": int(median_delay),
                "forwarded_total_eth": round(forwarded_total, 8),
                "max_holding_seconds": max_holding,
            },
            supporting_tx_hashes=tx_hashes,
            first_observed_at=_iso_from_ts(matched_cycles[0][0].timestamp),
            last_observed_at=_iso_from_ts(matched_cycles[-1][1].timestamp),
        )

    def _trace_suspicious_entities(
        self,
        profiles: dict[str, EntityProfile],
        behavior_map: dict[str, list[BehaviorDetection]],
        incoming_entity_edges: dict[str, list[EntityEdge]],
        outgoing_entity_edges: dict[str, list[EntityEdge]],
    ) -> list[TracePath]:
        suspicious_entities = sorted(
            entity_id
            for entity_id, detections in behavior_map.items()
            if detections and detections[0].confidence_score >= _SUSPICIOUS_BEHAVIOR_THRESHOLD
        )
        trace_paths: list[TracePath] = []
        for entity_id in suspicious_entities:
            trace_paths.extend(
                self._trace_entity(
                    root_entity_id=entity_id,
                    profiles=profiles,
                    incoming_entity_edges=incoming_entity_edges,
                    outgoing_entity_edges=outgoing_entity_edges,
                )
            )
        return trace_paths

    def _trace_entity(
        self,
        root_entity_id: str,
        profiles: dict[str, EntityProfile],
        incoming_entity_edges: dict[str, list[EntityEdge]],
        outgoing_entity_edges: dict[str, list[EntityEdge]],
    ) -> list[TracePath]:
        max_hops = max(1, int(self.cfg.placement_origin_max_hops or 3))
        branching_limit = max(1, int(self.cfg.placement_origin_branching_limit or 3))
        paths: list[TracePath] = []

        def dfs(
            current_entity_id: str,
            depth: int,
            score: float,
            node_chain: list[str],
            edge_chain: list[list[str]],
        ) -> None:
            candidate_edges = incoming_entity_edges.get(current_entity_id, [])
            viable_edges: list[tuple[EntityEdge, float]] = []
            for edge in candidate_edges:
                upstream_id = edge.source_entity_id
                if upstream_id in node_chain:
                    continue
                next_score = score * self._trace_edge_confidence(
                    edge=edge,
                    downstream_profile=profiles[current_entity_id],
                    upstream_profile=profiles[upstream_id],
                    depth=depth,
                    outgoing_entity_edges=outgoing_entity_edges,
                )
                if next_score < _TRACE_MIN_CONFIDENCE:
                    continue
                viable_edges.append((edge, next_score))

            if depth >= max_hops:
                paths.append(
                    TracePath(
                        root_entity_id=root_entity_id,
                        origin_entity_id=node_chain[-1],
                        entity_ids=list(reversed(node_chain)),
                        score=round(score, 4),
                        terminal_reason="max_hops_reached",
                        edge_tx_hashes=list(reversed(edge_chain)),
                    )
                )
                return

            if not viable_edges:
                terminal_reason = "no_incoming" if not candidate_edges else "confidence_cutoff"
                paths.append(
                    TracePath(
                        root_entity_id=root_entity_id,
                        origin_entity_id=node_chain[-1],
                        entity_ids=list(reversed(node_chain)),
                        score=round(score, 4),
                        terminal_reason=terminal_reason,
                        edge_tx_hashes=list(reversed(edge_chain)),
                    )
                )
                return

            viable_edges.sort(
                key=lambda item: (
                    item[0].first_seen_at,
                    -item[0].total_value_eth,
                    item[0].source_entity_id,
                )
            )
            for edge, next_score in viable_edges[:branching_limit]:
                dfs(
                    current_entity_id=edge.source_entity_id,
                    depth=depth + 1,
                    score=next_score,
                    node_chain=node_chain + [edge.source_entity_id],
                    edge_chain=edge_chain + [edge.tx_hashes[:20]],
                )

        dfs(
            current_entity_id=root_entity_id,
            depth=0,
            score=1.0,
            node_chain=[root_entity_id],
            edge_chain=[],
        )
        return paths

    def _trace_edge_confidence(
        self,
        edge: EntityEdge,
        downstream_profile: EntityProfile,
        upstream_profile: EntityProfile,
        depth: int,
        outgoing_entity_edges: dict[str, list[EntityEdge]],
    ) -> float:
        incoming_base = max(downstream_profile.total_in, edge.total_value_eth, 1e-9)
        contribution = edge.total_value_eth / incoming_base
        service_tx_limit = max(20, int(self.cfg.placement_origin_service_tx_count or 200))
        service_degree_limit = max(5, int(self.cfg.placement_origin_service_degree or 25))
        upstream_degree = len(upstream_profile.incoming_entities | upstream_profile.outgoing_entities)
        is_service_like = (
            upstream_profile.total_tx_count >= service_tx_limit
            or upstream_degree >= service_degree_limit
        )
        service_penalty = 0.6 if is_service_like else 1.0
        branch_penalty = 0.95 ** depth
        fanout_penalty = 0.9 if len(outgoing_entity_edges.get(edge.source_entity_id, [])) > 3 else 1.0
        return _clamp((0.45 + 0.55 * min(1.0, contribution)) * service_penalty * branch_penalty * fanout_penalty)

    def _identify_placements(
        self,
        profiles: dict[str, EntityProfile],
        behavior_map: dict[str, list[BehaviorDetection]],
        trace_paths: list[TracePath],
        incoming_entity_edges: dict[str, list[EntityEdge]],
    ) -> list[PlacementDetection]:
        suspicious_entities = {
            entity_id
            for entity_id, detections in behavior_map.items()
            if detections and detections[0].confidence_score >= _SUSPICIOUS_BEHAVIOR_THRESHOLD
        }
        grouped_paths: dict[str, list[TracePath]] = defaultdict(list)
        for path in trace_paths:
            grouped_paths[path.origin_entity_id].append(path)

        placements: list[PlacementDetection] = []
        for origin_entity_id, origin_paths in grouped_paths.items():
            origin_profile = profiles[origin_entity_id]
            linked_root_entity_ids = {path.root_entity_id for path in origin_paths}
            linked_root_entities = sorted(linked_root_entity_ids)
            descendant_behaviors = sorted(
                {
                    detection.behavior_type
                    for entity_id in linked_root_entity_ids | {origin_entity_id}
                    for detection in behavior_map.get(entity_id, [])
                }
            )
            if not descendant_behaviors:
                continue

            origin_behaviors = behavior_map.get(origin_entity_id, [])
            origin_behavior_score = max(
                (detection.confidence_score for detection in origin_behaviors),
                default=0.0,
            )
            downstream_behavior_score = max(
                (
                    behavior_map[root_entity_id][0].confidence_score
                    for root_entity_id in linked_root_entities
                    if behavior_map.get(root_entity_id)
                ),
                default=0.0,
            )
            behavior_score = max(origin_behavior_score, downstream_behavior_score * (1.0 if origin_behavior_score else 0.88))

            max_depth = max(len(path.entity_ids) - 1 for path in origin_paths)
            avg_path_score = sum(path.score for path in origin_paths) / len(origin_paths)
            has_no_incoming = len(incoming_entity_edges.get(origin_entity_id, [])) == 0
            graph_position_score = _clamp(
                0.45 * (1.0 if has_no_incoming else 0.7)
                + 0.25 * min(1.0, max_depth / max(1, int(self.cfg.placement_origin_max_hops or 3)))
                + 0.30 * avg_path_score
            )

            temporal_reference = max(86400, int(self.cfg.placement_smurfing_max_wallet_age_seconds or 604800))
            temporal_gap = 0.0
            for root_entity_id in linked_root_entities:
                root_profile = profiles[root_entity_id]
                temporal_gap += max(0.0, root_profile.entity.first_seen_at - origin_profile.entity.first_seen_at)
            temporal_gap /= max(1, len(linked_root_entities))
            temporal_score = _clamp(
                0.55 * min(1.0, temporal_gap / temporal_reference)
                + 0.45 * (1.0 if has_no_incoming else 0.7)
            )

            prior_suspicious_history = any(
                upstream_entity_id in suspicious_entities
                for upstream_entity_id in origin_profile.incoming_entities
            )
            placement_score = (
                behavior_score * 0.4
                + graph_position_score * 0.4
                + temporal_score * 0.2
            )
            if prior_suspicious_history:
                placement_score *= 0.8
            confidence = round(_clamp(placement_score), 4)
            if confidence < _SUSPICIOUS_BEHAVIOR_THRESHOLD:
                continue

            reasons = []
            if has_no_incoming:
                reasons.append("earliest reachable entity in traced suspicious flow")
            else:
                reasons.append("trace terminated after confidence or hop cutoff")
            if origin_behaviors:
                reasons.append(
                    "direct suspicious behavior: " + ", ".join(
                        sorted({behavior.behavior_type for behavior in origin_behaviors})
                    )
                )
            else:
                reasons.append(
                    "downstream suspicious behavior: " + ", ".join(descendant_behaviors)
                )
            if not prior_suspicious_history:
                reasons.append("no prior suspicious history observed upstream in analyzed graph")

            supporting_tx_hashes = sorted(
                {
                    tx_hash
                    for path in origin_paths
                    for edge_hashes in path.edge_tx_hashes
                    for tx_hash in edge_hashes
                }
            )[:40]
            placements.append(
                PlacementDetection(
                    entity_id=origin_entity_id,
                    entity_type=origin_profile.entity.entity_type,
                    addresses=origin_profile.entity.addresses,
                    confidence_score=confidence,
                    placement_score=round(_clamp(placement_score), 4),
                    behavior_score=round(_clamp(behavior_score), 4),
                    graph_position_score=round(graph_position_score, 4),
                    temporal_score=round(temporal_score, 4),
                    behaviors=descendant_behaviors,
                    reasons=reasons,
                    linked_root_entities=linked_root_entities,
                    trace_path_count=len(origin_paths),
                    supporting_tx_hashes=supporting_tx_hashes,
                    validation_status=origin_profile.entity.validation_status,
                    validation_confidence=origin_profile.entity.validation_confidence,
                    first_seen_at=_iso_from_ts(origin_profile.entity.first_seen_at),
                    last_seen_at=_iso_from_ts(origin_profile.entity.last_seen_at),
                    metrics={
                        "avg_trace_score": round(avg_path_score, 4),
                        "max_trace_depth": max_depth,
                        "linked_root_entities": linked_root_entities,
                        "prior_suspicious_history": prior_suspicious_history,
                    },
                )
            )

        return placements

    def _assign_labels(
        self,
        profiles: dict[str, EntityProfile],
        behavior_map: dict[str, list[BehaviorDetection]],
        trace_paths: list[TracePath],
        placements: list[PlacementDetection],
    ) -> list[EntityLabel]:
        placement_ids = {placement.entity_id for placement in placements}
        suspicious_ids = {
            entity_id
            for entity_id, detections in behavior_map.items()
            if detections and detections[0].confidence_score >= _SUSPICIOUS_BEHAVIOR_THRESHOLD
        }
        intermediate_ids = {
            entity_id
            for path in trace_paths
            for entity_id in path.entity_ids[1:-1]
            if entity_id not in placement_ids and entity_id not in suspicious_ids
        }
        labels: list[EntityLabel] = []

        for placement in placements:
            labels.append(
                EntityLabel(
                    entity_id=placement.entity_id,
                    entity_type=placement.entity_type,
                    label="placement_origin",
                    source="placement_scoring_model",
                    confidence_score=placement.confidence_score,
                    explanation="Earliest traced entity with placement-level evidence.",
                )
            )

        for suspicious_id in sorted(suspicious_ids - placement_ids):
            entity = profiles[suspicious_id].entity
            top_behavior = behavior_map[suspicious_id][0]
            labels.append(
                EntityLabel(
                    entity_id=suspicious_id,
                    entity_type=entity.entity_type,
                    label="suspicious_receiver",
                    source="behavior_detection",
                    confidence_score=top_behavior.confidence_score,
                    explanation=f"Behavior detection flagged {top_behavior.behavior_type}.",
                )
            )

        for intermediate_id in sorted(intermediate_ids):
            entity = profiles[intermediate_id].entity
            labels.append(
                EntityLabel(
                    entity_id=intermediate_id,
                    entity_type=entity.entity_type,
                    label="intermediate_node",
                    source="backward_trace",
                    confidence_score=round(entity.validation_confidence * 0.9, 4),
                    explanation="Entity appears between the placement origin and suspicious downstream activity.",
                )
            )

        return labels

    def _build_pois(self, placements: list[PlacementDetection]) -> list[InvestigationPoi]:
        pois: list[InvestigationPoi] = []
        for placement in placements:
            if placement.confidence_score < _ACTIONABLE_POI_THRESHOLD:
                continue
            poi_id = "POI-" + hashlib.sha1(
                f"{placement.entity_id}|{placement.first_seen_at}|{placement.placement_score}".encode()
            ).hexdigest()[:10].upper()
            pois.append(
                InvestigationPoi(
                    poi_id=poi_id,
                    entity_id=placement.entity_id,
                    entity_type=placement.entity_type,
                    risk_score=round(placement.placement_score * 100.0, 2),
                    reason="placement detection",
                    linked_behaviors=placement.behaviors,
                    supporting_evidence={
                        "reasons": placement.reasons,
                        "trace_path_count": placement.trace_path_count,
                        "supporting_tx_hashes": placement.supporting_tx_hashes[:20],
                    },
                )
            )
        return pois

    def _build_summary(
        self,
        *,
        source: str,
        transactions: list[TxRecord],
        entities: dict[str, PlacementEntity],
        behaviors: list[BehaviorDetection],
        placements: list[PlacementDetection],
        labels: list[EntityLabel],
        pois: list[InvestigationPoi],
    ) -> dict[str, Any]:
        return {
            "source": source,
            "transactions": len(transactions),
            "entities": len(entities),
            "cluster_entities": sum(1 for entity in entities.values() if entity.entity_type == "cluster"),
            "address_entities": sum(1 for entity in entities.values() if entity.entity_type == "address"),
            "validation_status": dict(Counter(entity.validation_status for entity in entities.values())),
            "behaviors": dict(Counter(detection.behavior_type for detection in behaviors)),
            "placements": len(placements),
            "labels": dict(Counter(label.label for label in labels)),
            "pois": len(pois),
        }

    def _persist(
        self,
        result: PlacementAnalysisResult,
        profiles: dict[str, EntityProfile],
        entity_edges: dict[tuple[str, str], EntityEdge],
        trace_paths: list[TracePath],
    ) -> None:
        create_tables_if_not_exist(self.cfg)
        engine = get_maria_engine(self.cfg)
        completed_at = datetime.fromisoformat(result.generated_at.replace("Z", "+00:00")).replace(tzinfo=None)

        entity_rows = []
        entity_address_rows = []
        for entity in result.entities:
            entity_rows.append(
                {
                    "run_id": result.run_id,
                    "entity_id": entity.entity_id,
                    "entity_type": entity.entity_type,
                    "validation_status": entity.validation_status,
                    "validation_confidence": entity.validation_confidence,
                    "source_kind": entity.source_kind,
                    "source_cluster_ids_json": _json_dumps(entity.source_cluster_ids),
                    "address_count": len(entity.addresses),
                    "first_seen_at": _dt_from_ts(entity.first_seen_at),
                    "last_seen_at": _dt_from_ts(entity.last_seen_at),
                    "metrics_json": _json_dumps(entity.metrics),
                }
            )
            for address in entity.addresses:
                entity_address_rows.append(
                    {
                        "run_id": result.run_id,
                        "entity_id": entity.entity_id,
                        "address": address,
                    }
                )

        behavior_rows = [
            {
                "run_id": result.run_id,
                "entity_id": behavior.entity_id,
                "entity_type": behavior.entity_type,
                "behavior_type": behavior.behavior_type,
                "confidence_score": behavior.confidence_score,
                "metrics_json": _json_dumps(behavior.supporting_metrics),
                "supporting_tx_hashes_json": _json_dumps(behavior.supporting_tx_hashes),
                "first_observed_at": datetime.fromisoformat(behavior.first_observed_at).replace(tzinfo=None) if behavior.first_observed_at else None,
                "last_observed_at": datetime.fromisoformat(behavior.last_observed_at).replace(tzinfo=None) if behavior.last_observed_at else None,
            }
            for behavior in result.behaviors
        ]

        trace_rows = []
        for path in trace_paths:
            nodes = path.entity_ids
            if len(nodes) == 1:
                entity = profiles[nodes[0]].entity
                trace_rows.append(
                    {
                        "run_id": result.run_id,
                        "root_entity_id": path.root_entity_id,
                        "origin_entity_id": path.origin_entity_id,
                        "path_index": path.path_index,
                        "depth": 0,
                        "upstream_entity_id": nodes[0],
                        "downstream_entity_id": None,
                        "path_score": path.score,
                        "is_terminal": 1,
                        "terminal_reason": path.terminal_reason,
                        "edge_value_eth": 0.0,
                        "supporting_tx_hashes_json": _json_dumps([]),
                        "first_seen_at": _dt_from_ts(entity.first_seen_at),
                        "last_seen_at": _dt_from_ts(entity.last_seen_at),
                        "details_json": _json_dumps({"entity_ids": nodes}),
                    }
                )
                continue

            for depth, (upstream_entity_id, downstream_entity_id) in enumerate(zip(nodes, nodes[1:])):
                edge = entity_edges.get((upstream_entity_id, downstream_entity_id))
                tx_hashes = path.edge_tx_hashes[depth] if depth < len(path.edge_tx_hashes) else []
                trace_rows.append(
                    {
                        "run_id": result.run_id,
                        "root_entity_id": path.root_entity_id,
                        "origin_entity_id": path.origin_entity_id,
                        "path_index": path.path_index,
                        "depth": depth,
                        "upstream_entity_id": upstream_entity_id,
                        "downstream_entity_id": downstream_entity_id,
                        "path_score": path.score,
                        "is_terminal": 1 if depth == len(nodes) - 2 else 0,
                        "terminal_reason": path.terminal_reason if depth == len(nodes) - 2 else None,
                        "edge_value_eth": 0.0 if edge is None else round(edge.total_value_eth, 8),
                        "supporting_tx_hashes_json": _json_dumps(tx_hashes),
                        "first_seen_at": None if edge is None else _dt_from_ts(edge.first_seen_at),
                        "last_seen_at": None if edge is None else _dt_from_ts(edge.last_seen_at),
                        "details_json": _json_dumps({"entity_ids": nodes}),
                    }
                )

        placement_rows = [
            {
                "run_id": result.run_id,
                "entity_id": placement.entity_id,
                "entity_type": placement.entity_type,
                "placement_type": "placement_origin",
                "confidence_score": placement.confidence_score,
                "placement_score": placement.placement_score,
                "behavior_score": placement.behavior_score,
                "graph_position_score": placement.graph_position_score,
                "temporal_score": placement.temporal_score,
                "reasons_json": _json_dumps(placement.reasons),
                "behaviors_json": _json_dumps(placement.behaviors),
                "linked_root_entities_json": _json_dumps(placement.linked_root_entities),
                "supporting_tx_hashes_json": _json_dumps(placement.supporting_tx_hashes),
                "metrics_json": _json_dumps(placement.metrics),
                "first_seen_at": datetime.fromisoformat(placement.first_seen_at).replace(tzinfo=None) if placement.first_seen_at else None,
                "last_seen_at": datetime.fromisoformat(placement.last_seen_at).replace(tzinfo=None) if placement.last_seen_at else None,
            }
            for placement in result.placements
        ]

        label_rows = [
            {
                "run_id": result.run_id,
                "entity_id": label.entity_id,
                "entity_type": label.entity_type,
                "label": label.label,
                "label_source": label.source,
                "confidence_score": label.confidence_score,
                "explanation": label.explanation,
            }
            for label in result.labels
        ]

        poi_rows = [
            {
                "poi_id": poi.poi_id,
                "run_id": result.run_id,
                "entity_id": poi.entity_id,
                "entity_type": poi.entity_type,
                "risk_score": poi.risk_score,
                "reason": poi.reason,
                "linked_behaviors_json": _json_dumps(poi.linked_behaviors),
                "supporting_evidence_json": _json_dumps(poi.supporting_evidence),
            }
            for poi in result.pois
        ]

        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO placement_runs
                            (id, source, status, started_at, completed_at, summary_json)
                        VALUES
                            (:id, :source, 'completed', :started_at, :completed_at, :summary_json)
                        """
                    ),
                    {
                        "id": result.run_id,
                        "source": result.summary.get("source", "auto"),
                        "started_at": completed_at,
                        "completed_at": completed_at,
                        "summary_json": _json_dumps(result.summary),
                    },
                )

                if entity_rows:
                    conn.execute(
                        text(
                            """
                            INSERT INTO placement_entities (
                                run_id,
                                entity_id,
                                entity_type,
                                validation_status,
                                validation_confidence,
                                source_kind,
                                source_cluster_ids_json,
                                address_count,
                                first_seen_at,
                                last_seen_at,
                                metrics_json
                            )
                            VALUES (
                                :run_id,
                                :entity_id,
                                :entity_type,
                                :validation_status,
                                :validation_confidence,
                                :source_kind,
                                :source_cluster_ids_json,
                                :address_count,
                                :first_seen_at,
                                :last_seen_at,
                                :metrics_json
                            )
                            """
                        ),
                        entity_rows,
                    )

                if entity_address_rows:
                    for batch in _chunked(entity_address_rows, 1000):
                        conn.execute(
                            text(
                                """
                                INSERT INTO placement_entity_addresses (run_id, entity_id, address)
                                VALUES (:run_id, :entity_id, :address)
                                """
                            ),
                            batch,
                        )

                if behavior_rows:
                    conn.execute(
                        text(
                            """
                            INSERT INTO placement_behaviors (
                                run_id,
                                entity_id,
                                entity_type,
                                behavior_type,
                                confidence_score,
                                metrics_json,
                                supporting_tx_hashes_json,
                                first_observed_at,
                                last_observed_at
                            )
                            VALUES (
                                :run_id,
                                :entity_id,
                                :entity_type,
                                :behavior_type,
                                :confidence_score,
                                :metrics_json,
                                :supporting_tx_hashes_json,
                                :first_observed_at,
                                :last_observed_at
                            )
                            """
                        ),
                        behavior_rows,
                    )

                if trace_rows:
                    for batch in _chunked(trace_rows, 1000):
                        conn.execute(
                            text(
                                """
                                INSERT INTO placement_traces (
                                    run_id,
                                    root_entity_id,
                                    origin_entity_id,
                                    path_index,
                                    depth,
                                    upstream_entity_id,
                                    downstream_entity_id,
                                    path_score,
                                    is_terminal,
                                    terminal_reason,
                                    edge_value_eth,
                                    supporting_tx_hashes_json,
                                    first_seen_at,
                                    last_seen_at,
                                    details_json
                                )
                                VALUES (
                                    :run_id,
                                    :root_entity_id,
                                    :origin_entity_id,
                                    :path_index,
                                    :depth,
                                    :upstream_entity_id,
                                    :downstream_entity_id,
                                    :path_score,
                                    :is_terminal,
                                    :terminal_reason,
                                    :edge_value_eth,
                                    :supporting_tx_hashes_json,
                                    :first_seen_at,
                                    :last_seen_at,
                                    :details_json
                                )
                                """
                            ),
                            batch,
                        )

                if placement_rows:
                    conn.execute(
                        text(
                            """
                            INSERT INTO placement_detections (
                                run_id,
                                entity_id,
                                entity_type,
                                placement_type,
                                confidence_score,
                                placement_score,
                                behavior_score,
                                graph_position_score,
                                temporal_score,
                                reasons_json,
                                behaviors_json,
                                linked_root_entities_json,
                                supporting_tx_hashes_json,
                                metrics_json,
                                first_seen_at,
                                last_seen_at
                            )
                            VALUES (
                                :run_id,
                                :entity_id,
                                :entity_type,
                                :placement_type,
                                :confidence_score,
                                :placement_score,
                                :behavior_score,
                                :graph_position_score,
                                :temporal_score,
                                :reasons_json,
                                :behaviors_json,
                                :linked_root_entities_json,
                                :supporting_tx_hashes_json,
                                :metrics_json,
                                :first_seen_at,
                                :last_seen_at
                            )
                            """
                        ),
                        placement_rows,
                    )

                if label_rows:
                    conn.execute(
                        text(
                            """
                            INSERT INTO placement_labels (
                                run_id,
                                entity_id,
                                entity_type,
                                label,
                                label_source,
                                confidence_score,
                                explanation
                            )
                            VALUES (
                                :run_id,
                                :entity_id,
                                :entity_type,
                                :label,
                                :label_source,
                                :confidence_score,
                                :explanation
                            )
                            """
                        ),
                        label_rows,
                    )

                if poi_rows:
                    conn.execute(
                        text(
                            """
                            INSERT INTO placement_pois (
                                poi_id,
                                run_id,
                                entity_id,
                                entity_type,
                                risk_score,
                                reason,
                                linked_behaviors_json,
                                supporting_evidence_json
                            )
                            VALUES (
                                :poi_id,
                                :run_id,
                                :entity_id,
                                :entity_type,
                                :risk_score,
                                :reason,
                                :linked_behaviors_json,
                                :supporting_evidence_json
                            )
                            """
                        ),
                        poi_rows,
                    )

            logger.info(
                "Persisted placement run %s with %d placements and %d POIs",
                result.run_id,
                len(result.placements),
                len(result.pois),
            )
        finally:
            engine.dispose()
