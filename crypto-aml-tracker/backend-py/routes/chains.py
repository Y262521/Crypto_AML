"""
Chains API routes.

Exposes the list of supported blockchains and per-chain statistics
to the frontend. The frontend uses this to populate chain filter dropdowns.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from db.mysql import fetch_all, get_pool

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Chain metadata (mirrors chains/registry.py) ───────────────────────────────
# Kept here as a flat dict so the backend doesn't need to import the AML package
# at every request. Synced manually with the registry.

_CHAIN_METADATA: dict[str, dict[str, Any]] = {
    "ethereum": {
        "chain_name": "ethereum",
        "chain_id": 1,
        "display_name": "Ethereum",
        "native_asset": "ETH",
        "blockchain_type": "EVM",
        "color": "#627EEA",
        "icon": "ETH",
    },
    "bnb": {
        "chain_name": "bnb",
        "chain_id": 56,
        "display_name": "BNB Chain",
        "native_asset": "BNB",
        "blockchain_type": "EVM",
        "color": "#F3BA2F",
        "icon": "BNB",
    },
    "polygon": {
        "chain_name": "polygon",
        "chain_id": 137,
        "display_name": "Polygon",
        "native_asset": "POL",
        "blockchain_type": "EVM",
        "color": "#8247E5",
        "icon": "POL",
    },
    "arbitrum": {
        "chain_name": "arbitrum",
        "chain_id": 42161,
        "display_name": "Arbitrum",
        "native_asset": "ETH",
        "blockchain_type": "EVM",
        "color": "#2D374B",
        "icon": "ARB",
    },
    "base": {
        "chain_name": "base",
        "chain_id": 8453,
        "display_name": "Base",
        "native_asset": "ETH",
        "blockchain_type": "EVM",
        "color": "#0052FF",
        "icon": "BASE",
    },
    "bitcoin": {
        "chain_name": "bitcoin",
        "chain_id": 0,
        "display_name": "Bitcoin",
        "native_asset": "BTC",
        "blockchain_type": "UTXO",
        "color": "#F7931A",
        "icon": "BTC",
    },
    "litecoin": {
        "chain_name": "litecoin",
        "chain_id": 2,
        "display_name": "Litecoin",
        "native_asset": "LTC",
        "blockchain_type": "UTXO",
        "color": "#A6A9AA",
        "icon": "LTC",
    },
    "dogecoin": {
        "chain_name": "dogecoin",
        "chain_id": 3,
        "display_name": "Dogecoin",
        "native_asset": "DOGE",
        "blockchain_type": "UTXO",
        "color": "#C2A633",
        "icon": "DOGE",
    },
    "bitcoin_cash": {
        "chain_name": "bitcoin_cash",
        "chain_id": 145,
        "display_name": "Bitcoin Cash",
        "native_asset": "BCH",
        "blockchain_type": "UTXO",
        "color": "#8DC351",
        "icon": "BCH",
    },
    "solana": {
        "chain_name": "solana",
        "chain_id": 900,
        "display_name": "Solana",
        "native_asset": "SOL",
        "blockchain_type": "ACCOUNT_BASED",
        "color": "#9945FF",
        "icon": "SOL",
    },
}


def _require_mysql() -> None:
    if get_pool() is None:
        raise HTTPException(
            status_code=503,
            detail="MySQL is not connected.",
        )


@router.get("/")
async def get_supported_chains():
    """
    Return all supported chains with metadata.
    Used by the frontend to build chain filter dropdowns.
    """
    return {
        "chains": list(_CHAIN_METADATA.values()),
        "total": len(_CHAIN_METADATA),
    }


@router.get("/active")
async def get_active_chains():
    """
    Return chains that have actual data in the database.
    Uses the chain_name column on the transactions table.
    """
    _require_mysql()
    try:
        rows = await fetch_all(
            """
            SELECT
                COALESCE(chain_name, 'ethereum') AS chain_name,
                COUNT(*) AS tx_count,
                MIN(block_number) AS min_block,
                MAX(block_number) AS max_block
            FROM transactions
            GROUP BY COALESCE(chain_name, 'ethereum')
            ORDER BY tx_count DESC
            """
        )
    except Exception as exc:
        logger.warning("Could not query active chains: %s", exc)
        rows = []

    active = []
    for row in rows:
        chain_name = row.get("chain_name", "ethereum")
        meta = _CHAIN_METADATA.get(chain_name, {
            "chain_name": chain_name,
            "chain_id": 0,
            "display_name": chain_name.title(),
            "native_asset": "???",
            "blockchain_type": "EVM",
            "color": "#888888",
            "icon": "?",
        })
        active.append({
            **meta,
            "tx_count": int(row.get("tx_count") or 0),
            "min_block": int(row.get("min_block") or 0),
            "max_block": int(row.get("max_block") or 0),
        })

    return {
        "chains": active,
        "total": len(active),
    }


@router.get("/stats")
async def get_chain_stats():
    """
    Return per-chain transaction and address counts.
    Used for the multi-chain dashboard overview.
    """
    _require_mysql()
    try:
        tx_rows = await fetch_all(
            """
            SELECT
                COALESCE(chain_name, 'ethereum') AS chain_name,
                COUNT(*) AS tx_count,
                COALESCE(SUM(value_eth), 0) AS total_value,
                COALESCE(SUM(CASE WHEN value_eth >= 10 THEN 1 ELSE 0 END), 0) AS high_value_count
            FROM transactions
            GROUP BY COALESCE(chain_name, 'ethereum')
            """
        )
    except Exception as exc:
        logger.warning("Could not query chain stats: %s", exc)
        tx_rows = []

    try:
        addr_rows = await fetch_all(
            """
            SELECT
                COALESCE(chain_name, 'ethereum') AS chain_name,
                COUNT(*) AS address_count
            FROM addresses
            GROUP BY COALESCE(chain_name, 'ethereum')
            """
        )
    except Exception as exc:
        logger.warning("Could not query address chain stats: %s", exc)
        addr_rows = []

    try:
        cluster_rows = await fetch_all(
            """
            SELECT
                COALESCE(chain_name, 'ethereum') AS chain_name,
                COUNT(*) AS cluster_count
            FROM wallet_clusters
            GROUP BY COALESCE(chain_name, 'ethereum')
            """
        )
    except Exception as exc:
        logger.warning("Could not query cluster chain stats: %s", exc)
        cluster_rows = []

    # Merge into per-chain stats
    stats: dict[str, dict] = {}

    for row in tx_rows:
        cn = row.get("chain_name", "ethereum")
        meta = _CHAIN_METADATA.get(cn, {})
        stats[cn] = {
            "chain_name": cn,
            "display_name": meta.get("display_name", cn.title()),
            "native_asset": meta.get("native_asset", "???"),
            "blockchain_type": meta.get("blockchain_type", "EVM"),
            "color": meta.get("color", "#888888"),
            "tx_count": int(row.get("tx_count") or 0),
            "total_value_native": float(row.get("total_value") or 0.0),
            "high_value_tx_count": int(row.get("high_value_count") or 0),
            "address_count": 0,
            "cluster_count": 0,
        }

    for row in addr_rows:
        cn = row.get("chain_name", "ethereum")
        if cn not in stats:
            meta = _CHAIN_METADATA.get(cn, {})
            stats[cn] = {
                "chain_name": cn,
                "display_name": meta.get("display_name", cn.title()),
                "native_asset": meta.get("native_asset", "???"),
                "blockchain_type": meta.get("blockchain_type", "EVM"),
                "color": meta.get("color", "#888888"),
                "tx_count": 0,
                "total_value_native": 0.0,
                "high_value_tx_count": 0,
                "address_count": 0,
                "cluster_count": 0,
            }
        stats[cn]["address_count"] = int(row.get("address_count") or 0)

    for row in cluster_rows:
        cn = row.get("chain_name", "ethereum")
        if cn in stats:
            stats[cn]["cluster_count"] = int(row.get("cluster_count") or 0)

    return {
        "chains": sorted(stats.values(), key=lambda x: x["tx_count"], reverse=True),
        "total_chains": len(stats),
    }
