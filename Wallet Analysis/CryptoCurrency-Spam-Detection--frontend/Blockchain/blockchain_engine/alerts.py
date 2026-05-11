from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AlertEngine:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "alerts.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def evaluate(
        self,
        *,
        address: str,
        chain: str,
        risk_score: int,
        risk_label: str,
        watchlist_entries: list[dict[str, Any]],
        clusters: list[dict[str, Any]],
        transactions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        if risk_score >= 70:
            alerts.append(
                self._alert(
                    "risk_threshold",
                    "high",
                    address,
                    chain,
                    {"risk_score": risk_score, "risk_label": risk_label},
                )
            )

        if watchlist_entries:
            alerts.append(
                self._alert(
                    "watchlist_match",
                    "high",
                    address,
                    chain,
                    {"matches": watchlist_entries},
                )
            )

        if clusters:
            alerts.append(
                self._alert(
                    "cluster_activity",
                    "medium",
                    address,
                    chain,
                    {"clusters": clusters},
                )
            )
            # Add specific trigger for high-risk clusters
            if any("rapid_funding" in c["type"] for c in clusters):
                alerts.append(
                    self._alert(
                        "high_risk_cluster_interaction",
                        "high",
                        address,
                        chain,
                        {"reason": "Interaction with rapid funding cluster detected"},
                    )
                )

        if self._has_large_movement_after_inactivity(transactions):
            alerts.append(
                self._alert(
                    "large_post_inactivity_movement",
                    "medium",
                    address,
                    chain,
                    {"transaction_count": len(transactions)},
                )
            )

        self._write(alerts)
        return alerts

    def list_alerts(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, alerts: list[dict[str, Any]]) -> None:
        existing = self.list_alerts()
        existing.extend(alerts)
        self.path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    @staticmethod
    def _alert(alert_type: str, severity: str, address: str, chain: str, details: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": alert_type,
            "severity": severity,
            "address": address,
            "chain": chain,
            "details": details,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

    @staticmethod
    def _has_large_movement_after_inactivity(transactions: list[dict[str, Any]]) -> bool:
        if len(transactions) < 2:
            return False
        timestamps = sorted(
            datetime.fromisoformat(tx["timestamp"].replace("Z", "+00:00"))
            for tx in transactions
        )
        gap = timestamps[-1] - timestamps[0]
        largest = max(tx["value"] for tx in transactions)
        return gap.days >= 1 and largest > 1
