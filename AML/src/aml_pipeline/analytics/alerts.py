"""Alert generation rules and scoring."""

import logging
from datetime import datetime, timezone
from typing import List

import pandas as pd

from ..config import Config

logger = logging.getLogger(__name__)


def _score_row(row, cfg: Config) -> float:
    """Compute a risk score for a transaction row."""
    # Simple additive risk score; tune per your policy.
    score = 0.0
    if row["amount_usd"] >= cfg.usd_threshold:
        score += 40.0
    if row["btc_amount"] >= cfg.btc_threshold:
        score += 40.0
    if row["cluster_label"] == -1:
        score += 25.0
    if row["sender_tx_count_24h"] >= cfg.velocity_24h_threshold:
        score += 15.0
    if row["is_new_counterparty"] == 1 and row["amount_usd"] >= cfg.usd_threshold * 0.5:
        score += 10.0
    return min(score, 100.0)


def _build_reasons(row, cfg: Config) -> List[str]:
    """Generate human-readable reasons for alerting."""
    reasons = []
    if row["amount_usd"] >= cfg.usd_threshold:
        reasons.append("amount_usd_threshold")
    if row["btc_amount"] >= cfg.btc_threshold:
        reasons.append("btc_threshold")
    if row["cluster_label"] == -1:
        reasons.append("cluster_outlier")
    if row["sender_tx_count_24h"] >= cfg.velocity_24h_threshold:
        reasons.append("velocity_24h")
    if row["is_new_counterparty"] == 1 and row["amount_usd"] >= cfg.usd_threshold * 0.5:
        reasons.append("new_counterparty_high_value")
    return reasons


def build_alerts(
    df_clean: pd.DataFrame,
    features: pd.DataFrame,
    labels: pd.Series,
    cfg: Config,
) -> pd.DataFrame:
    """Return alert rows for transactions that meet any rule."""
    if df_clean.empty or features.empty:
        return pd.DataFrame()

    df = df_clean.merge(features, on="tx_id", how="left")
    df["cluster_label"] = df["tx_id"].map(labels).fillna(0).astype(int)

    reasons_list = df.apply(lambda row: _build_reasons(row, cfg), axis=1)
    df["reasons"] = reasons_list.apply(lambda items: ",".join(items))
    df["flagged"] = reasons_list.apply(lambda items: len(items) > 0)

    df["risk_score"] = df.apply(lambda row: _score_row(row, cfg), axis=1)
    df["alert_time"] = datetime.now(timezone.utc)

    alerts = df[df["flagged"]].copy()
    logger.info("Generated %s alerts", len(alerts))

    return alerts[
        [
            "tx_id",
            "alert_time",
            "risk_score",
            "reasons",
            "cluster_label",
            "amount_usd",
            "btc_amount",
        ]
    ]
