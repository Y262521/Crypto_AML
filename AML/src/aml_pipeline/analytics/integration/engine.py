
"""Integration-stage AML analytics engine.

Implements 5 algorithms to detect the integration stage of money laundering:
  1. Convergence / Fan-In Detection
  2. Dormancy-to-Activation Pattern
  3. Terminal Node Attribution (Exit Detection)
  4. Value Reaggregation Scrutiny
  5. Confidence Aggregation Scoring
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import logging
import statistics
from typing import Any

from sqlalchemy import text

from ...config import Config, load_config
from ...etl.load.mariadb_loader import create_tables_if_not_exist
from ...utils.connections import get_maria_engine
from ..layering.engine import LayeringAnalysisEngine
from ..layering.types import LayeringAnalysisResult
from .types import (
    ConvergenceSignal,
    DormancySignal,
    IntegrationAlert,
    IntegrationAnalysisResult,
    ReaggregationSignal,
    TerminalNodeSignal,
    clamp,
    chunked,
    dt_from_ts,
    iso_from_ts,
    json_dumps,
    stable_run_id,
)

logger = logging.getLogger(__name__)

# ── Known exchange / exit-point address prefixes (first 8 chars lowercase) ───
# Extend this list with real exchange hot-wallet addresses for production use.
_KNOWN_EXIT_PREFIXES: frozenset[str] = frozenset({
    "0xd551234",  # Binance hot wallet prefix example
    "0xa9d1e08",  # Coinbase example
    "0x3f5ce5f",  # Binance 2
    "0xbe0eb53",  # Binance 3
    "0x564286",   # Binance 4
    "0x4e9ce36",  # Binance 5
})

# Minimum dormancy before activation is suspicious (30 days)
_DEFAULT_DORMANCY_SECONDS = 30 * 24 * 3600
# Minimum activation value to flag dormancy (1 ETH)
_DEFAULT_DORMANCY_MIN_ETH = 1.0
# Minimum senders for fan-in convergence
_DEFAULT_CONVERGENCE_MIN_SENDERS = 5
# Minimum inputs for reaggregation
_DEFAULT_REAGGREGATION_MIN_INPUTS = 4
# Minimum reaggregation ratio (output / total_input)
_DEFAULT_REAGGREGATION_MIN_RATIO = 0.70


def _is_known_exit(address: str) -> bool:
    """Return True if address matches a known exchange/exit prefix."""
    if not address:
        return False
    normalized = address.lower().strip()
    return any(normalized.startswith(prefix) for prefix in _KNOWN_EXIT_PREFIXES)


class IntegrationAnalysisEngine:
    """
    Detects the integration stage of money laundering using 5 algorithms.

    Can run standalone or downstream of LayeringAnalysisEngine to inherit
    placement and layering scores for confidence aggregation.
    """

    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or load_config()
        self._layering_engine = LayeringAnalysisEngine(cfg=self.cfg)

    # ── Public API ────────────────────────────────────────────────────────────

    def run(
        self,
        source: str = "auto",
        persist: bool = False,
        layering_result: LayeringAnalysisResult | None = None,
    ) -> IntegrationAnalysisResult:
        """Run all 5 integration detectors and return scored alerts."""
        transactions = list(
            self._layering_engine.clustering_engine.adapter.iter_transactions(source=source)
        )
        transactions.sort(key=lambda tx: (float(tx.timestamp or 0.0), tx.tx_hash))
        generated_at = datetime.now(timezone.utc)
        run_id = stable_run_id(generated_at)

        logger.info("Integration analysis loaded %d transactions", len(transactions))

        if not transactions:
            return self._empty_result(run_id, generated_at.isoformat(), source)

        # Build address-level stats from transactions
        address_total_in: dict[str, float] = defaultdict(float)
        address_total_out: dict[str, float] = defaultdict(float)
        address_first_seen: dict[str, float] = {}
        address_last_seen: dict[str, float] = {}
        address_in_txs: dict[str, list] = defaultdict(list)
        address_out_txs: dict[str, list] = defaultdict(list)

        for tx in transactions:
            ts = float(tx.timestamp or 0.0)
            val = float(tx.value_eth or 0.0)
            if tx.from_address:
                addr = tx.from_address.lower()
                address_total_out[addr] += val
                address_out_txs[addr].append(tx)
                address_first_seen[addr] = min(address_first_seen.get(addr, ts), ts)
                address_last_seen[addr] = max(address_last_seen.get(addr, ts), ts)
            if tx.to_address:
                addr = tx.to_address.lower()
                address_total_in[addr] += val
                address_in_txs[addr].append(tx)
                address_first_seen[addr] = min(address_first_seen.get(addr, ts), ts)
                address_last_seen[addr] = max(address_last_seen.get(addr, ts), ts)

        # Build layering score lookup for confidence aggregation
        layering_scores: dict[str, float] = {}
        placement_scores: dict[str, float] = {}
        if layering_result is not None:
            for alert in layering_result.alerts:
                for addr in alert.addresses:
                    layering_scores[addr.lower()] = max(
                        layering_scores.get(addr.lower(), 0.0),
                        float(alert.layering_score or 0.0),
                    )
                    placement_scores[addr.lower()] = max(
                        placement_scores.get(addr.lower(), 0.0),
                        float(alert.placement_score or 0.0),
                    )

        # Run the 4 detection algorithms
        convergence = self._detect_convergence(
            transactions, address_in_txs, address_total_in
        )
        dormancy = self._detect_dormancy(
            transactions, address_first_seen, address_last_seen,
            address_out_txs, address_total_out
        )
        terminal = self._detect_terminal_nodes(
            address_total_in, address_total_out, address_in_txs
        )
        reaggregation = self._detect_reaggregation(
            address_in_txs, address_out_txs, address_total_in, address_total_out
        )

        # Algorithm 5: Confidence Aggregation Scoring
        alerts = self._aggregate_scores(
            convergence, dormancy, terminal, reaggregation,
            layering_scores, placement_scores,
        )

        summary = {
            "source": source,
            "transactions": len(transactions),
            "convergence_signals": len(convergence),
            "dormancy_signals": len(dormancy),
            "terminal_signals": len(terminal),
            "reaggregation_signals": len(reaggregation),
            "alerts": len(alerts),
            "high_confidence_alerts": sum(1 for a in alerts if a.integration_score >= 0.70),
        }

        result = IntegrationAnalysisResult(
            run_id=run_id,
            generated_at=generated_at.isoformat(),
            summary=summary,
            convergence_signals=sorted(convergence, key=lambda s: s.confidence_score, reverse=True),
            dormancy_signals=sorted(dormancy, key=lambda s: s.confidence_score, reverse=True),
            terminal_signals=sorted(terminal, key=lambda s: s.confidence_score, reverse=True),
            reaggregation_signals=sorted(reaggregation, key=lambda s: s.confidence_score, reverse=True),
            alerts=sorted(alerts, key=lambda a: (a.integration_score, a.confidence_score), reverse=True),
        )

        if persist:
            self._persist(result)

        return result

    # ── Algorithm 1: Convergence / Fan-In Detection ───────────────────────────

    def _detect_convergence(
        self,
        transactions: list,
        address_in_txs: dict[str, list],
        address_total_in: dict[str, float],
    ) -> list[ConvergenceSignal]:
        """
        Detect addresses receiving from many distinct senders.
        Many wallets → one central address = consolidation before exit.
        """
        min_senders = max(
            2,
            int(getattr(self.cfg, "integration_convergence_min_senders", _DEFAULT_CONVERGENCE_MIN_SENDERS)),
        )
        signals: list[ConvergenceSignal] = []

        for addr, in_txs in address_in_txs.items():
            unique_senders = {tx.from_address.lower() for tx in in_txs if tx.from_address}
            if len(unique_senders) < min_senders:
                continue

            total_in = address_total_in.get(addr, 0.0)
            tx_hashes = [tx.tx_hash for tx in in_txs if tx.tx_hash]
            timestamps = [float(tx.timestamp or 0.0) for tx in in_txs]

            # Score: more senders = higher confidence, capped at 1.0
            sender_score = clamp(len(unique_senders) / (min_senders * 3))
            # Value score: higher total value = more suspicious
            value_score = clamp(total_in / 50.0)  # 50 ETH = max score
            confidence = clamp(sender_score * 0.6 + value_score * 0.4)

            if confidence < 0.30:
                continue

            signals.append(ConvergenceSignal(
                entity_id=addr,
                entity_type="address",
                addresses=[addr],
                convergence_address=addr,
                sender_count=len(unique_senders),
                total_value_eth=round(total_in, 8),
                confidence_score=round(confidence, 4),
                supporting_tx_hashes=sorted(set(tx_hashes))[:20],
                first_seen_at=iso_from_ts(min(timestamps)) if timestamps else None,
                last_seen_at=iso_from_ts(max(timestamps)) if timestamps else None,
                metrics={
                    "unique_senders": len(unique_senders),
                    "total_in_eth": round(total_in, 8),
                    "sender_score": round(sender_score, 4),
                    "value_score": round(value_score, 4),
                },
            ))

        logger.info("Convergence detector found %d signals", len(signals))
        return signals

    # ── Algorithm 2: Dormancy-to-Activation Pattern ───────────────────────────

    def _detect_dormancy(
        self,
        transactions: list,
        address_first_seen: dict[str, float],
        address_last_seen: dict[str, float],
        address_out_txs: dict[str, list],
        address_total_out: dict[str, float],
    ) -> list[DormancySignal]:
        """
        Detect wallets that were inactive for a long period then suddenly
        sent a high-value transaction. Classic cooling-off before integration.
        """
        min_dormancy = float(getattr(
            self.cfg, "integration_dormancy_min_seconds", _DEFAULT_DORMANCY_SECONDS
        ))
        min_activation_eth = float(getattr(
            self.cfg, "integration_dormancy_min_activation_eth", _DEFAULT_DORMANCY_MIN_ETH
        ))
        signals: list[DormancySignal] = []

        for addr, out_txs in address_out_txs.items():
            if len(out_txs) < 1:
                continue
            first_seen = address_first_seen.get(addr)
            if first_seen is None:
                continue

            # Sort outgoing transactions by time
            sorted_out = sorted(out_txs, key=lambda tx: float(tx.timestamp or 0.0))

            # Find the largest gap between consecutive outgoing transactions
            # or between first_seen and first outgoing tx
            timestamps = [float(tx.timestamp or 0.0) for tx in sorted_out]
            gaps: list[tuple[float, float, float]] = []  # (gap_seconds, before_ts, after_ts)

            # Gap from first_seen to first outgoing tx
            if timestamps:
                gap = timestamps[0] - first_seen
                if gap > 0:
                    gaps.append((gap, first_seen, timestamps[0]))

            # Gaps between consecutive outgoing txs
            for i in range(1, len(timestamps)):
                gap = timestamps[i] - timestamps[i - 1]
                if gap > 0:
                    gaps.append((gap, timestamps[i - 1], timestamps[i]))

            if not gaps:
                continue

            max_gap, dormancy_start, activation_ts = max(gaps, key=lambda g: g[0])
            if max_gap < min_dormancy:
                continue

            # Find the activation transaction (first tx after the gap)
            activation_txs = [
                tx for tx in sorted_out
                if float(tx.timestamp or 0.0) >= activation_ts
            ]
            if not activation_txs:
                continue

            activation_value = sum(float(tx.value_eth or 0.0) for tx in activation_txs[:3])
            if activation_value < min_activation_eth:
                continue

            # Score: longer dormancy + higher activation value = more suspicious
            dormancy_days = max_gap / 86400.0
            dormancy_score = clamp(dormancy_days / 90.0)   # 90 days = max score
            value_score = clamp(activation_value / 10.0)   # 10 ETH = max score
            confidence = clamp(dormancy_score * 0.55 + value_score * 0.45)

            if confidence < 0.30:
                continue

            signals.append(DormancySignal(
                entity_id=addr,
                entity_type="address",
                addresses=[addr],
                dormancy_seconds=round(max_gap, 2),
                activation_value_eth=round(activation_value, 8),
                confidence_score=round(confidence, 4),
                supporting_tx_hashes=[tx.tx_hash for tx in activation_txs[:10] if tx.tx_hash],
                dormancy_start_at=iso_from_ts(dormancy_start),
                activation_at=iso_from_ts(activation_ts),
                metrics={
                    "dormancy_days": round(dormancy_days, 2),
                    "activation_value_eth": round(activation_value, 8),
                    "dormancy_score": round(dormancy_score, 4),
                    "value_score": round(value_score, 4),
                },
            ))

        logger.info("Dormancy detector found %d signals", len(signals))
        return signals

    # ── Algorithm 3: Terminal Node Attribution (Exit Detection) ───────────────

    def _detect_terminal_nodes(
        self,
        address_total_in: dict[str, float],
        address_total_out: dict[str, float],
        address_in_txs: dict[str, list],
    ) -> list[TerminalNodeSignal]:
        """
        Detect addresses that only receive and never send (terminal nodes).
        If the terminal address is a known exchange, it's a confirmed exit point.
        """
        signals: list[TerminalNodeSignal] = []

        for addr, total_in in address_total_in.items():
            total_out = address_total_out.get(addr, 0.0)
            if total_out > 0.0:
                continue  # Not a terminal node — it sends too
            if total_in < 0.01:
                continue  # Dust, ignore

            in_txs = address_in_txs.get(addr, [])
            if not in_txs:
                continue

            is_exit = _is_known_exit(addr)
            timestamps = [float(tx.timestamp or 0.0) for tx in in_txs]
            tx_hashes = [tx.tx_hash for tx in in_txs if tx.tx_hash]

            # Score: known exchange = high confidence; unknown terminal = moderate
            base_score = 0.85 if is_exit else 0.50
            # Value boost: more ETH received = more suspicious
            value_score = clamp(total_in / 20.0)  # 20 ETH = max boost
            confidence = clamp(base_score * 0.70 + value_score * 0.30)

            if confidence < 0.35:
                continue

            signals.append(TerminalNodeSignal(
                entity_id=addr,
                entity_type="address",
                addresses=[addr],
                terminal_address=addr,
                total_received_eth=round(total_in, 8),
                is_known_exchange=is_exit,
                confidence_score=round(confidence, 4),
                supporting_tx_hashes=sorted(set(tx_hashes))[:20],
                first_seen_at=iso_from_ts(min(timestamps)) if timestamps else None,
                last_seen_at=iso_from_ts(max(timestamps)) if timestamps else None,
                metrics={
                    "total_received_eth": round(total_in, 8),
                    "is_known_exchange": is_exit,
                    "incoming_tx_count": len(in_txs),
                    "value_score": round(value_score, 4),
                },
            ))

        logger.info("Terminal node detector found %d signals", len(signals))
        return signals

    # ── Algorithm 4: Value Reaggregation Scrutiny ─────────────────────────────

    def _detect_reaggregation(
        self,
        address_in_txs: dict[str, list],
        address_out_txs: dict[str, list],
        address_total_in: dict[str, float],
        address_total_out: dict[str, float],
    ) -> list[ReaggregationSignal]:
        """
        Detect addresses that receive many small inputs then send one large output.
        This is the reverse of structuring — reassembly of fragmented funds.
        """
        min_inputs = max(
            2,
            int(getattr(self.cfg, "integration_reaggregation_min_inputs", _DEFAULT_REAGGREGATION_MIN_INPUTS)),
        )
        min_ratio = float(getattr(
            self.cfg, "integration_reaggregation_min_ratio", _DEFAULT_REAGGREGATION_MIN_RATIO
        ))
        signals: list[ReaggregationSignal] = []

        for addr in set(address_in_txs) & set(address_out_txs):
            in_txs = address_in_txs[addr]
            out_txs = address_out_txs[addr]

            if len(in_txs) < min_inputs:
                continue
            if len(out_txs) == 0:
                continue

            total_in = address_total_in.get(addr, 0.0)
            total_out = address_total_out.get(addr, 0.0)

            if total_in < 0.1 or total_out < 0.1:
                continue

            # Reaggregation ratio: how much of what came in went out as one flow
            ratio = total_out / total_in if total_in > 0 else 0.0
            if ratio < min_ratio:
                continue

            # Check that inputs are many small amounts and output is fewer larger amounts
            in_values = [float(tx.value_eth or 0.0) for tx in in_txs if float(tx.value_eth or 0.0) > 0]
            out_values = [float(tx.value_eth or 0.0) for tx in out_txs if float(tx.value_eth or 0.0) > 0]

            if not in_values or not out_values:
                continue

            avg_in = sum(in_values) / len(in_values)
            avg_out = sum(out_values) / len(out_values)

            # Reaggregation: average output should be larger than average input
            if avg_out <= avg_in:
                continue

            all_timestamps = [float(tx.timestamp or 0.0) for tx in in_txs + out_txs]
            all_tx_hashes = [tx.tx_hash for tx in in_txs + out_txs if tx.tx_hash]

            # Score: more inputs + higher ratio = more suspicious
            input_score = clamp(len(in_txs) / (min_inputs * 4))
            ratio_score = clamp((ratio - min_ratio) / (1.0 - min_ratio))
            size_contrast = clamp((avg_out - avg_in) / max(avg_in, 0.001) / 10.0)
            confidence = clamp(input_score * 0.35 + ratio_score * 0.40 + size_contrast * 0.25)

            if confidence < 0.30:
                continue

            signals.append(ReaggregationSignal(
                entity_id=addr,
                entity_type="address",
                addresses=[addr],
                input_count=len(in_txs),
                input_total_eth=round(total_in, 8),
                output_value_eth=round(total_out, 8),
                reaggregation_ratio=round(ratio, 4),
                confidence_score=round(confidence, 4),
                supporting_tx_hashes=sorted(set(all_tx_hashes))[:20],
                first_seen_at=iso_from_ts(min(all_timestamps)) if all_timestamps else None,
                last_seen_at=iso_from_ts(max(all_timestamps)) if all_timestamps else None,
                metrics={
                    "input_count": len(in_txs),
                    "output_count": len(out_txs),
                    "avg_input_eth": round(avg_in, 8),
                    "avg_output_eth": round(avg_out, 8),
                    "reaggregation_ratio": round(ratio, 4),
                    "input_score": round(input_score, 4),
                    "ratio_score": round(ratio_score, 4),
                },
            ))

        logger.info("Reaggregation detector found %d signals", len(signals))
        return signals

    # ── Algorithm 5: Confidence Aggregation Scoring ───────────────────────────

    def _aggregate_scores(
        self,
        convergence: list[ConvergenceSignal],
        dormancy: list[DormancySignal],
        terminal: list[TerminalNodeSignal],
        reaggregation: list[ReaggregationSignal],
        layering_scores: dict[str, float],
        placement_scores: dict[str, float],
    ) -> list[IntegrationAlert]:
        """
        Combine all 4 signal types into a unified integration score per address.
        More signals firing on the same address = exponentially higher score.
        Upstream layering/placement scores boost the final confidence.
        """
        # Collect all signals per address
        addr_signals: dict[str, dict[str, float]] = defaultdict(dict)
        addr_reasons: dict[str, list[str]] = defaultdict(list)
        addr_tx_hashes: dict[str, set[str]] = defaultdict(set)
        addr_first_seen: dict[str, float] = {}
        addr_last_seen: dict[str, float] = {}

        def _register(addr: str, signal_name: str, score: float, reason: str, tx_hashes: list[str],
                       first_ts: str | None, last_ts: str | None):
            addr_signals[addr][signal_name] = score
            addr_reasons[addr].append(reason)
            addr_tx_hashes[addr].update(h for h in tx_hashes if h)
            # Track timestamps
            from datetime import datetime
            for ts_str, is_first in [(first_ts, True), (last_ts, False)]:
                if not ts_str:
                    continue
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
                    if is_first:
                        addr_first_seen[addr] = min(addr_first_seen.get(addr, ts), ts)
                    else:
                        addr_last_seen[addr] = max(addr_last_seen.get(addr, ts), ts)
                except Exception:
                    pass

        for s in convergence:
            _register(
                s.convergence_address, "convergence", s.confidence_score,
                f"Fan-in convergence: {s.sender_count} senders → {s.total_value_eth:.4f} ETH received",
                s.supporting_tx_hashes, s.first_seen_at, s.last_seen_at,
            )

        for s in dormancy:
            for addr in s.addresses:
                _register(
                    addr, "dormancy", s.confidence_score,
                    f"Dormancy-to-activation: {s.dormancy_seconds / 86400:.1f} days silent, "
                    f"then {s.activation_value_eth:.4f} ETH sent",
                    s.supporting_tx_hashes, s.dormancy_start_at, s.activation_at,
                )

        for s in terminal:
            _register(
                s.terminal_address, "terminal_node", s.confidence_score,
                ("Known exchange exit point" if s.is_known_exchange else "Terminal node")
                + f": {s.total_received_eth:.4f} ETH received, never forwarded",
                s.supporting_tx_hashes, s.first_seen_at, s.last_seen_at,
            )

        for s in reaggregation:
            for addr in s.addresses:
                _register(
                    addr, "reaggregation", s.confidence_score,
                    f"Value reaggregation: {s.input_count} inputs → "
                    f"{s.output_value_eth:.4f} ETH output (ratio {s.reaggregation_ratio:.2f})",
                    s.supporting_tx_hashes, s.first_seen_at, s.last_seen_at,
                )

        alerts: list[IntegrationAlert] = []

        for addr, signal_scores in addr_signals.items():
            if not signal_scores:
                continue

            # Base integration score: weighted average of all fired signals
            # Multi-signal bonus: each additional signal adds 15% boost
            scores = list(signal_scores.values())
            base_score = statistics.fmean(scores)
            multi_signal_bonus = min(0.30, (len(scores) - 1) * 0.15)
            integration_score = clamp(base_score + multi_signal_bonus)

            # Upstream boost: if layering/placement also flagged this address
            upstream_boost = 0.0
            lay_score = layering_scores.get(addr, 0.0)
            plc_score = placement_scores.get(addr, 0.0)
            if lay_score > 0.5:
                upstream_boost += 0.10
            if plc_score > 0.5:
                upstream_boost += 0.05
            integration_score = clamp(integration_score + upstream_boost)

            # Confidence = highest individual signal score
            confidence = max(scores)

            # Only emit alerts above threshold
            if integration_score < 0.35:
                continue

            signals_fired = sorted(signal_scores.keys(), key=lambda k: signal_scores[k], reverse=True)

            alerts.append(IntegrationAlert(
                entity_id=addr,
                entity_type="address",
                addresses=[addr],
                integration_score=round(integration_score, 4),
                confidence_score=round(confidence, 4),
                signals_fired=signals_fired,
                signal_scores={k: round(v, 4) for k, v in signal_scores.items()},
                reasons=addr_reasons[addr],
                supporting_tx_hashes=sorted(addr_tx_hashes[addr])[:30],
                layering_score=round(lay_score, 4),
                placement_score=round(plc_score, 4),
                first_seen_at=iso_from_ts(addr_first_seen.get(addr)),
                last_seen_at=iso_from_ts(addr_last_seen.get(addr)),
                metrics={
                    "signal_count": len(scores),
                    "base_score": round(base_score, 4),
                    "multi_signal_bonus": round(multi_signal_bonus, 4),
                    "upstream_boost": round(upstream_boost, 4),
                    "layering_score": round(lay_score, 4),
                    "placement_score": round(plc_score, 4),
                },
            ))

        logger.info(
            "Integration confidence aggregation produced %d alerts (%d high-confidence)",
            len(alerts),
            sum(1 for a in alerts if a.integration_score >= 0.70),
        )
        return alerts

    # ── Persistence ───────────────────────────────────────────────────────────

    def _persist(self, result: IntegrationAnalysisResult) -> None:
        """Persist integration results to MySQL integration_* tables."""
        create_tables_if_not_exist(self.cfg)
        engine = get_maria_engine(self.cfg)
        completed_at = datetime.fromisoformat(
            result.generated_at.replace("Z", "+00:00")
        ).replace(tzinfo=None)

        try:
            with engine.begin() as conn:
                # Upsert run record
                conn.execute(
                    text("""
                        INSERT INTO integration_runs
                            (id, source, status, started_at, completed_at, summary_json)
                        VALUES
                            (:id, :source, 'completed', :started_at, :completed_at, :summary_json)
                        ON DUPLICATE KEY UPDATE
                            status = 'completed',
                            completed_at = :completed_at,
                            summary_json = :summary_json
                    """),
                    {
                        "id": result.run_id,
                        "source": result.summary.get("source", "auto"),
                        "started_at": completed_at,
                        "completed_at": completed_at,
                        "summary_json": json_dumps(result.summary),
                    },
                )

                # Persist alerts
                for chunk in chunked(result.alerts):
                    rows = [
                        {
                            "run_id": result.run_id,
                            "entity_id": a.entity_id,
                            "entity_type": a.entity_type,
                            "integration_score": a.integration_score,
                            "confidence_score": a.confidence_score,
                            "signals_fired_json": json_dumps(a.signals_fired),
                            "signal_scores_json": json_dumps(a.signal_scores),
                            "reasons_json": json_dumps(a.reasons),
                            "supporting_tx_hashes_json": json_dumps(a.supporting_tx_hashes),
                            "layering_score": a.layering_score,
                            "placement_score": a.placement_score,
                            "metrics_json": json_dumps(a.metrics),
                            "first_seen_at": dt_from_ts(
                                datetime.fromisoformat(a.first_seen_at.replace("Z", "+00:00")).timestamp()
                                if a.first_seen_at else None
                            ),
                            "last_seen_at": dt_from_ts(
                                datetime.fromisoformat(a.last_seen_at.replace("Z", "+00:00")).timestamp()
                                if a.last_seen_at else None
                            ),
                        }
                        for a in chunk
                    ]
                    if rows:
                        conn.execute(
                            text("""
                                INSERT INTO integration_alerts (
                                    run_id, entity_id, entity_type,
                                    integration_score, confidence_score,
                                    signals_fired_json, signal_scores_json,
                                    reasons_json, supporting_tx_hashes_json,
                                    layering_score, placement_score,
                                    metrics_json, first_seen_at, last_seen_at
                                ) VALUES (
                                    :run_id, :entity_id, :entity_type,
                                    :integration_score, :confidence_score,
                                    :signals_fired_json, :signal_scores_json,
                                    :reasons_json, :supporting_tx_hashes_json,
                                    :layering_score, :placement_score,
                                    :metrics_json, :first_seen_at, :last_seen_at
                                )
                                ON DUPLICATE KEY UPDATE
                                    integration_score = VALUES(integration_score),
                                    confidence_score = VALUES(confidence_score),
                                    signals_fired_json = VALUES(signals_fired_json),
                                    signal_scores_json = VALUES(signal_scores_json),
                                    reasons_json = VALUES(reasons_json),
                                    metrics_json = VALUES(metrics_json)
                            """),
                            rows,
                        )

            logger.info(
                "Integration results persisted: run=%s, alerts=%d",
                result.run_id, len(result.alerts),
            )
        except Exception as exc:
            logger.warning("Integration persist failed (non-fatal): %s", exc)
        finally:
            engine.dispose()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _empty_result(self, run_id: str, generated_at: str, source: str) -> IntegrationAnalysisResult:
        return IntegrationAnalysisResult(
            run_id=run_id,
            generated_at=generated_at,
            summary={
                "source": source,
                "transactions": 0,
                "convergence_signals": 0,
                "dormancy_signals": 0,
                "terminal_signals": 0,
                "reaggregation_signals": 0,
                "alerts": 0,
                "high_confidence_alerts": 0,
            },
            convergence_signals=[],
            dormancy_signals=[],
            terminal_signals=[],
            reaggregation_signals=[],
            alerts=[],
        )
