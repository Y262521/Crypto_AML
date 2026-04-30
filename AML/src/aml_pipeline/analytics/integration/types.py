"""Shared types for integration-stage analytics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def iso_from_ts(value: float | None) -> str | None:
    if not value:
        return None
    return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()


def dt_from_ts(value: float | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(float(value), tz=timezone.utc).replace(tzinfo=None)


def json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def chunked(items: list[Any], size: int = 500):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def stable_run_id(generated_at: datetime) -> str:
    digest = hashlib.sha1(generated_at.isoformat().encode()).hexdigest()[:8].upper()
    return f"INT-{generated_at.strftime('%Y%m%d%H%M%S')}-{digest}"


# ── Signal dataclasses ────────────────────────────────────────────────────────

@dataclass
class ConvergenceSignal:
    """Fan-in: many wallets → one central address."""
    entity_id: str
    entity_type: str
    addresses: list[str]
    convergence_address: str
    sender_count: int
    total_value_eth: float
    confidence_score: float
    supporting_tx_hashes: list[str]
    first_seen_at: str | None
    last_seen_at: str | None
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class DormancySignal:
    """Wallet inactive for N days then suddenly active with high value."""
    entity_id: str
    entity_type: str
    addresses: list[str]
    dormancy_seconds: float
    activation_value_eth: float
    confidence_score: float
    supporting_tx_hashes: list[str]
    dormancy_start_at: str | None
    activation_at: str | None
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class TerminalNodeSignal:
    """Address receives funds but never sends — exit point."""
    entity_id: str
    entity_type: str
    addresses: list[str]
    terminal_address: str
    total_received_eth: float
    is_known_exchange: bool
    confidence_score: float
    supporting_tx_hashes: list[str]
    first_seen_at: str | None
    last_seen_at: str | None
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReaggregationSignal:
    """Many small inputs → one large output (reverse of structuring)."""
    entity_id: str
    entity_type: str
    addresses: list[str]
    input_count: int
    input_total_eth: float
    output_value_eth: float
    reaggregation_ratio: float
    confidence_score: float
    supporting_tx_hashes: list[str]
    first_seen_at: str | None
    last_seen_at: str | None
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class IntegrationAlert:
    """Final scored alert combining all integration signals."""
    entity_id: str
    entity_type: str
    addresses: list[str]
    integration_score: float          # 0–1 combined score
    confidence_score: float           # highest individual signal
    signals_fired: list[str]          # which detectors triggered
    signal_scores: dict[str, float]   # per-signal scores
    reasons: list[str]                # human-readable explanations
    supporting_tx_hashes: list[str]
    layering_score: float             # from upstream layering stage
    placement_score: float            # from upstream placement stage
    first_seen_at: str | None
    last_seen_at: str | None
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class IntegrationAnalysisResult:
    run_id: str
    generated_at: str
    summary: dict[str, Any]
    convergence_signals: list[ConvergenceSignal]
    dormancy_signals: list[DormancySignal]
    terminal_signals: list[TerminalNodeSignal]
    reaggregation_signals: list[ReaggregationSignal]
    alerts: list[IntegrationAlert]

    def analyst_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "entity_id": a.entity_id,
                "entity_type": a.entity_type,
                "addresses": a.addresses,
                "address_count": len(a.addresses),
                "integration_score": a.integration_score,
                "confidence_score": a.confidence_score,
                "signals_fired": a.signals_fired,
                "primary_signal": a.signals_fired[0] if a.signals_fired else None,
                "reason": a.reasons[0] if a.reasons else None,
                "layering_score": a.layering_score,
                "placement_score": a.placement_score,
                "supporting_tx_hashes": a.supporting_tx_hashes,
                "first_seen_at": a.first_seen_at,
                "last_seen_at": a.last_seen_at,
                "metrics": a.metrics,
            }
            for a in self.alerts
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "summary": self.summary,
            "convergence_signals": [s.__dict__ for s in self.convergence_signals],
            "dormancy_signals": [s.__dict__ for s in self.dormancy_signals],
            "terminal_signals": [s.__dict__ for s in self.terminal_signals],
            "reaggregation_signals": [s.__dict__ for s in self.reaggregation_signals],
            "alerts": [a.__dict__ for a in self.alerts],
            "table_rows": self.analyst_rows(),
        }
