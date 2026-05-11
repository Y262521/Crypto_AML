from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class NormalizedTransaction:
    chain: str
    tx_hash: str
    block_number: int | None
    timestamp: datetime
    from_address: str
    to_address: str | None
    value: float
    asset: str
    direction: str
    tx_type: str = "transfer"
    method_id: str | None = None
    token_contract: str | None = None
    token_symbol: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.astimezone(timezone.utc).isoformat()
        return payload


@dataclass(slots=True)
class Detection:
    detector: str
    label: str
    severity: str
    confidence: float
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RiskResult:
    address: str
    chain: str
    score: int
    reasons: list[str]
    label: str = "safe"
    entity_label: str = "user wallet"
    detections: list[Detection] = field(default_factory=list)
    transactions: list[NormalizedTransaction] = field(default_factory=list)


@dataclass(slots=True)
class ScreeningMatch:
    address: str
    category: str
    source: str
    score: int
    label: str | None = None


@dataclass(slots=True)
class ScreeningResult:
    address: str
    chain: str
    matched: bool
    entity_label: str = "user wallet"
    matches: list[ScreeningMatch] = field(default_factory=list)


@dataclass(slots=True)
class GraphNode:
    id: str
    risk: str
    score: int
    entity_label: str = "user wallet"


@dataclass(slots=True)
class GraphEdge:
    source: str
    target: str
    tx_hash: str
    value: float
    asset: str
    timestamp: str
