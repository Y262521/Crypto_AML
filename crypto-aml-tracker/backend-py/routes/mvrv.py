"""
MVRV Routes
===========
Market Value to Realized Value analytics — address and cluster level.

GET  /api/mvrv/address/{address}        full MVRV breakdown
GET  /api/mvrv/cluster/{cluster_id}     aggregated cluster MVRV
GET  /api/mvrv/history/{entity_id}      historical snapshots
GET  /api/mvrv/directory                ranked index (all known addresses)
POST /api/mvrv/refresh/{address}        force-refresh + recompute

NOTE: All schema DDL runs once at startup (main.py lifespan).
      No DDL is executed per-request.
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Query

from db.mysql import fetch_all, fetch_one, get_pool
from services.balance_aggregator import get_aggregator, STABLECOINS
from services.mvrv_calculator import (
    compute_mvrv_for_address,
    compute_mvrv_for_cluster,
    generate_mvrv_flags,
    get_mvrv_history,
    save_mvrv_snapshot,
)

router = APIRouter()

_directory_count_cache = {
    'updated_at': None,
    'count': 0,
}
_DIRECTORY_COUNT_TTL = 60

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_ts(value) -> Optional[str]:
    if not value:
        return None
    if isinstance(value, str):
        return value
    dt = value
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat()


def _stale(updated_at, seconds: int = 3600) -> bool:
    if not updated_at:
        return True
    u = updated_at
    if isinstance(u, str):
        try:
            u = datetime.fromisoformat(u.replace("Z", "+00:00"))
        except ValueError:
            return True
    if getattr(u, "tzinfo", None) is None:
        u = u.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - u).total_seconds() > seconds


async def _get_current_prices() -> dict:
    agg = get_aggregator()
    prices = await agg.fetch_token_prices()
    return {k: Decimal(str(v)) for k, v in prices.items()}


async def _get_address_balances(address: str) -> dict:
    addr = address.lower()
    rows = await fetch_all(
        """SELECT token_symbol, SUM(balance) AS balance
           FROM wallet_balances WHERE address = %s
           GROUP BY token_symbol""",
        (addr,),
    ) or []
    return {r["token_symbol"]: Decimal(str(r["balance"] or 0)) for r in rows}


async def _get_entity_label(address: str) -> str:
    """Derive a human-readable entity label from cluster/owner data."""
    addr = address.lower()
    row = await fetch_one(
        """
        SELECT wc.cluster_size, ol.full_name
        FROM addresses a
        LEFT JOIN wallet_clusters wc ON a.cluster_id = wc.id
        LEFT JOIN owner_list ol ON wc.owner_id = ol.id
        WHERE a.address = %s
        LIMIT 1
        """,
        (addr,),
    )
    if row:
        if row.get("full_name"):
            return row["full_name"]
        size = row.get("cluster_size") or 1
        if size >= 10:
            return "Large Cluster"
        if size > 1:
            return "Cluster"
    bal_row = await fetch_one(
        "SELECT SUM(balance_usd) AS total FROM wallet_balances WHERE address = %s",
        (address.lower(),),
    )
    total = float((bal_row or {}).get("total") or 0)
    if total >= 1_000_000:
        return "Whale"
    if total >= 100_000:
        return "High Value"
    return "Individual"


def _validate_method(method: str) -> str:
    m = (method or "FIFO").upper()
    return m if m in ("FIFO", "LIFO", "HIFO") else "FIFO"


async def _resolve_cluster_id(cluster_id_or_address: str) -> str:
    """Resolve a cluster identifier from a cluster id or a representative address."""
    if not cluster_id_or_address:
        return cluster_id_or_address

    candidate = str(cluster_id_or_address).strip()

    # Already a cluster ID (e.g. C-DFEAFB85990B) — verify it exists, return as-is
    if candidate.upper().startswith('C-'):
        row = await fetch_one(
            "SELECT id FROM wallet_clusters WHERE id = %s LIMIT 1",
            (candidate.upper(),),
        )
        if row:
            return row['id']
        # Try case-insensitive fallback
        row = await fetch_one(
            "SELECT id FROM wallet_clusters WHERE UPPER(id) = %s LIMIT 1",
            (candidate.upper(),),
        )
        if row:
            return row['id']
        return candidate.upper()

    # It's a 0x address — look up its cluster
    if len(candidate) == 42 and candidate.lower().startswith('0x'):
        row = await fetch_one(
            "SELECT cluster_id FROM addresses WHERE address = %s LIMIT 1",
            (candidate.lower(),),
        )
        if row and row.get('cluster_id'):
            return row['cluster_id']

    return cluster_id_or_address


# ---------------------------------------------------------------------------
# Address endpoint
# ---------------------------------------------------------------------------

@router.get("/address/{address}")
async def get_address_mvrv(
    address: str,
    method: str = Query("FIFO", pattern="^(FIFO|LIFO|HIFO)$"),
):
    """Full MVRV breakdown for a single Ethereum address."""
    addr = address.lower()
    acct = _validate_method(method)

    # Always refresh on-chain balances (stale check: >1 h)
    latest_row = await fetch_one(
        "SELECT MAX(updated_at) AS u FROM wallet_balances WHERE address = %s", (addr,)
    )
    latest_u = (latest_row or {}).get("u")
    if _stale(latest_u):
        await get_aggregator().update_address(addr)
        latest_row = await fetch_one(
            "SELECT MAX(updated_at) AS u FROM wallet_balances WHERE address = %s", (addr,)
        )
        latest_u = (latest_row or {}).get("u")

    current_balances = await _get_address_balances(addr)
    current_prices   = await _get_current_prices()

    # If wallet_balances are all zero (RPC may have failed), fetch live ETH balance directly
    if not any(v > 0 for v in current_balances.values()):
        try:
            eth_bal = await get_aggregator().fetch_eth_balance(addr)
            if eth_bal > 0:
                current_balances["ETH"] = eth_bal
        except Exception:
            pass

    mvrv = await compute_mvrv_for_address(addr, current_prices, current_balances, acct)
    await save_mvrv_snapshot(addr, "address", mvrv)

    asset_rows = await fetch_all(
        """
        SELECT token_symbol,
               MAX(NULLIF(token_contract,'')) AS token_contract,
               SUM(balance)     AS balance,
               SUM(balance_usd) AS balance_usd
        FROM wallet_balances
        WHERE address = %s
        GROUP BY token_symbol, IFNULL(NULLIF(token_contract,''),'')
        ORDER BY balance_usd DESC
        """,
        (addr,),
    ) or []

    total_mv = mvrv["market_value_usd"]
    assets = []
    for r in asset_rows:
        sym    = r["token_symbol"]
        cb     = mvrv["cost_basis_per_token"].get(sym, {})
        mv_usd = float(r["balance_usd"] or 0)
        cb_available = cb.get("cost_basis_available", False)
        assets.append({
            "token_symbol":       sym,
            "token_contract":     r.get("token_contract") or None,
            "balance":            float(r["balance"] or 0),
            "current_price_usd":  float(current_prices.get(sym, Decimal("0"))),
            "market_value_usd":   mv_usd,
            # None when no acquisition history — never fabricate zero
            "cost_basis_usd":     float(cb["avg_cost_basis_usd"]) if cb_available and cb.get("avg_cost_basis_usd") is not None else None,
            "unrealized_pnl_usd": float(cb["unrealized_pnl_usd"]) if cb_available and cb.get("unrealized_pnl_usd") is not None else None,
            "realized_pnl_usd":   float(cb["realized_pnl_usd"])   if cb_available and cb.get("realized_pnl_usd")   is not None else None,
            "cost_basis_available": cb_available,
            "portfolio_percent":  round(mv_usd / total_mv * 100, 2) if total_mv > 0 else 0,
        })

    entity_label = await _get_entity_label(addr)
    flags        = generate_mvrv_flags(mvrv, assets)

    eth_v = sum(a["market_value_usd"] for a in assets if a["token_symbol"] in ("ETH", "WETH"))
    st_v  = sum(a["market_value_usd"] for a in assets if a["token_symbol"] in STABLECOINS)
    allocation = {
        "eth_percent":        round(eth_v / total_mv * 100, 2) if total_mv > 0 else 0,
        "stablecoin_percent": round(st_v  / total_mv * 100, 2) if total_mv > 0 else 0,
        "defi_percent":       0,
    }
    allocation["other_erc20_percent"] = round(
        100 - allocation["eth_percent"] - allocation["stablecoin_percent"], 2
    )

    return {
        "address":      address,
        "entity_label": entity_label,
        "mvrv":         mvrv,
        "summary": {
            "market_value_usd":   mvrv["market_value_usd"],
            "realized_value_usd": mvrv.get("realized_value_usd"),   # None if no history
            "mvrv_ratio":         mvrv.get("mvrv_ratio"),            # None if no history
            "unrealized_pnl_usd": mvrv.get("unrealized_pnl_usd"),   # None if no history
            "unrealized_pnl_pct": mvrv.get("unrealized_pnl_pct"),   # None if no history
            "realized_pnl_usd":   mvrv.get("realized_pnl_usd"),     # None if no history
            "net_pnl_usd":        mvrv.get("net_pnl_usd"),          # None if no history
            "tx_count_in":        mvrv["tx_count_in"],
            "tx_count_out":       mvrv["tx_count_out"],
            "tx_count_total":     mvrv["tx_count_total"],
            "token_count":        len(assets),
            "wallet_count":       1,
            "accounting_method":  acct,
            "updated_at":         _fmt_ts(latest_u),
            "cost_basis_available": mvrv.get("cost_basis_available", False),
            "history_complete":     mvrv.get("history_complete", False),
            "pricing_source":       mvrv.get("pricing_source", "chainlink_oracle"),
        },
        "assets":     assets,
        "allocation": allocation,
        "flags":      flags,
    }


# ---------------------------------------------------------------------------
# Cluster endpoint — pure aggregation from precomputed address snapshots
# No FIFO recomputation. No RPC calls. No wallet_balances reconstruction.
# Cluster MV/RV = SUM of address-level mvrv_snapshots only.
# ---------------------------------------------------------------------------

@router.get("/cluster/{cluster_id}")
async def get_cluster_mvrv(
    cluster_id: str,
    method: str = Query("FIFO", pattern="^(FIFO|LIFO|HIFO)$"),
):
    """
    Aggregate MVRV for a wallet cluster by summing precomputed address-level snapshots.

    Architecture:
      1. Resolve cluster → member addresses (no RPC)
      2. Fetch latest mvrv_snapshots for each member address (no FIFO recomputation)
      3. Aggregate: cluster_MV = SUM(addr.MV), cluster_RV = SUM(addr.RV), etc.
      4. Addresses with no snapshot are skipped (not zeroed)
      5. cluster_ratio = cluster_MV / cluster_RV (safe division)
    """
    acct = _validate_method(method)
    cluster_id = await _resolve_cluster_id(cluster_id)

    # Step 1 — resolve member addresses
    addr_rows = await fetch_all(
        "SELECT address FROM addresses WHERE cluster_id = %s", (cluster_id,)
    ) or []
    if not addr_rows:
        addr_rows = await fetch_all(
            "SELECT address FROM addresses WHERE UPPER(cluster_id) = %s", (cluster_id.upper(),)
        ) or []
    if not addr_rows:
        addr_rows = await fetch_all(
            "SELECT address FROM placement_entity_addresses WHERE entity_id = %s", (cluster_id,)
        ) or []
    if not addr_rows:
        addr_rows = await fetch_all(
            "SELECT address FROM layering_entity_addresses WHERE entity_id = %s", (cluster_id,)
        ) or []

    addresses = [r["address"].lower() for r in addr_rows]
    if not addresses:
        return _empty_cluster_response(cluster_id, acct)

    # Step 2 — fetch latest precomputed snapshots for all member addresses
    # One query for all members — no per-address loops, no FIFO, no RPC
    placeholders = ",".join(["%s"] * len(addresses))
    snapshot_rows = await fetch_all(
        f"""
        SELECT ms.entity_id,
               ms.market_value_usd,
               ms.realized_value_usd,
               ms.mvrv_ratio,
               ms.unrealized_pnl_usd,
               ms.realized_pnl_usd,
               ms.accounting_method,
               ms.snapshot_at
        FROM mvrv_snapshots ms
        INNER JOIN (
            SELECT entity_id, MAX(snapshot_at) AS latest
            FROM mvrv_snapshots
            WHERE entity_type = 'address'
              AND entity_id IN ({placeholders})
            GROUP BY entity_id
        ) latest_snap
          ON ms.entity_id = latest_snap.entity_id
         AND ms.snapshot_at = latest_snap.latest
        WHERE ms.entity_type = 'address'
        """,
        tuple(addresses),
    ) or []

    # Step 3 — pure aggregation (skip addresses with no snapshot)
    total_mv   = Decimal("0")
    total_rv   = Decimal("0")
    total_upnl = Decimal("0")
    total_rpnl = Decimal("0")
    addresses_with_snapshot = 0
    addresses_with_cost_basis = 0

    for snap in snapshot_rows:
        mv   = Decimal(str(snap["market_value_usd"]   or 0))
        rv   = Decimal(str(snap["realized_value_usd"] or 0))
        upnl = Decimal(str(snap["unrealized_pnl_usd"] or 0))
        rpnl = Decimal(str(snap["realized_pnl_usd"]   or 0))

        if mv <= 0:
            continue  # skip addresses with no holdings

        total_mv   += mv
        total_upnl += upnl
        total_rpnl += rpnl
        addresses_with_snapshot += 1

        if rv > 0:
            total_rv += rv
            addresses_with_cost_basis += 1

    # Step 4 — compute cluster-level ratio (safe division)
    if total_mv > 0 and total_rv > 0:
        cluster_ratio     = round(float(total_mv / total_rv), 6)
        upnl_pct          = round(float(total_upnl / total_rv * 100), 4)
        cost_basis_available = True
    elif total_mv > 0:
        cluster_ratio     = 0.0   # holdings exist but no cost basis
        upnl_pct          = 0.0
        cost_basis_available = False
    else:
        cluster_ratio     = 0.0
        upnl_pct          = 0.0
        cost_basis_available = False

    # Step 5 — build asset breakdown from wallet_balances (read-only, no recomputation)
    asset_rows = await fetch_all(
        f"""
        SELECT token_symbol,
               MAX(NULLIF(token_contract,'')) AS token_contract,
               SUM(balance)     AS balance,
               SUM(balance_usd) AS balance_usd
        FROM wallet_balances
        WHERE address IN ({placeholders})
        GROUP BY token_symbol, IFNULL(NULLIF(token_contract,''),'')
        ORDER BY balance_usd DESC
        """,
        tuple(addresses),
    ) or []

    total_mv_f = float(total_mv)
    assets = [
        {
            "token_symbol":       r["token_symbol"],
            "token_contract":     r.get("token_contract") or None,
            "balance":            float(r["balance"] or 0),
            "current_price_usd":  None,   # not recomputed — read from wallet_balances
            "market_value_usd":   float(r["balance_usd"] or 0),
            "cost_basis_usd":     None,   # cluster-level cost basis not per-token
            "unrealized_pnl_usd": None,
            "realized_pnl_usd":   None,
            "portfolio_percent":  round(float(r["balance_usd"] or 0) / total_mv_f * 100, 2)
                                  if total_mv_f > 0 else 0,
        }
        for r in asset_rows
        if float(r["balance_usd"] or 0) > 0
    ]

    eth_v = sum(a["market_value_usd"] for a in assets if a["token_symbol"] in ("ETH", "WETH"))
    st_v  = sum(a["market_value_usd"] for a in assets if a["token_symbol"] in STABLECOINS)
    allocation = {
        "eth_percent":        round(eth_v / total_mv_f * 100, 2) if total_mv_f > 0 else 0,
        "stablecoin_percent": round(st_v  / total_mv_f * 100, 2) if total_mv_f > 0 else 0,
        "defi_percent":       0,
    }
    allocation["other_erc20_percent"] = round(
        100 - allocation["eth_percent"] - allocation["stablecoin_percent"], 2
    )

    mvrv_out = {
        "market_value_usd":    total_mv_f,
        "realized_value_usd":  float(total_rv),
        "mvrv_ratio":          cluster_ratio,
        "unrealized_pnl_usd":  float(total_upnl),
        "unrealized_pnl_pct":  upnl_pct,
        "realized_pnl_usd":    float(total_rpnl),
        "net_pnl_usd":         float(total_upnl + total_rpnl),
        "cost_basis_per_token": {},
        "tx_count_total":      0,
        "wallet_count":        len(addresses),
        "accounting_method":   acct,
        "cost_basis_available": cost_basis_available,
        "history_complete":    cost_basis_available,
        "pricing_source":      "chainlink_oracle",
        "cost_basis_method":   acct,
    }

    # Save cluster snapshot
    if total_mv_f > 0:
        await save_mvrv_snapshot(cluster_id, "cluster", mvrv_out)

    flags = generate_mvrv_flags(mvrv_out, assets)

    return {
        "cluster_id":          cluster_id,
        "mvrv":                mvrv_out,
        "summary": {
            "market_value_usd":          total_mv_f,
            "realized_value_usd":        float(total_rv),
            "mvrv_ratio":                cluster_ratio,
            "unrealized_pnl_usd":        float(total_upnl),
            "unrealized_pnl_pct":        upnl_pct,
            "realized_pnl_usd":          float(total_rpnl),
            "net_pnl_usd":               float(total_upnl + total_rpnl),
            "tx_count_total":            0,
            "token_count":               len(assets),
            "wallet_count":              len(addresses),
            "accounting_method":         acct,
            "updated_at":                None,
            "cost_basis_available":      cost_basis_available,
            "addresses_with_snapshot":   addresses_with_snapshot,
            "addresses_with_cost_basis": addresses_with_cost_basis,
            "snapshot_status":           "COMPLETE" if cost_basis_available else
                                         ("PARTIAL" if total_mv_f > 0 else "EMPTY"),
        },
        "assets":     assets,
        "allocation": allocation,
        "flags":      flags,
    }


def _empty_cluster_response(cluster_id: str, method: str = "FIFO") -> dict:
    z = {
        "market_value_usd": 0, "realized_value_usd": 0, "mvrv_ratio": 1.0,
        "unrealized_pnl_usd": 0, "unrealized_pnl_pct": 0,
        "realized_pnl_usd": 0, "net_pnl_usd": 0,
        "tx_count_in": 0, "tx_count_out": 0, "tx_count_total": 0,
        "cost_basis_per_token": {}, "accounting_method": method,
    }
    return {
        "cluster_id": cluster_id, "mvrv": z,
        "summary": {**z, "token_count": 0, "wallet_count": 0, "updated_at": None},
        "assets": [],
        "allocation": {"eth_percent": 0, "stablecoin_percent": 0, "other_erc20_percent": 0, "defi_percent": 0},
        "flags": [],
    }


# ---------------------------------------------------------------------------
# History endpoint
# ---------------------------------------------------------------------------

@router.get("/history/{entity_id}")
async def get_mvrv_history_endpoint(
    entity_id: str,
    entity_type: str = Query("address", pattern="^(address|cluster)$"),
    days: int = Query(30, ge=1, le=365),
):
    if entity_type == 'address':
        entity_id = entity_id.lower()
    elif entity_type == 'cluster':
        entity_id = await _resolve_cluster_id(entity_id)
    history = await get_mvrv_history(entity_id, entity_type, days)
    return {"entity_id": entity_id, "entity_type": entity_type, "history": history}


# ---------------------------------------------------------------------------
# Directory endpoint — fast, no DDL, no CoinGecko
# ---------------------------------------------------------------------------

@router.get("/directory")
async def get_mvrv_directory(
    limit:  int = Query(25, ge=1, le=500),
    offset: int = Query(0, ge=0),
    q:      str = Query("", max_length=66),
    sort:   str = Query("market_value_usd", pattern="^(market_value_usd|mvrv_ratio|unrealized_pnl_usd|realized_pnl_usd|eth_total_units|updated_at)$"),
    order:  str = Query("desc", pattern="^(asc|desc)$"),
):
    """
    All known addresses ranked by chosen column, merged with latest MVRV snapshot.
    Pure read — no DDL, no on-chain calls, no CoinGecko.
    """
    search     = (q or "").strip().lower()
    where_sql  = " WHERE z.address LIKE %s " if search else ""
    where_args = (f"%{search}%",) if search else ()

    # Union of all address sources — only include addresses that have
    # actual transaction data or wallet balance data (skip empty/burn addresses)
    union_core = """
        SELECT LOWER(address) AS address FROM addresses
            WHERE CHAR_LENGTH(address) = 42 AND address LIKE '0x%%'
            AND (total_in > 0 OR total_out > 0 OR tx_count > 0)
        UNION
        SELECT LOWER(address) FROM wallet_balances
            WHERE CHAR_LENGTH(address) = 42 AND address LIKE '0x%%'
            AND balance_usd > 0
        UNION
        SELECT LOWER(address) FROM placement_entity_addresses
            WHERE CHAR_LENGTH(address) = 42 AND address LIKE '0x%%'
        UNION
        SELECT LOWER(address) FROM layering_entity_addresses
            WHERE CHAR_LENGTH(address) = 42 AND address LIKE '0x%%'
    """

    if search:
        count_row = await fetch_one(
            f"SELECT COUNT(*) AS c FROM ({union_core}) z {where_sql}", where_args
        )
        total = int((count_row or {}).get("c") or 0)
    else:
        cache_ts = _directory_count_cache.get('updated_at')
        if cache_ts and (datetime.now(timezone.utc) - cache_ts).total_seconds() < _DIRECTORY_COUNT_TTL:
            total = _directory_count_cache['count']
        else:
            count_row = await fetch_one(
                f"SELECT COUNT(*) AS c FROM ({union_core}) z",
                (),
            )
            total = int((count_row or {}).get("c") or 0)
            _directory_count_cache['count'] = total
            _directory_count_cache['updated_at'] = datetime.now(timezone.utc)

    # Safe sort column map
    sort_col_map = {
        "market_value_usd":   "COALESCE(w.total_value_usd, 0)",
        "mvrv_ratio":         "COALESCE(ms.mvrv_ratio, 0)",
        "unrealized_pnl_usd": "COALESCE(ms.unrealized_pnl_usd, 0)",
        "realized_pnl_usd":   "COALESCE(ms.realized_pnl_usd, 0)",
        "eth_total_units":    "COALESCE(w.eth_total_units, 0)",
        "updated_at":         "w.updated_at",
    }
    sort_expr = sort_col_map.get(sort, "COALESCE(w.total_value_usd, 0)")
    order_dir = "DESC" if order == "desc" else "ASC"

    # Latest snapshot per address using a non-correlated GROUP BY join (fast)
    sql = f"""
        SELECT
            z.address,
            COALESCE(w.total_value_usd, 0)        AS market_value_usd,
            COALESCE(w.eth_total_units, 0)         AS eth_total_units,
            COALESCE(w.stablecoin_value_usd, 0)    AS stablecoin_value_usd,
            COALESCE(w.token_slots, 0)             AS token_slots,
            w.updated_at                           AS updated_at,
            COALESCE(ms.realized_value_usd, 0)     AS realized_value_usd,
            COALESCE(ms.mvrv_ratio, 0)             AS mvrv_ratio,
            COALESCE(ms.unrealized_pnl_usd, 0)     AS unrealized_pnl_usd,
            COALESCE(ms.realized_pnl_usd, 0)       AS realized_pnl_usd,
            COALESCE(ms.accounting_method, 'FIFO') AS accounting_method,
            ms.snapshot_at                         AS mvrv_snapshot_at,
            COALESCE(a_lbl.cluster_size, 1)        AS cluster_size,
            COALESCE(ol.full_name, '')             AS owner_name
        FROM ({union_core}) z
        LEFT JOIN (
            SELECT address,
                   SUM(balance_usd) AS total_value_usd,
                   SUM(CASE WHEN token_symbol IN ('ETH','WETH') THEN balance ELSE 0 END) AS eth_total_units,
                   SUM(CASE WHEN token_symbol IN ('USDT','USDC','DAI','BUSD') THEN balance_usd ELSE 0 END) AS stablecoin_value_usd,
                   COUNT(DISTINCT CONCAT(token_symbol,'|',IFNULL(token_contract,''))) AS token_slots,
                   MAX(updated_at) AS updated_at
            FROM wallet_balances
            GROUP BY address
        ) w ON z.address = w.address
        LEFT JOIN (
            SELECT entity_id,
                   realized_value_usd, mvrv_ratio,
                   unrealized_pnl_usd, realized_pnl_usd,
                   accounting_method,  snapshot_at
            FROM mvrv_snapshots
            WHERE entity_type = 'address'
              AND (entity_id, snapshot_at) IN (
                  SELECT entity_id, MAX(snapshot_at)
                  FROM mvrv_snapshots
                  WHERE entity_type = 'address'
                  GROUP BY entity_id
              )
        ) ms ON z.address = ms.entity_id
        LEFT JOIN addresses addr_tbl ON z.address = addr_tbl.address
        LEFT JOIN wallet_clusters a_lbl ON addr_tbl.cluster_id = a_lbl.id
        LEFT JOIN owner_list ol ON a_lbl.owner_id = ol.id
        {where_sql}
        ORDER BY {sort_expr} {order_dir}, z.address ASC
        LIMIT %s OFFSET %s
    """

    rows = await fetch_all(sql, where_args + (limit, offset)) or []

    items = []
    for row in rows:
        mv    = float(row["market_value_usd"] or 0)
        rv    = float(row["realized_value_usd"] or 0)
        snap  = row.get("mvrv_snapshot_at")

        # Recompute ratio from actual MV/RV — never trust stored ratio if MV changed
        if mv > 0 and rv > 0:
            ratio = round(mv / rv, 6)
        elif snap:
            ratio = float(row["mvrv_ratio"] or 0)
        else:
            ratio = 0.0

        upnl     = mv - rv if (mv > 0 and rv > 0) else float(row["unrealized_pnl_usd"] or 0)
        upnl_pct = round(upnl / rv * 100, 2) if rv > 0 else 0.0

        owner = (row.get("owner_name") or "").strip()
        size  = int(row.get("cluster_size") or 1)
        if owner:
            label = owner
        elif mv >= 1_000_000:
            label = "Whale"
        elif mv >= 100_000:
            label = "High Value"
        elif size >= 10:
            label = "Large Cluster"
        elif size > 1:
            label = "Cluster"
        else:
            label = "Individual"

        items.append({
            "address":              row["address"],
            "entity_label":         label,
            "market_value_usd":     mv,
            "realized_value_usd":   rv,
            "mvrv_ratio":           ratio,
            "unrealized_pnl_usd":   upnl,
            "unrealized_pnl_pct":   upnl_pct,
            "realized_pnl_usd":     float(row["realized_pnl_usd"] or 0),
            "eth_total_units":      float(row["eth_total_units"] or 0),
            "stablecoin_value_usd": float(row["stablecoin_value_usd"] or 0),
            "token_slots":          int(row["token_slots"] or 0),
            "accounting_method":    row.get("accounting_method") or "FIFO",
            "updated_at":           _fmt_ts(row.get("updated_at")),
            "mvrv_snapshot_at":     _fmt_ts(row.get("mvrv_snapshot_at")),
        })

    return {"total": total, "limit": limit, "offset": offset, "items": items}


# ---------------------------------------------------------------------------
# Force-refresh
# ---------------------------------------------------------------------------

@router.post("/refresh/{address}")
async def refresh_address_mvrv(
    address: str,
    method: str = Query("FIFO", pattern="^(FIFO|LIFO|HIFO)$"),
):
    """Force-refresh on-chain balances and recompute MVRV."""
    await get_aggregator().update_address(address.lower())
    return await get_address_mvrv(address.lower(), method=method)


# ---------------------------------------------------------------------------
# Bulk populate — compute MV from transaction history for all addresses
# No on-chain RPC calls needed — uses local DB transactions + current price
# ---------------------------------------------------------------------------

@router.post("/bulk-populate")
async def bulk_populate_mvrv(
    limit: int = Query(5000, ge=1, le=20000),
    skip_existing: bool = Query(True),
):
    """
    Compute MVRV snapshots for all addresses with incoming transactions.
    Uses FIFO cost basis from local transaction history + Chainlink oracle prices.
    No RPC calls — fully offline from local DB.

    Addresses with ONLY outgoing transactions are skipped (no cost basis possible).
    Results include cost_basis_available flag for forensic traceability.
    """
    current_prices = await _get_current_prices()
    eth_price = current_prices.get("ETH", Decimal("0"))
    if eth_price <= 0:
        return {"error": "ETH price unavailable — ensure ALCHEMY_RPC is configured", "populated": 0}

    # Get addresses that already have real snapshots (skip if requested)
    existing = set()
    if skip_existing:
        rows = await fetch_all(
            "SELECT DISTINCT entity_id FROM mvrv_snapshots WHERE entity_type='address' AND market_value_usd > 0"
        ) or []
        existing = {r["entity_id"] for r in rows}

    # Get ALL addresses with incoming transactions (these can have real cost basis)
    addr_rows = await fetch_all(
        """
        SELECT address, total_in, total_out, tx_count
        FROM addresses
        WHERE address LIKE '0x%%'
          AND LENGTH(address) = 42
          AND total_in > 0
        ORDER BY (total_in + total_out) DESC
        LIMIT %s
        """,
        (limit,),
    ) or []

    populated       = 0
    skipped_exists  = 0
    skipped_no_mv   = 0
    insufficient    = 0

    from services.mvrv_calculator import compute_mvrv_for_address, save_mvrv_snapshot as _save

    for row in addr_rows:
        addr = row["address"].lower()
        if addr in existing:
            skipped_exists += 1
            continue

        # Build current_balances from wallet_balances if available,
        # otherwise derive from net tx history (total_in - total_out)
        bal_rows = await fetch_all(
            "SELECT token_symbol, SUM(balance) AS balance FROM wallet_balances WHERE address = %s GROUP BY token_symbol",
            (addr,),
        ) or []
        current_balances = {r["token_symbol"]: Decimal(str(r["balance"] or 0)) for r in bal_rows if float(r["balance"] or 0) > 0}

        if not current_balances:
            net_eth = max(float(row["total_in"] or 0) - float(row["total_out"] or 0), 0.0)
            if net_eth > 0:
                current_balances["ETH"] = Decimal(str(net_eth))

        if not current_balances:
            skipped_no_mv += 1
            continue

        try:
            mvrv = await compute_mvrv_for_address(addr, current_prices, current_balances, "FIFO")

            if mvrv["market_value_usd"] <= 0:
                skipped_no_mv += 1
                continue

            if not mvrv.get("cost_basis_available"):
                insufficient += 1
                # Still save the snapshot — MV is real, just RV is unavailable
                # mvrv_ratio=0 signals "no cost basis" to the frontend

            await _save(addr, "address", mvrv)
            populated += 1

        except Exception:
            skipped_no_mv += 1
            continue

    _directory_count_cache['updated_at'] = None

    return {
        "populated":            populated,
        "skipped_already_done": skipped_exists,
        "skipped_no_balance":   skipped_no_mv,
        "insufficient_history": insufficient,
        "eth_price_used":       float(eth_price),
        "total_candidates":     len(addr_rows),
        "note":                 "FIFO cost basis from local tx history + Chainlink oracle prices. cost_basis_available=false means address has no incoming txs.",
    }
