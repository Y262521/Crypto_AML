"""
Redis Watchlist
===============
Maintains a real-time set of high-risk addresses for transaction screening.
Falls back gracefully if Redis is not available.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_redis_client = None
_WATCHLIST_TTL = 86400 * 7  # 7 days


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis
        _redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
        _redis_client.ping()
        logger.info("Redis watchlist connected.")
    except Exception as e:
        logger.warning("Redis not available — watchlist disabled: %s", e)
        _redis_client = None
    return _redis_client


def add_to_watchlist(entity_id: str, addresses: list, risk_score: float) -> int:
    """Add all addresses of a POI entity to the Redis watchlist."""
    r = _get_redis()
    if not r:
        return 0
    added = 0
    payload = json.dumps({"entity_id": entity_id, "risk_score": round(risk_score, 4)})
    for addr in addresses:
        try:
            r.setex(f"watchlist:{addr.lower()}", _WATCHLIST_TTL, payload)
            added += 1
        except Exception as e:
            logger.warning("Failed to add %s to watchlist: %s", addr, e)
    return added


def remove_from_watchlist(addresses: list) -> int:
    """Remove addresses from the Redis watchlist when entity is downgraded."""
    r = _get_redis()
    if not r:
        return 0
    removed = 0
    for addr in addresses:
        try:
            r.delete(f"watchlist:{addr.lower()}")
            removed += 1
        except Exception as e:
            logger.warning("Failed to remove %s from watchlist: %s", addr, e)
    return removed


def check_watchlist(address: str) -> Optional[dict]:
    """Check if an address is on the watchlist. Returns entity info or None."""
    r = _get_redis()
    if not r:
        return None
    try:
        val = r.get(f"watchlist:{address.lower()}")
        return json.loads(val) if val else None
    except Exception:
        return None


def screen_transaction(tx: dict) -> Optional[dict]:
    """
    Screen a transaction against the watchlist.
    Returns alert dict if either address is flagged, else None.
    """
    from_hit = check_watchlist(tx.get("from_address", ""))
    to_hit   = check_watchlist(tx.get("to_address", ""))

    if from_hit or to_hit:
        return {
            "tx_hash":    tx.get("tx_hash"),
            "from_address": tx.get("from_address"),
            "to_address":   tx.get("to_address"),
            "value_eth":    tx.get("value_eth"),
            "from_hit":     from_hit,
            "to_hit":       to_hit,
            "alert_type":   "watchlist_match",
        }
    return None


def sync_watchlist(conn) -> dict:
    """
    Sync Redis watchlist from MySQL — add all current POI addresses,
    remove addresses of downgraded entities.
    """
    r = _get_redis()
    if not r:
        return {"status": "skipped", "reason": "Redis not available"}

    added = removed = 0
    with conn.cursor() as cur:
        # Add POI addresses
        cur.execute("""
            SELECT wc.id AS entity_id, wc.risk_score, a.address
            FROM wallet_clusters wc
            JOIN addresses a ON a.cluster_id = wc.id
            WHERE wc.is_poi = 1
        """)
        poi_rows = cur.fetchall()
        for r_row in poi_rows:
            payload = json.dumps({
                "entity_id":  r_row["entity_id"],
                "risk_score": float(r_row["risk_score"] or 0),
            })
            try:
                r.setex(f"watchlist:{r_row['address'].lower()}", _WATCHLIST_TTL, payload)
                added += 1
            except Exception:
                pass

        # Remove non-POI addresses
        cur.execute("""
            SELECT a.address
            FROM wallet_clusters wc
            JOIN addresses a ON a.cluster_id = wc.id
            WHERE wc.is_poi = 0
        """)
        for r_row in cur.fetchall():
            try:
                r.delete(f"watchlist:{r_row['address'].lower()}")
                removed += 1
            except Exception:
                pass

    return {"status": "success", "added": added, "removed": removed}
