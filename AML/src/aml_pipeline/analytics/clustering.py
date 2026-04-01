"""Unsupervised clustering for anomaly signals."""

import logging
from typing import List

import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler

from ..config import Config

logger = logging.getLogger(__name__)

FEATURE_COLUMNS: List[str] = [
    "amount_usd",
    "btc_amount",
    "hour_of_day",
    "sender_tx_count_24h",
    "sender_unique_counterparties_7d",
    "is_new_counterparty",
]


def cluster_transactions(features: pd.DataFrame, cfg: Config) -> pd.Series:
    """Assign DBSCAN cluster labels to transactions based on features."""
    if features.empty:
        return pd.Series(dtype="int")

    data = features[FEATURE_COLUMNS].fillna(0.0)
    if len(data) < cfg.dbscan_min_samples:
        labels = [0] * len(data)
        logger.info("Not enough data for DBSCAN, skipping clustering")
        return pd.Series(labels, index=features["tx_id"], dtype="int")

    scaler = StandardScaler()
    data_scaled = scaler.fit_transform(data)

    model = DBSCAN(eps=cfg.dbscan_eps, min_samples=cfg.dbscan_min_samples)
    labels = model.fit_predict(data_scaled)
    logger.info("DBSCAN produced %s clusters (including noise)", len(set(labels)))
    return pd.Series(labels, index=features["tx_id"], dtype="int")
