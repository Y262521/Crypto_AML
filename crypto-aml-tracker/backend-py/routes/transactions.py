"""
Transaction API routes.

Serves processed transactions from MySQL and graph edges from Neo4j.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Literal
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from db.mysql import fetch_all, fetch_one, get_pool
from db.neo4j import get_driver
from settings import get_env

router = APIRouter()
NEO4J_DATABASE = get_env("NEO4J_DATABASE", default="neo4j")
MIN_CLUSTER_SIZE = int(get_env("CLUSTER_MIN_CLUSTER_SIZE", default="2") or "2")


def _threshold_eth() -> float:
    raw = get_env("HIGH_VALUE_THRESHOLD_ETH", "AML_HIGH_VALUE_THRESHOLD", default="10")
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 10.0


def _risk_score(value_eth: float, threshold: float) -> float:
    if threshold <= 0 or value_eth <= 0:
        return 0.0

    ratio = value_eth / threshold
    if ratio >= 2.0:
        return 100.0
    if ratio >= 1.0:
        return round(75.0 + 25.0 * (ratio - 1.0), 1)
    return round(max(0.0, min(75.0, 75.0 * ratio)), 1)


def _risk_label(value_eth: float, threshold: float) -> str:
    score = _risk_score(value_eth, threshold)
    if score > 75:
        return "High"
    if score > 40:
        return "Medium"
    return "Low"


def _format_ts(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def _require_mysql():
    if get_pool() is None:
        raise HTTPException(
            status_code=503,
            detail="MySQL is not connected. Transactions are unavailable.",
        )


def _latest_transactions_sql(sort_by: str = "value_usd_desc", chain: str | None = None) -> tuple[str, list]:
    # Sorting options:
    #   value_usd_desc  — sort by USD value (cross-chain comparable)
    #   amount_desc     — sort by native asset amount (legacy, chain-specific)
    #   latest          — sort by most recent block
    order_clause = {
        "value_usd_desc":  "ORDER BY COALESCE(usd_at_execution, 0) DESC, value_eth DESC, block_number DESC, tx_hash DESC",
        "amount_desc":     "ORDER BY value_eth DESC, block_number DESC, tx_hash DESC",
        "latest":          "ORDER BY block_number DESC, tx_hash DESC",
    }.get(sort_by, "ORDER BY COALESCE(usd_at_execution, 0) DESC, value_eth DESC, block_number DESC, tx_hash DESC")

    where_clauses = []
    params: list = []

    if chain and chain != "all":
        where_clauses.append("(chain_name = %s OR (chain_name IS NULL AND %s = 'ethereum'))")
        params.extend([chain, chain])

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    sql = f"""
        SELECT tx_hash, from_address, to_address, value_eth, timestamp, block_number,
               is_contract_call, gas_used, status,
               usd_at_execution,
               COALESCE(chain_name, 'ethereum') AS chain_name,
               COALESCE(chain_id, 1) AS chain_id,
               COALESCE(blockchain_type, 'EVM') AS blockchain_type,
               COALESCE(native_asset, 'ETH') AS native_asset
        FROM transactions
        {where_sql}
        {order_clause}
        LIMIT %s OFFSET %s
        """
    params.extend(["__limit__", "__offset__"])
    return sql, params

@router.get("/")
async def get_latest_transactions(
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sort_by: Literal["value_usd_desc", "amount_desc", "latest"] = Query("value_usd_desc"),
    chain: str | None = Query(default=None, description="Filter by chain name (e.g. ethereum, bnb, polygon)"),
):
    _require_mysql()
    threshold = _threshold_eth()

    # Build count query with optional chain filter
    if chain and chain != "all":
        total_row = await fetch_one(
            "SELECT COUNT(*) AS total FROM transactions "
            "WHERE chain_name = %s OR (chain_name IS NULL AND %s = 'ethereum')",
            (chain, chain),
        ) or {}
    else:
        total_row = await fetch_one("SELECT COUNT(*) AS total FROM transactions") or {}

    sql, base_params = _latest_transactions_sql(sort_by, chain)
    # Replace placeholder params with actual limit/offset
    sql = sql.replace("'__limit__'", "%s").replace("'__offset__'", "%s")
    # Fix: base_params ends with ["__limit__", "__offset__"], replace them
    actual_params = [p for p in base_params if p not in ("__limit__", "__offset__")]
    actual_params.extend([limit, offset])

    rows = await fetch_all(sql, actual_params)

    # Native-asset to USD rates — loaded from MVA price cache (Chainlink oracle)
    # Current market rates — live prices from Binance public API (no auth needed)
    def _get_current_rates() -> dict:
        try:
            from services.live_prices import get_live_prices
            return get_live_prices()
        except Exception:
            return {}

    # Current market rates (cached 5 min, from Binance)
    _CURRENT_RATES = _get_current_rates()
    _FALLBACK_RATES: dict = {}  # empty — show "—" if fetch failed

    results = []
    for row in rows:
        value_eth = float(row.get("value_eth") or 0.0)
        score = _risk_score(value_eth, threshold)
        native_asset = row.get("native_asset") or "ETH"
        chain_name   = row.get("chain_name") or "ethereum"

        # Historical USD value — what actually moved at execution time (AML relevant)
        usd_stored = row.get("usd_at_execution")
        if usd_stored is not None and float(usd_stored) > 0:
            usd_at_execution = float(usd_stored)
            usd_source = "chainlink_oracle"
        else:
            usd_at_execution = 0.0
            usd_source = "unavailable"

        # Current market USD value — what it's worth TODAY
        current_rate = _CURRENT_RATES.get(native_asset) or _FALLBACK_RATES.get(native_asset, 0.0)
        current_usd_value = value_eth * current_rate

        # The displayed USD value depends on which sort mode is active:
        # value_usd_desc  → use usd_at_execution (historical, oracle-sourced)
        # For display in table always show current market value alongside historical
        display_usd = usd_at_execution if usd_at_execution > 0 else current_usd_value

        results.append({
            "hash": row.get("tx_hash"),
            "sender": row.get("from_address"),
            "receiver": row.get("to_address"),
            "amount": f"{value_eth:.6f}",
            "timestamp": _format_ts(row.get("timestamp")),
            "blockNumber": int(row.get("block_number") or 0),
            "isContractCall": bool(row.get("is_contract_call")),
            "gasUsed": row.get("gas_used"),
            "status": row.get("status"),
            "riskScore": round(score, 1),
            "riskLabel": _risk_label(value_eth, threshold),
            # Chain identity
            "chain": chain_name,
            "chainId": int(row.get("chain_id") or 1),
            "blockchainType": row.get("blockchain_type") or "EVM",
            "nativeAsset": native_asset,
            # USD values — both historical and current
            "usdValue": round(display_usd, 2),          # shown in table
            "usdAtExecution": round(usd_at_execution, 2),  # at time of tx
            "currentUsdValue": round(current_usd_value, 2),  # today's price
            "usdSource": usd_source,
        })

    total = int(total_row.get("total") or 0)
    return {
        "items": results,
        "total": total,
        "limit": limit,
        "offset": offset,
        "sortBy": sort_by,
        "chain": chain or "all",
        "hasMore": offset + len(results) < total,
    }


@router.get("/analytics")
async def get_analytics():
    _require_mysql()
    threshold = _threshold_eth()

    totals = await fetch_one(
        "SELECT COUNT(*) AS total, COALESCE(SUM(value_eth), 0) AS total_eth FROM transactions"
    ) or {}
    total_tx = int(totals.get("total") or 0)
    total_eth = float(totals.get("total_eth") or 0.0)

    high_value = await fetch_one(
        "SELECT COUNT(*) AS high_value FROM transactions WHERE value_eth >= %s",
        (threshold,),
    ) or {}
    high_value_tx = int(high_value.get("high_value") or 0)

    buckets = await fetch_one(
        """
        SELECT
            SUM(CASE WHEN value_eth < 0.1 THEN 1 ELSE 0 END) AS b1,
            SUM(CASE WHEN value_eth >= 0.1 AND value_eth < 1 THEN 1 ELSE 0 END) AS b2,
            SUM(CASE WHEN value_eth >= 1 AND value_eth < 10 THEN 1 ELSE 0 END) AS b3,
            SUM(CASE WHEN value_eth >= 10 AND value_eth < 50 THEN 1 ELSE 0 END) AS b4,
            SUM(CASE WHEN value_eth >= 50 THEN 1 ELSE 0 END) AS b5
        FROM transactions
        """
    ) or {}

    top_clusters_balance = await fetch_all(
        """
        SELECT c.id, COUNT(a.address) AS cluster_size, c.total_balance
        FROM wallet_clusters c
        JOIN addresses a ON a.cluster_id = c.id
        GROUP BY c.id, c.total_balance
        HAVING COUNT(a.address) >= %s
        ORDER BY c.total_balance DESC, COUNT(a.address) DESC
        LIMIT 5
        """,
        (MIN_CLUSTER_SIZE,),
    )
    top_clusters_size = await fetch_all(
        """
        SELECT c.id, COUNT(a.address) AS cluster_size, c.total_balance
        FROM wallet_clusters c
        JOIN addresses a ON a.cluster_id = c.id
        GROUP BY c.id, c.total_balance
        HAVING COUNT(a.address) >= %s
        ORDER BY COUNT(a.address) DESC, c.total_balance DESC
        LIMIT 5
        """,
        (MIN_CLUSTER_SIZE,),
    )

    return {
        "totalTransactions": total_tx,
        "totalEth": round(total_eth, 6),
        "highValueTransactions": high_value_tx,
        "amountBuckets": [
            {"range": "0-0.1", "count": int(buckets.get("b1") or 0)},
            {"range": "0.1-1", "count": int(buckets.get("b2") or 0)},
            {"range": "1-10", "count": int(buckets.get("b3") or 0)},
            {"range": "10-50", "count": int(buckets.get("b4") or 0)},
            {"range": "50+", "count": int(buckets.get("b5") or 0)},
        ],
        "topClustersByBalance": [
            {
                "cluster_id": row.get("id"),
                "cluster_size": int(row.get("cluster_size") or 0),
                "total_balance": float(row.get("total_balance") or 0.0),
            }
            for row in top_clusters_balance
        ],
        "topClustersBySize": [
            {
                "cluster_id": row.get("id"),
                "cluster_size": int(row.get("cluster_size") or 0),
                "total_balance": float(row.get("total_balance") or 0.0),
            }
            for row in top_clusters_size
        ],
    }


@router.get("/chains")
async def get_transaction_chains():
    _require_mysql()
    eth_network = get_env("ETH_NETWORK", default="ethereum")
    try:
        rows = await fetch_all(
            """
            SELECT
                COALESCE(chain_name, %s) AS chain_name,
                COALESCE(blockchain_type, 'EVM') AS blockchain_type,
                COUNT(*) AS transaction_count,
                COALESCE(SUM(value_eth), 0) AS total_eth
            FROM transactions
            GROUP BY COALESCE(chain_name, %s), COALESCE(blockchain_type, 'EVM')
            ORDER BY transaction_count DESC
            """,
            (eth_network, eth_network),
        )
    except Exception:
        totals = await fetch_one(
            "SELECT COUNT(*) AS total, COALESCE(SUM(value_eth), 0) AS total_eth FROM transactions"
        ) or {}
        return {
            "chains": [
                {
                    "chainName": eth_network,
                    "blockchainType": "EVM",
                    "transactionCount": int(totals.get("total") or 0),
                    "totalEth": float(totals.get("total_eth") or 0.0),
                }
            ],
            "totalChains": 1,
            "note": "Chain metadata is not available from the current transactions schema.",
        }

    return {
        "chains": [
            {
                "chainName": row.get("chain_name") or eth_network,
                "blockchainType": row.get("blockchain_type") or "EVM",
                "transactionCount": int(row.get("transaction_count") or 0),
                "totalEth": float(row.get("total_eth") or 0.0),
            }
            for row in rows
        ],
        "totalChains": len(rows),
    }


def _require_neo4j():
    driver = get_driver()
    if not driver:
        raise HTTPException(
            status_code=503,
            detail="Neo4j is not connected. Graph exploration is unavailable.",
        )
    return driver


@router.get("/graph")
async def get_graph_data(
    search: str | None = None,
    center: str | None = None,
    hops: int = Query(2, ge=1, le=4),
    max_edges: int = Query(300, ge=50, le=3000),
    min_value: float = Query(0, ge=0),
):
    driver = _require_neo4j()

    if center:
        hops = max(1, min(int(hops), 4))
        query = f"""
        MATCH p = (a:Address {{address: $center}})-[:TRANSFER*1..{hops}]-(b:Address)
        UNWIND relationships(p) AS r
        WITH DISTINCT r
        WHERE r.value_eth >= $min_value
        RETURN startNode(r).address AS from_address,
               endNode(r).address AS to_address,
               r.value_eth AS value_eth,
               r.block_number AS block_number,
               r.tx_hash AS tx_hash
        LIMIT $max_edges
        """
        params = {"center": center.lower(), "min_value": min_value, "max_edges": max_edges}
    elif search:
        query = """
        MATCH (a:Address)
        WHERE toLower(a.address) CONTAINS toLower($search)
        WITH a LIMIT 5
        MATCH p = (a)-[:TRANSFER*1..2]-(b:Address)
        UNWIND relationships(p) AS r
        WITH DISTINCT r
        WHERE r.value_eth >= $min_value
        RETURN startNode(r).address AS from_address,
               endNode(r).address AS to_address,
               r.value_eth AS value_eth,
               r.block_number AS block_number,
               r.tx_hash AS tx_hash
        LIMIT $max_edges
        """
        params = {"search": search, "min_value": min_value, "max_edges": max_edges}
    else:
        query = """
        MATCH (a:Address)-[r:TRANSFER]->(b:Address)
        WHERE r.value_eth >= $min_value
        RETURN a.address AS from_address,
               b.address AS to_address,
               r.value_eth AS value_eth,
               r.block_number AS block_number,
               r.tx_hash AS tx_hash
        ORDER BY r.block_number DESC
        LIMIT $max_edges
        """
        params = {"min_value": min_value, "max_edges": max_edges}

    try:
        async with driver.session(database=NEO4J_DATABASE) as session:
            result = await session.run(query, params)
            rows = [record.data() async for record in result]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Neo4j graph query failed: {exc}") from exc

    return [
        {
            "sender": row.get("from_address"),
            "receiver": row.get("to_address"),
            "amount": float(row.get("value_eth") or 0.0),
            "blockNumber": int(row.get("block_number") or 0),
            "txHash": row.get("tx_hash"),
        }
        for row in rows
    ]


@router.post("/refresh")
async def refresh_pipeline():
    """Optional manual refresh: run ETL plus analytics once."""
    try:
        import sys
        from pathlib import Path
        from dotenv import load_dotenv

        aml_root = Path(__file__).resolve().parents[3] / "AML"
        aml_src = str(aml_root / "src")
        if aml_src not in sys.path:
            sys.path.insert(0, aml_src)
        load_dotenv(aml_root / ".env")

        from aml_pipeline.config import load_config
        from aml_pipeline.pipelines.daily_pipeline import run_daily_pipeline

        cfg = load_config()
        summary = await asyncio.to_thread(
            run_daily_pipeline,
            cfg=cfg,
            run_clustering=True,
            skip_mongo_backup=True,
        )
        return {"status": "ok", "summary": summary}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline refresh failed: {exc}") from exc
