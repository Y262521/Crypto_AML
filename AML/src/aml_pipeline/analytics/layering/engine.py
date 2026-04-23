"""Layering-stage AML analytics engine."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import logging
import statistics
from typing import Any

from sqlalchemy import text

from ...clustering.graph_builder import build_graph_artifacts
from ...config import Config
from ...etl.load.mariadb_loader import create_tables_if_not_exist
from ...utils.connections import get_maria_engine
from ..placement import PlacementAnalysisEngine, PlacementAnalysisResult
from .detectors import (
    BridgeHoppingDetector,
    HighDepthTransactionChainingDetector,
    MixingInteractionDetector,
    PeelingChainDetector,
    ShellWalletNetworkDetector,
)
from .service_profiles import ServiceRegistry, load_service_registry
from .types import (
    LayeringAlert,
    LayeringAnalysisResult,
    LayeringContext,
    LayeringSeed,
    chunked,
    clamp,
    json_dumps,
    stable_run_id,
)

logger = logging.getLogger(__name__)


class LayeringAnalysisEngine(PlacementAnalysisEngine):
    """Run layering-stage analytics on Ethereum account-based transaction flows."""

    def __init__(
        self,
        cfg: Config | None = None,
        service_registry: ServiceRegistry | None = None,
    ):
        super().__init__(cfg=cfg)
        self._service_registry_override = service_registry
        self.detectors = [
            PeelingChainDetector(),
            MixingInteractionDetector(),
            BridgeHoppingDetector(),
            ShellWalletNetworkDetector(),
            HighDepthTransactionChainingDetector(),
        ]

    def run(
        self,
        source: str = "auto",
        persist: bool = False,
        placement_result: PlacementAnalysisResult | None = None,
        seed_entity_ids: list[str] | None = None,
        seed_addresses: list[str] | None = None,
    ) -> LayeringAnalysisResult:
        transactions = self._load_transactions(source=source)
        generated_at = datetime.now(timezone.utc)
        run_id = stable_run_id(generated_at)

        if not transactions:
            result = self._empty_result(
                run_id=run_id,
                generated_at=generated_at.isoformat(),
                source=source,
                placement_run_id=None if placement_result is None else placement_result.run_id,
            )
            if persist:
                self._persist(result, None)
            return result

        if placement_result is None and not seed_entity_ids and not seed_addresses:
            placement_result = super().run(source=source, persist=False)

        artifacts = build_graph_artifacts(transactions)
        entities, address_to_entity = self._resolve_entities(transactions, artifacts)
        profiles, entity_edges, incoming_entity_edges, outgoing_entity_edges = self._build_entity_profiles(
            transactions,
            entities,
            address_to_entity,
        )
        seeds = self._build_seeds(
            entities=entities,
            address_to_entity=address_to_entity,
            placement_result=placement_result,
            seed_entity_ids=seed_entity_ids,
            seed_addresses=seed_addresses,
        )

        service_registry = self._service_registry_override or load_service_registry(self.cfg)
        tx_by_hash = {tx.tx_hash: tx for tx in transactions if tx.tx_hash}
        address_first_seen, address_last_seen, address_degree, address_tx_count = self._build_address_stats(
            transactions,
            artifacts,
        )
        address_labels = self._build_address_labels(
            transactions=transactions,
            entities=entities,
            artifacts=artifacts,
            service_registry=service_registry,
            address_degree=address_degree,
            address_tx_count=address_tx_count,
        )
        entity_labels = self._build_entity_labels(entities, address_labels)

        context = LayeringContext(
            cfg=self.cfg,
            transactions=transactions,
            artifacts=artifacts,
            seeds=seeds,
            entities=entities,
            address_to_entity=address_to_entity,
            profiles=profiles,
            entity_edges=entity_edges,
            incoming_entity_edges=incoming_entity_edges,
            outgoing_entity_edges=outgoing_entity_edges,
            tx_by_hash=tx_by_hash,
            service_registry=service_registry,
            address_labels=address_labels,
            entity_labels=entity_labels,
            address_first_seen=address_first_seen,
            address_last_seen=address_last_seen,
            address_degree=address_degree,
            address_tx_count=address_tx_count,
        )

        detections = []
        evidence = []
        bridge_pairs = []
        for detector in self.detectors:
            detector_output = detector.detect(context)
            logger.info(
                "Layering detector %s produced %d hits",
                detector.detector_type,
                len(detector_output.hits),
            )
            detections.extend(detector_output.hits)
            evidence.extend(detector_output.evidence)
            bridge_pairs.extend(detector_output.bridge_pairs)

        detections = self._dedupe_detections(detections)
        evidence = self._dedupe_evidence(evidence)
        bridge_pairs = self._dedupe_bridge_pairs(bridge_pairs)
        alerts = self._build_alerts(seeds, detections, evidence, bridge_pairs)
        summary = self._build_summary(
            source=source,
            placement_run_id=None if placement_result is None else placement_result.run_id,
            transactions=transactions,
            seeds=seeds,
            detections=detections,
            alerts=alerts,
            bridge_pairs=bridge_pairs,
        )

        result = LayeringAnalysisResult(
            run_id=run_id,
            generated_at=generated_at.isoformat(),
            summary=summary,
            seeds=sorted(seeds.values(), key=lambda item: (item.entity_type, item.entity_id)),
            detections=sorted(
                detections,
                key=lambda item: (item.confidence_score, item.entity_id, item.detector_type),
                reverse=True,
            ),
            evidence=sorted(evidence, key=lambda item: (item.entity_id, item.detector_type, item.evidence_id)),
            bridge_pairs=sorted(
                bridge_pairs,
                key=lambda item: (item.confidence_score, item.entity_id, item.latency_seconds),
                reverse=True,
            ),
            alerts=sorted(
                alerts,
                key=lambda item: (item.layering_score, item.confidence_score, item.entity_id),
                reverse=True,
            ),
        )

        if persist:
            self._persist(result, context)

        return result

    def _empty_result(
        self,
        run_id: str,
        generated_at: str,
        source: str,
        placement_run_id: str | None,
    ) -> LayeringAnalysisResult:
        return LayeringAnalysisResult(
            run_id=run_id,
            generated_at=generated_at,
            summary={
                "source": source,
                "placement_run_id": placement_run_id,
                "transactions": 0,
                "seeds_analyzed": 0,
                "detections": {},
                "alerts": 0,
                "bridge_pairs": 0,
            },
            seeds=[],
            detections=[],
            evidence=[],
            bridge_pairs=[],
            alerts=[],
        )

    def _load_transactions(self, source: str) -> list:
        adapter = self.clustering_engine.adapter
        preferred_source = source
        if source == "auto" and hasattr(adapter, "_count_raw_mongo_transactions"):
            try:
                if int(adapter._count_raw_mongo_transactions()) > 0:
                    preferred_source = "raw"
            except Exception:
                preferred_source = source
        transactions = list(adapter.iter_transactions(source=preferred_source))
        transactions.sort(key=lambda tx: (float(tx.timestamp or 0.0), tx.tx_hash))
        logger.info(
            "Layering analysis loaded %d transactions from %s",
            len(transactions),
            preferred_source,
        )
        return transactions

    def _build_seeds(
        self,
        entities: dict[str, Any],
        address_to_entity: dict[str, str],
        placement_result: PlacementAnalysisResult | None,
        seed_entity_ids: list[str] | None,
        seed_addresses: list[str] | None,
    ) -> dict[str, LayeringSeed]:
        seeds: dict[str, LayeringSeed] = {}
        min_seed_confidence = max(0.0, float(self.cfg.layering_min_seed_confidence or 0.55))

        if placement_result is not None:
            for placement in placement_result.placements:
                if float(placement.confidence_score or 0.0) < min_seed_confidence:
                    continue
                entity_id = self._match_entity_id(
                    placement.entity_id,
                    placement.addresses,
                    address_to_entity,
                )
                if not entity_id or entity_id not in entities:
                    continue
                entity = entities[entity_id]
                existing = seeds.get(entity_id)
                if existing is not None and existing.placement_score >= float(placement.placement_score or 0.0):
                    continue
                seeds[entity_id] = LayeringSeed(
                    entity_id=entity.entity_id,
                    entity_type=entity.entity_type,
                    addresses=list(entity.addresses),
                    placement_score=round(float(placement.placement_score or 0.0), 4),
                    placement_confidence=round(float(placement.confidence_score or 0.0), 4),
                    placement_behaviors=list(placement.behaviors),
                    first_seen_at=placement.first_seen_at,
                    last_seen_at=placement.last_seen_at,
                    metrics={
                        "seed_source": "placement",
                        "placement_behaviors": list(placement.behaviors),
                        "placement_reasons": list(placement.reasons),
                    },
                )

        manual_entities: set[str] = set()
        for raw_entity_id in seed_entity_ids or []:
            normalized = str(raw_entity_id or "").lower().strip()
            if not normalized:
                continue
            if raw_entity_id in entities:
                manual_entities.add(raw_entity_id)
            elif normalized in address_to_entity:
                manual_entities.add(address_to_entity[normalized])
        for address in seed_addresses or []:
            normalized = str(address or "").lower().strip()
            if normalized in address_to_entity:
                manual_entities.add(address_to_entity[normalized])

        for entity_id in sorted(manual_entities):
            if entity_id in seeds or entity_id not in entities:
                continue
            entity = entities[entity_id]
            seeds[entity_id] = LayeringSeed(
                entity_id=entity.entity_id,
                entity_type=entity.entity_type,
                addresses=list(entity.addresses),
                placement_score=0.0,
                placement_confidence=0.0,
                placement_behaviors=[],
                first_seen_at=None,
                last_seen_at=None,
                metrics={"seed_source": "manual"},
            )

        logger.info("Layering analysis selected %d seed entities", len(seeds))
        return seeds

    def _match_entity_id(
        self,
        placement_entity_id: str,
        addresses: list[str],
        address_to_entity: dict[str, str],
    ) -> str | None:
        if placement_entity_id in address_to_entity.values():
            return placement_entity_id
        overlap = Counter(
            address_to_entity.get(str(address or "").lower().strip())
            for address in addresses
        )
        overlap.pop(None, None)
        if not overlap:
            return None
        return overlap.most_common(1)[0][0]

    def _build_address_stats(
        self,
        transactions: list[Any],
        artifacts: Any,
    ) -> tuple[dict[str, float], dict[str, float], dict[str, int], dict[str, int]]:
        first_seen: dict[str, float] = {}
        last_seen: dict[str, float] = {}
        tx_count: dict[str, int] = defaultdict(int)
        for tx in transactions:
            tx_ts = float(tx.timestamp or 0.0)
            for address in (tx.from_address, tx.to_address):
                if not address:
                    continue
                address = address.lower().strip()
                tx_count[address] += 1
                first_seen[address] = tx_ts if address not in first_seen else min(first_seen[address], tx_ts)
                last_seen[address] = tx_ts if address not in last_seen else max(last_seen[address], tx_ts)

        degree: dict[str, int] = {}
        for address in set(first_seen) | set(last_seen):
            neighbors = {
                str(edge.get("to_address") or "").lower().strip()
                for edge in artifacts.outgoing_edges.get(address, [])
            } | {
                str(edge.get("from_address") or "").lower().strip()
                for edge in artifacts.incoming_edges.get(address, [])
            }
            degree[address] = len({neighbor for neighbor in neighbors if neighbor})

        return first_seen, last_seen, degree, dict(tx_count)

    def _build_address_labels(
        self,
        transactions: list[Any],
        entities: dict[str, Any],
        artifacts: Any,
        service_registry: ServiceRegistry,
        address_degree: dict[str, int],
        address_tx_count: dict[str, int],
    ) -> dict[str, set[str]]:
        labels: dict[str, set[str]] = defaultdict(set)
        all_addresses = {
            address
            for entity in entities.values()
            for address in entity.addresses
        }
        for address in all_addresses:
            labels[address].update(service_registry.categories_for_address(address))

        for tx in transactions:
            method_categories = service_registry.categories_for_method(tx.input_method_id)
            if method_categories and tx.to_address:
                labels[tx.to_address].update(method_categories)
            if tx.from_address:
                labels[tx.from_address].update(service_registry.categories_for_address(tx.from_address))
            if tx.to_address:
                labels[tx.to_address].update(service_registry.categories_for_address(tx.to_address))

        service_tx_count = max(20, int(self.cfg.layering_service_tx_count or 200))
        service_degree = max(5, int(self.cfg.layering_service_degree or 25))
        for address in set(address_tx_count) | set(address_degree):
            if labels[address] & {"mixer", "bridge", "exchange"}:
                continue
            if address_tx_count.get(address, 0) >= service_tx_count or address_degree.get(address, 0) >= service_degree:
                labels[address].add("service_like")

        return {address: set(value) for address, value in labels.items()}

    def _build_entity_labels(
        self,
        entities: dict[str, Any],
        address_labels: dict[str, set[str]],
    ) -> dict[str, set[str]]:
        entity_labels: dict[str, set[str]] = {}
        for entity_id, entity in entities.items():
            merged = set()
            for address in entity.addresses:
                merged.update(address_labels.get(address, set()))
            entity_labels[entity_id] = merged
        return entity_labels

    def _dedupe_detections(self, detections: list[Any]) -> list[Any]:
        deduped: dict[tuple[str, str], Any] = {}
        for detection in detections:
            key = (detection.entity_id, detection.detector_type)
            existing = deduped.get(key)
            if existing is None or detection.confidence_score > existing.confidence_score:
                deduped[key] = detection
                continue
            existing.supporting_tx_hashes = sorted(
                set(existing.supporting_tx_hashes) | set(detection.supporting_tx_hashes)
            )
            existing.evidence_ids = sorted(set(existing.evidence_ids) | set(detection.evidence_ids))
        return list(deduped.values())

    def _dedupe_evidence(self, evidence: list[Any]) -> list[Any]:
        unique: dict[str, Any] = {}
        for item in evidence:
            unique[item.evidence_id] = item
        return list(unique.values())

    def _dedupe_bridge_pairs(self, bridge_pairs: list[Any]) -> list[Any]:
        unique: dict[tuple[str, str, str], Any] = {}
        for pair in bridge_pairs:
            unique[(pair.entity_id, pair.source_tx, pair.destination_tx)] = pair
        return list(unique.values())

    def _build_alerts(
        self,
        seeds: dict[str, LayeringSeed],
        detections: list[Any],
        evidence: list[Any],
        bridge_pairs: list[Any],
    ) -> list[LayeringAlert]:
        evidence_by_entity: dict[str, set[str]] = defaultdict(set)
        for item in evidence:
            evidence_by_entity[item.entity_id].add(item.evidence_id)
        bridge_pair_counts = Counter(pair.entity_id for pair in bridge_pairs)

        grouped: dict[str, list[Any]] = defaultdict(list)
        for detection in detections:
            grouped[detection.entity_id].append(detection)

        alerts: list[LayeringAlert] = []
        for entity_id, hits in grouped.items():
            if entity_id not in seeds:
                continue
            seed = seeds[entity_id]
            ranked_hits = sorted(
                hits,
                key=lambda item: (item.confidence_score, item.detector_type),
                reverse=True,
            )
            method_scores = {
                hit.detector_type: round(hit.confidence_score, 4)
                for hit in ranked_hits
            }
            methods = [hit.detector_type for hit in ranked_hits]
            confidence_score = round(ranked_hits[0].confidence_score, 4)
            layering_score = round(statistics.fmean(method_scores.values()), 4)
            reasons = [hit.summary for hit in ranked_hits]
            supporting_tx_hashes = sorted(
                {
                    tx_hash
                    for hit in ranked_hits
                    for tx_hash in hit.supporting_tx_hashes
                }
            )
            evidence_ids = sorted(
                set(evidence_by_entity.get(entity_id, set()))
                | {
                    evidence_id
                    for hit in ranked_hits
                    for evidence_id in hit.evidence_ids
                }
            )
            first_seen_at = next((hit.first_observed_at for hit in ranked_hits if hit.first_observed_at), seed.first_seen_at)
            last_seen_at = next((hit.last_observed_at for hit in ranked_hits if hit.last_observed_at), seed.last_seen_at)
            alerts.append(
                LayeringAlert(
                    entity_id=entity_id,
                    entity_type=seed.entity_type,
                    addresses=list(seed.addresses),
                    confidence_score=confidence_score,
                    layering_score=layering_score,
                    placement_score=seed.placement_score,
                    placement_confidence=seed.placement_confidence,
                    method_scores=method_scores,
                    methods=methods,
                    reasons=reasons,
                    supporting_tx_hashes=supporting_tx_hashes,
                    evidence_ids=evidence_ids,
                    first_seen_at=first_seen_at,
                    last_seen_at=last_seen_at,
                    metrics={
                        "detector_count": len(ranked_hits),
                        "placement_behaviors": seed.placement_behaviors,
                        "bridge_pair_count": bridge_pair_counts.get(entity_id, 0),
                    },
                )
            )

        return alerts

    def _build_summary(
        self,
        source: str,
        placement_run_id: str | None,
        transactions: list[Any],
        seeds: dict[str, LayeringSeed],
        detections: list[Any],
        alerts: list[LayeringAlert],
        bridge_pairs: list[Any],
    ) -> dict[str, Any]:
        return {
            "source": source,
            "placement_run_id": placement_run_id,
            "transactions": len(transactions),
            "seeds_analyzed": len(seeds),
            "detections": dict(Counter(detection.detector_type for detection in detections)),
            "alerts": len(alerts),
            "bridge_pairs": len(bridge_pairs),
            "average_alert_confidence": round(
                statistics.fmean(alert.confidence_score for alert in alerts),
                4,
            ) if alerts else 0.0,
        }

    def _persist(
        self,
        result: LayeringAnalysisResult,
        context: LayeringContext | None,
    ) -> None:
        create_tables_if_not_exist(self.cfg)
        engine = get_maria_engine(self.cfg)
        completed_at = datetime.fromisoformat(result.generated_at.replace("Z", "+00:00")).replace(tzinfo=None)

        def _dt_from_iso(value: str | None):
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None) if value else None

        entity_rows = []
        entity_address_rows = []
        if context is not None:
            for seed in result.seeds:
                entity = context.entities.get(seed.entity_id)
                if entity is None:
                    continue
                entity_rows.append(
                    {
                        "run_id": result.run_id,
                        "entity_id": seed.entity_id,
                        "entity_type": seed.entity_type,
                        "placement_score": seed.placement_score,
                        "placement_confidence": seed.placement_confidence,
                        "placement_behaviors_json": json_dumps(seed.placement_behaviors),
                        "validation_status": entity.validation_status,
                        "validation_confidence": entity.validation_confidence,
                        "source_kind": entity.source_kind,
                        "address_count": len(seed.addresses),
                        "first_seen_at": _dt_from_iso(seed.first_seen_at),
                        "last_seen_at": _dt_from_iso(seed.last_seen_at),
                        "metrics_json": json_dumps(seed.metrics),
                    }
                )
                for address in seed.addresses:
                    entity_address_rows.append(
                        {
                            "run_id": result.run_id,
                            "entity_id": seed.entity_id,
                            "address": address,
                        }
                    )

        detection_rows = [
            {
                "run_id": result.run_id,
                "entity_id": detection.entity_id,
                "entity_type": detection.entity_type,
                "detector_type": detection.detector_type,
                "confidence_score": detection.confidence_score,
                "summary_text": detection.summary,
                "score_components_json": json_dumps(detection.score_components),
                "metrics_json": json_dumps(detection.metrics),
                "supporting_tx_hashes_json": json_dumps(detection.supporting_tx_hashes),
                "evidence_ids_json": json_dumps(detection.evidence_ids),
                "first_observed_at": _dt_from_iso(detection.first_observed_at),
                "last_observed_at": _dt_from_iso(detection.last_observed_at),
            }
            for detection in result.detections
        ]
        evidence_rows = [
            {
                "run_id": result.run_id,
                "evidence_id": evidence.evidence_id,
                "entity_id": evidence.entity_id,
                "detector_type": evidence.detector_type,
                "evidence_type": evidence.evidence_type,
                "title": evidence.title,
                "summary_text": evidence.summary,
                "entity_ids_json": json_dumps(evidence.entity_ids),
                "tx_hashes_json": json_dumps(evidence.tx_hashes),
                "path_json": json_dumps(evidence.path),
                "metrics_json": json_dumps(evidence.metrics),
                "first_seen_at": _dt_from_iso(evidence.first_seen_at),
                "last_seen_at": _dt_from_iso(evidence.last_seen_at),
            }
            for evidence in result.evidence
        ]
        bridge_rows = [
            {
                "run_id": result.run_id,
                "entity_id": pair.entity_id,
                "source_tx_hash": pair.source_tx,
                "destination_tx_hash": pair.destination_tx,
                "bridge_contract": pair.bridge_contract,
                "token_symbol": pair.token,
                "amount": pair.amount,
                "latency_seconds": pair.latency_seconds,
                "confidence_score": pair.confidence_score,
                "source_address": pair.source_address,
                "destination_address": pair.destination_address,
                "details_json": json_dumps(pair.details),
            }
            for pair in result.bridge_pairs
        ]
        alert_rows = [
            {
                "run_id": result.run_id,
                "entity_id": alert.entity_id,
                "entity_type": alert.entity_type,
                "confidence_score": alert.confidence_score,
                "layering_score": alert.layering_score,
                "placement_score": alert.placement_score,
                "placement_confidence": alert.placement_confidence,
                "method_scores_json": json_dumps(alert.method_scores),
                "methods_json": json_dumps(alert.methods),
                "reasons_json": json_dumps(alert.reasons),
                "supporting_tx_hashes_json": json_dumps(alert.supporting_tx_hashes),
                "evidence_ids_json": json_dumps(alert.evidence_ids),
                "metrics_json": json_dumps(alert.metrics),
                "first_seen_at": _dt_from_iso(alert.first_seen_at),
                "last_seen_at": _dt_from_iso(alert.last_seen_at),
            }
            for alert in result.alerts
        ]

        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        INSERT INTO layering_runs (
                            id,
                            source,
                            placement_run_id,
                            status,
                            started_at,
                            completed_at,
                            summary_json
                        )
                        VALUES (
                            :id,
                            :source,
                            :placement_run_id,
                            'completed',
                            :started_at,
                            :completed_at,
                            :summary_json
                        )
                        """
                    ),
                    {
                        "id": result.run_id,
                        "source": result.summary.get("source", "auto"),
                        "placement_run_id": result.summary.get("placement_run_id"),
                        "started_at": completed_at,
                        "completed_at": completed_at,
                        "summary_json": json_dumps(result.summary),
                    },
                )

                if entity_rows:
                    conn.execute(
                        text(
                            """
                            INSERT INTO layering_entities (
                                run_id,
                                entity_id,
                                entity_type,
                                placement_score,
                                placement_confidence,
                                placement_behaviors_json,
                                validation_status,
                                validation_confidence,
                                source_kind,
                                address_count,
                                first_seen_at,
                                last_seen_at,
                                metrics_json
                            )
                            VALUES (
                                :run_id,
                                :entity_id,
                                :entity_type,
                                :placement_score,
                                :placement_confidence,
                                :placement_behaviors_json,
                                :validation_status,
                                :validation_confidence,
                                :source_kind,
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
                    for batch in chunked(entity_address_rows, 1000):
                        conn.execute(
                            text(
                                """
                                INSERT INTO layering_entity_addresses (run_id, entity_id, address)
                                VALUES (:run_id, :entity_id, :address)
                                """
                            ),
                            batch,
                        )
                if detection_rows:
                    conn.execute(
                        text(
                            """
                            INSERT INTO layering_detector_hits (
                                run_id,
                                entity_id,
                                entity_type,
                                detector_type,
                                confidence_score,
                                summary_text,
                                score_components_json,
                                metrics_json,
                                supporting_tx_hashes_json,
                                evidence_ids_json,
                                first_observed_at,
                                last_observed_at
                            )
                            VALUES (
                                :run_id,
                                :entity_id,
                                :entity_type,
                                :detector_type,
                                :confidence_score,
                                :summary_text,
                                :score_components_json,
                                :metrics_json,
                                :supporting_tx_hashes_json,
                                :evidence_ids_json,
                                :first_observed_at,
                                :last_observed_at
                            )
                            """
                        ),
                        detection_rows,
                    )
                if evidence_rows:
                    for batch in chunked(evidence_rows, 1000):
                        conn.execute(
                            text(
                                """
                                INSERT INTO layering_evidence (
                                    run_id,
                                    evidence_id,
                                    entity_id,
                                    detector_type,
                                    evidence_type,
                                    title,
                                    summary_text,
                                    entity_ids_json,
                                    tx_hashes_json,
                                    path_json,
                                    metrics_json,
                                    first_seen_at,
                                    last_seen_at
                                )
                                VALUES (
                                    :run_id,
                                    :evidence_id,
                                    :entity_id,
                                    :detector_type,
                                    :evidence_type,
                                    :title,
                                    :summary_text,
                                    :entity_ids_json,
                                    :tx_hashes_json,
                                    :path_json,
                                    :metrics_json,
                                    :first_seen_at,
                                    :last_seen_at
                                )
                                """
                            ),
                            batch,
                        )
                if bridge_rows:
                    conn.execute(
                        text(
                            """
                            INSERT INTO layering_bridge_pairs (
                                run_id,
                                entity_id,
                                source_tx_hash,
                                destination_tx_hash,
                                bridge_contract,
                                token_symbol,
                                amount,
                                latency_seconds,
                                confidence_score,
                                source_address,
                                destination_address,
                                details_json
                            )
                            VALUES (
                                :run_id,
                                :entity_id,
                                :source_tx_hash,
                                :destination_tx_hash,
                                :bridge_contract,
                                :token_symbol,
                                :amount,
                                :latency_seconds,
                                :confidence_score,
                                :source_address,
                                :destination_address,
                                :details_json
                            )
                            """
                        ),
                        bridge_rows,
                    )
                if alert_rows:
                    conn.execute(
                        text(
                            """
                            INSERT INTO layering_alerts (
                                run_id,
                                entity_id,
                                entity_type,
                                confidence_score,
                                layering_score,
                                placement_score,
                                placement_confidence,
                                method_scores_json,
                                methods_json,
                                reasons_json,
                                supporting_tx_hashes_json,
                                evidence_ids_json,
                                metrics_json,
                                first_seen_at,
                                last_seen_at
                            )
                            VALUES (
                                :run_id,
                                :entity_id,
                                :entity_type,
                                :confidence_score,
                                :layering_score,
                                :placement_score,
                                :placement_confidence,
                                :method_scores_json,
                                :methods_json,
                                :reasons_json,
                                :supporting_tx_hashes_json,
                                :evidence_ids_json,
                                :metrics_json,
                                :first_seen_at,
                                :last_seen_at
                            )
                            """
                        ),
                        alert_rows,
                    )

            logger.info(
                "Persisted layering run %s with %d alerts",
                result.run_id,
                len(result.alerts),
            )
        finally:
            engine.dispose()
