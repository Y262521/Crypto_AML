"""
Real-Time Transaction Screener
================================
Screens transactions against the Redis watchlist.
Called from the MariaDB loader after each transaction batch is written.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)


def screen_and_alert(transactions: List[dict], conn) -> int:
    """
    Screen a batch of transactions against the Redis watchlist.
    Saves alerts to poi_alerts table.
    Returns number of alerts generated.
    """
    try:
        from .watchlist import check_watchlist
    except Exception:
        return 0

    alerts = []
    for tx in transactions:
        from_addr = (tx.get("from_address") or "").lower()
        to_addr   = (tx.get("to_address")   or "").lower()

        from_hit = check_watchlist(from_addr) if from_addr else None
        to_hit   = check_watchlist(to_addr)   if to_addr   else None

        if from_hit:
            alerts.append({
                "tx_hash":         tx.get("tx_hash"),
                "entity_id":       from_hit.get("entity_id"),
                "matched_address": from_addr,
                "risk_score":      from_hit.get("risk_score", 0),
                "alert_type":      "watchlist_sender",
            })
        if to_hit:
            alerts.append({
                "tx_hash":         tx.get("tx_hash"),
                "entity_id":       to_hit.get("entity_id"),
                "matched_address": to_addr,
                "risk_score":      to_hit.get("risk_score", 0),
                "alert_type":      "watchlist_receiver",
            })

    if not alerts:
        return 0

    try:
        with conn.cursor() as cur:
            # Ensure table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS poi_alerts (
                    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
                    tx_hash         VARCHAR(66)  NULL,
                    entity_id       VARCHAR(64)  NULL,
                    matched_address VARCHAR(64)  NULL,
                    risk_score      DECIMAL(6,4) NOT NULL DEFAULT 0,
                    alert_type      VARCHAR(50)  NOT NULL DEFAULT 'watchlist_match',
                    created_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_pa_entity  (entity_id),
                    INDEX idx_pa_address (matched_address)
                )
            """)
            for alert in alerts:
                cur.execute("""
                    INSERT INTO poi_alerts (tx_hash, entity_id, matched_address, risk_score, alert_type)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    alert["tx_hash"], alert["entity_id"],
                    alert["matched_address"], alert["risk_score"], alert["alert_type"],
                ))
        conn.commit()
        logger.warning("POI ALERT: %d transactions matched watchlist", len(alerts))
    except Exception as e:
        logger.error("Failed to save POI alerts: %s", e)

    return len(alerts)
