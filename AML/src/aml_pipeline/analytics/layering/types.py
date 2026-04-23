"""Shared types and helpers for layering analytics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...clustering.base import TxRecord
    from ...clustering.graph_builder import GraphArtifacts
    from ...config import Config
    from ..placement import EntityEdge, EntityProfile, PlacementEntity
    from .service_profiles import ServiceRegistry


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def dt_from_ts(value: float | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(float(value), tz=timezone.utc).replace(tzinfo=None)


def iso_from_ts(value: float | None) -> str | None:
    if not value:
        return None
    return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()


def json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def chunked(items: list[Any], size: int = 500):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def stable_run_id(generated_at: datetime, prefix: str = "LYR") -> str:
    digest = hashlib.sha1(generated_at.isoformat().encode()).hexdigest()[:8].upper()
    return f"{prefix}-{generated_at.strftime('%Y%m%d%H%M%S')}-{digest}"


def stable_evidence_id(entity_id: str, detector_type: str, ordinal: int) -> str:
    digest = hashlib.sha1(f"{entity_id}|{detector_type}|{ordinal}".encode()).hexdigest()[:12].upper()
    return f"LEV-{digest}"


@dataclass
class LayeringSeed:
    entity_id: str
    entity_type: str
    addresses: list[str]
    placement_score: float
    placement_confidence: float
    placement_behaviors: list[str]
    first_seen_at: str | None
    last_seen_at: str | None
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectorHit:
    entity_id: str
    entity_type: str
    detector_type: str
    confidence_score: float
    summary: str
    score_components: dict[str, float]
    metrics: dict[str, Any]
    supporting_tx_hashes: list[str]
    evidence_ids: list[str]
    first_observed_at: str | None
    last_observed_at: str | None


@dataclass
class EvidenceRecord:
    evidence_id: str
    entity_id: str
    detector_type: str
    evidence_type: str
    title: str
    summary: str
    entity_ids: list[str]
    tx_hashes: list[str]
    path: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    first_seen_at: str | None = None
    last_seen_at: str | None = None


@dataclass
class BridgePairRecord:
    entity_id: str
    source_tx: str
    destination_tx: str
    bridge_contract: str
    token: str
    amount: float
    latency_seconds: float
    confidence_score: float
    source_address: str
    destination_address: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class LayeringAlert:
    entity_id: str
    entity_type: str
    addresses: list[str]
    confidence_score: float
    layering_score: float
    placement_score: float
    placement_confidence: float
    method_scores: dict[str, float]
    methods: list[str]
    reasons: list[str]
    supporting_tx_hashes: list[str]
    evidence_ids: list[str]
    first_seen_at: str | None
    last_seen_at: str | None
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectorOutput:
    hits: list[DetectorHit] = field(default_factory=list)
    evidence: list[EvidenceRecord] = field(default_factory=list)
    bridge_pairs: list[BridgePairRecord] = field(default_factory=list)


@dataclass(frozen=True)
class LayeringContext:
    cfg: "Config"
    transactions: list["TxRecord"]
    artifacts: "GraphArtifacts"
    seeds: dict[str, LayeringSeed]
    entities: dict[str, "PlacementEntity"]
    address_to_entity: dict[str, str]
    profiles: dict[str, "EntityProfile"]
    entity_edges: dict[tuple[str, str], "EntityEdge"]
    incoming_entity_edges: dict[str, list["EntityEdge"]]
    outgoing_entity_edges: dict[str, list["EntityEdge"]]
    tx_by_hash: dict[str, "TxRecord"]
    service_registry: "ServiceRegistry"
    address_labels: dict[str, set[str]]
    entity_labels: dict[str, set[str]]
    address_first_seen: dict[str, float]
    address_last_seen: dict[str, float]
    address_degree: dict[str, int]
    address_tx_count: dict[str, int]

    def labels_for_address(self, address: str | None) -> set[str]:
        if not address:
            return set()
        return set(self.address_labels.get(address.lower().strip(), set()))

    def labels_for_entity(self, entity_id: str | None) -> set[str]:
        if not entity_id:
            return set()
        return set(self.entity_labels.get(entity_id, set()))

    def entity_for_address(self, address: str | None) -> str | None:
        if not address:
            return None
        return self.address_to_entity.get(address.lower().strip())

    def is_service_address(self, address: str | None) -> bool:
        labels = self.labels_for_address(address)
        return bool(labels & {"mixer", "bridge", "exchange", "service_like"})

    def is_exchange_like(self, address: str | None) -> bool:
        labels = self.labels_for_address(address)
        return bool(labels & {"exchange", "service_like"})

    def is_fresh_address(
        self,
        address: str | None,
        observed_at: float,
        max_age_seconds: float = 7200.0,
        max_degree: int = 2,
    ) -> bool:
        if not address:
            return False
        normalized = address.lower().strip()
        first_seen = self.address_first_seen.get(normalized)
        if first_seen is None:
            return False
        age_seconds = max(0.0, float(observed_at or 0.0) - float(first_seen))
        return age_seconds <= max_age_seconds and self.address_degree.get(normalized, 0) <= max_degree


@dataclass
class LayeringAnalysisResult:
    run_id: str
    generated_at: str
    summary: dict[str, Any]
    seeds: list[LayeringSeed]
    detections: list[DetectorHit]
    evidence: list[EvidenceRecord]
    bridge_pairs: list[BridgePairRecord]
    alerts: list[LayeringAlert]

    def analyst_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "entity_id": alert.entity_id,
                "entity_type": alert.entity_type,
                "addresses": alert.addresses,
                "address_count": len(alert.addresses),
                "confidence": alert.confidence_score,
                "layering_score": alert.layering_score,
                "placement_score": alert.placement_score,
                "placement_confidence": alert.placement_confidence,
                "methods": alert.methods,
                "primary_method": alert.methods[0] if alert.methods else None,
                "reason": alert.reasons[0] if alert.reasons else None,
                "evidence_count": len(alert.evidence_ids),
                "supporting_tx_hashes": alert.supporting_tx_hashes,
                "first_seen_at": alert.first_seen_at,
                "last_seen_at": alert.last_seen_at,
                "metrics": alert.metrics,
            }
            for alert in self.alerts
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "summary": self.summary,
            "seeds": [seed.__dict__ for seed in self.seeds],
            "detections": [hit.__dict__ for hit in self.detections],
            "evidence": [evidence.__dict__ for evidence in self.evidence],
            "bridge_pairs": [pair.__dict__ for pair in self.bridge_pairs],
            "alerts": [alert.__dict__ for alert in self.alerts],
            "table_rows": self.analyst_rows(),
        }
