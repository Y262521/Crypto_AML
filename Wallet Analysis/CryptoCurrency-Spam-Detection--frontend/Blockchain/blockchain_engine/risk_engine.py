from __future__ import annotations

import json
from pathlib import Path

from blockchain_engine.models import Detection, NormalizedTransaction, RiskResult


class RiskEngine:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.flagged_db_path = self.data_dir / "flagged_addresses.json"

    def evaluate(
        self,
        chain: str,
        address: str,
        transactions: list[NormalizedTransaction],
        detections: list[Detection],
        entity_label: str = "user wallet",
    ) -> RiskResult:
        score = 0
        reasons: list[str] = []
        flagged_db = self._load_flagged_db()
        address_key = address.lower()

        # 1. Flagged Database Match
        for record in flagged_db.get(chain, []) + flagged_db.get("global", []):
            if record["address"].lower() == address_key:
                score += int(record.get("score", 60))
                reasons.append(f"Flagged by {record['source']}: {record['category']}")

        # 2. Counterparty analysis
        unique_counterparties = {
            str(tx.to_address).lower()
            for tx in transactions
            if tx.to_address and str(tx.to_address).lower() != address_key
        }
        if len(unique_counterparties) >= 10:
            score += 10
            reasons.append("High counterparty fan-out detected")

        # 3. Activity burst
        if len(transactions) >= 15:
            score += 15
            reasons.append("High activity burst detected")

        # 4. Flow pattern
        outgoing_ratio = self._outgoing_ratio(transactions)
        if outgoing_ratio > 0.9 and len(transactions) >= 5:
            score += 10
            reasons.append("Mostly outbound flow pattern")

        # 5. Fast movement of funds (In -> Out in short window)
        if self._detect_fast_movement(transactions, address_key):
            score += 20
            reasons.append("Fast movement of funds after receipt")

        # 6. Interaction with flagged addresses (Detections)
        approval_count = sum(1 for item in detections if item.label == "approval")
        if approval_count >= 3:
            score += 10
            reasons.append("Repeated approval interactions")

        if any(item.label in {"tornado_cash", "bridge"} for item in detections):
            score += 25
            reasons.append("Mixer or bridge exposure detected")

        if any(item.label == "large_transfer" for item in detections):
            score += 5
            reasons.append("Large transfer detected")

        # 7. Entity context
        if entity_label == "bot":
            score += 15
            reasons.append("Programmatic bot-like behavior")
        elif entity_label == "mixer":
            score += 30
            reasons.append("Classified as a mixer/anonymizer")

        score = min(score, 100)
        label = "safe"
        if score >= 70:
            label = "high_risk"
        elif score >= 30:
            label = "suspicious"
        return RiskResult(
            address=address,
            chain=chain,
            score=score,
            reasons=reasons,
            label=label,
            entity_label=entity_label,
            detections=detections,
            transactions=transactions,
        )

    def _detect_fast_movement(self, transactions: list[NormalizedTransaction], address: str) -> bool:
        if len(transactions) < 2:
            return False
        
        # Sort by timestamp
        sorted_txs = sorted(transactions, key=lambda x: x.timestamp)
        for i in range(len(sorted_txs) - 1):
            curr = sorted_txs[i]
            next_tx = sorted_txs[i+1]
            
            # If current is IN and next is OUT
            if curr.direction == "in" and next_tx.direction == "out":
                delta = (next_tx.timestamp - curr.timestamp).total_seconds()
                # If moved within 10 minutes
                if 0 < delta < 600:
                    return True
        return False

    def _load_flagged_db(self) -> dict:
        if not self.flagged_db_path.exists():
            return {"global": []}
        try:
            return json.loads(self.flagged_db_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"global": []}

    @staticmethod
    def _outgoing_ratio(transactions: list[NormalizedTransaction]) -> float:
        if not transactions:
            return 0.0
        outgoing = sum(1 for tx in transactions if tx.direction == "out")
        return outgoing / len(transactions)
