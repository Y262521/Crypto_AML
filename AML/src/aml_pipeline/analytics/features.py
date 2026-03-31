"""Feature engineering for transaction analytics."""

import logging
from collections import deque

import pandas as pd

logger = logging.getLogger(__name__)


def _compute_velocity_24h(df: pd.DataFrame) -> pd.Series:
    """Compute rolling 24h transaction counts per sender."""
    df_sorted = df.sort_values("event_time").copy()
    df_sorted = df_sorted.set_index("event_time")
    counts = (
        df_sorted.groupby("sender_id")["tx_id"]
        .rolling("24H")
        .count()
        .reset_index(level=0, drop=True)
    )
    df_sorted["sender_tx_count_24h"] = counts
    df_sorted = df_sorted.reset_index()
    return df_sorted.set_index("tx_id")["sender_tx_count_24h"].reindex(df["tx_id"]).fillna(0)


def _compute_unique_counterparties_7d(df: pd.DataFrame) -> pd.Series:
    """Compute unique counterparties per sender in a 7-day window."""
    results = pd.Series(index=df.index, dtype="int")
    for sender_id, group in df.groupby("sender_id"):
        group_sorted = group.sort_values("event_time")
        # Sliding 7-day window per sender to count unique counterparties.
        window = deque()
        counts = {}
        for idx, row in group_sorted.iterrows():
            cutoff = row["event_time"] - pd.Timedelta(days=7)
            while window and window[0][0] < cutoff:
                _, old_receiver = window.popleft()
                counts[old_receiver] -= 1
                if counts[old_receiver] <= 0:
                    del counts[old_receiver]
            receiver_id = row["receiver_id"]
            window.append((row["event_time"], receiver_id))
            counts[receiver_id] = counts.get(receiver_id, 0) + 1
            results.loc[idx] = len(counts)
    return results.fillna(0).astype(int)


def _compute_is_new_counterparty(df: pd.DataFrame) -> pd.Series:
    """Flag whether a counterparty is new for a given sender."""
    results = pd.Series(index=df.index, dtype="int")
    for sender_id, group in df.groupby("sender_id"):
        group_sorted = group.sort_values("event_time")
        # Track first-time counterparties per sender.
        seen = set()
        for idx, receiver_id in zip(group_sorted.index, group_sorted["receiver_id"]):
            results.loc[idx] = 0 if receiver_id in seen else 1
            seen.add(receiver_id)
    return results.fillna(0).astype(int)


def build_features(df_clean: pd.DataFrame) -> pd.DataFrame:
    """Build model-ready features from clean transaction data."""
    if df_clean.empty:
        return pd.DataFrame()

    df = df_clean.copy().reset_index(drop=True)

    df["hour_of_day"] = df["event_time"].dt.hour
    df["sender_tx_count_24h"] = _compute_velocity_24h(df)
    df["sender_unique_counterparties_7d"] = _compute_unique_counterparties_7d(df)
    df["is_new_counterparty"] = _compute_is_new_counterparty(df)

    features = df[
        [
            "tx_id",
            "amount_usd",
            "btc_amount",
            "hour_of_day",
            "sender_tx_count_24h",
            "sender_unique_counterparties_7d",
            "is_new_counterparty",
        ]
    ].copy()

    return features
