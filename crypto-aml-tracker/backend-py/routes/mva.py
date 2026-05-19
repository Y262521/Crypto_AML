"""
Market Value Analysis (MVA) Routes
On-chain portfolio intelligence for wallet clusters and addresses.
"""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from db.mysql import fetch_all, fetch_one, get_pool
import aiomysql

router = APIRouter()


def _format_ts_utc(value) -> str | None:
    """Serialize DB/datetime timestamps as UTC ISO-8601 for JSON."""
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


@router.post("/trigger-update/{address}")
async def trigger_balance_update(address: str):
    """
    Manual trigger to update balances for testing.
    """
    try:
        from services.balance_aggregator import get_aggregator
        aggregator = get_aggregator()
        
        print(f"\n{'='*60}")
        print(f"MANUAL TRIGGER: Updating {address}")
        print(f"{'='*60}")
        
        await aggregator.update_address(address.lower())
        
        return {"status": "success", "message": f"Updated balances for {address}"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


async def ensure_mva_schema():
    """Create MVA tables if they don't exist."""
    pool = get_pool()
    if not pool:
        return

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # wallet_balances table
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS wallet_balances (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    address VARCHAR(42) NOT NULL,
                    token_symbol VARCHAR(20) NOT NULL,
                    token_contract VARCHAR(42),
                    balance DECIMAL(36, 18) NOT NULL DEFAULT 0,
                    balance_usd DECIMAL(20, 2) NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_address (address),
                    INDEX idx_token (token_symbol),
                    INDEX idx_updated (updated_at),
                    UNIQUE KEY unique_address_token (address, token_symbol, token_contract)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # cluster_portfolios table
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS cluster_portfolios (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    cluster_id VARCHAR(255) NOT NULL,
                    total_value_usd DECIMAL(20, 2) NOT NULL DEFAULT 0,
                    eth_value_usd DECIMAL(20, 2) NOT NULL DEFAULT 0,
                    stablecoin_value_usd DECIMAL(20, 2) NOT NULL DEFAULT 0,
                    defi_exposure_usd DECIMAL(20, 2) NOT NULL DEFAULT 0,
                    token_count INT NOT NULL DEFAULT 0,
                    wallet_count INT NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_cluster (cluster_id),
                    INDEX idx_total_value (total_value_usd),
                    INDEX idx_updated (updated_at),
                    UNIQUE KEY unique_cluster (cluster_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # token_price_cache table
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS token_price_cache (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    token_symbol VARCHAR(20) NOT NULL,
                    token_contract VARCHAR(42),
                    price_usd DECIMAL(20, 8) NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_symbol (token_symbol),
                    INDEX idx_contract (token_contract),
                    INDEX idx_updated (updated_at),
                    UNIQUE KEY unique_token (token_symbol, token_contract)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            # portfolio_history table for historical tracking
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_history (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    entity_id VARCHAR(255) NOT NULL,
                    entity_type ENUM('address', 'cluster') NOT NULL,
                    total_value_usd DECIMAL(20, 2) NOT NULL DEFAULT 0,
                    eth_value_usd DECIMAL(20, 2) NOT NULL DEFAULT 0,
                    stablecoin_value_usd DECIMAL(20, 2) NOT NULL DEFAULT 0,
                    snapshot_at TIMESTAMP NOT NULL,
                    INDEX idx_entity (entity_id, entity_type),
                    INDEX idx_snapshot (snapshot_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

            await conn.commit()
            print("✓ MVA schema initialized")
            # Normalize legacy native-ETH rows so UNIQUE(address, token_symbol, token_contract) dedupes correctly
            try:
                await cur.execute(
                    """
                    UPDATE wallet_balances
                    SET token_contract = ''
                    WHERE token_symbol = 'ETH' AND (token_contract IS NULL OR token_contract = '')
                    """
                )
                await conn.commit()
            except Exception as mig_e:
                print(f"MVA ETH contract normalization skipped: {mig_e}")


@router.get("/cluster/{cluster_id}")
async def get_cluster_mva(cluster_id: str):
    """
    Get Market Value Analysis for a wallet cluster.
    Returns portfolio summary, asset holdings, allocation, and intelligence flags.
    Automatically fetches balances if not in database.
    """
    try:
        # Get cluster portfolio summary
        portfolio = await fetch_one(
            """
            SELECT 
                cluster_id,
                total_value_usd,
                eth_value_usd,
                stablecoin_value_usd,
                defi_exposure_usd,
                token_count,
                wallet_count,
                updated_at
            FROM cluster_portfolios
            WHERE cluster_id = %s
            """,
            (cluster_id,)
        )

        # Get cluster addresses from addresses table
        addresses_result = await fetch_all(
            """
            SELECT address
            FROM addresses
            WHERE cluster_id = %s
            """,
            (cluster_id,)
        )

        addresses = [row['address'] for row in addresses_result] if addresses_result else []

        def _portfolio_stale(row: dict) -> bool:
            if not row or not row.get("updated_at"):
                return True
            u = row["updated_at"]
            if getattr(u, "tzinfo", None) is None:
                u = u.replace(tzinfo=timezone.utc)
            else:
                u = u.astimezone(timezone.utc)
            return (datetime.now(timezone.utc) - u).total_seconds() > 3600

        # If no portfolio data or stale (>1 hour), fetch fresh balances
        if not portfolio or _portfolio_stale(portfolio):
            if addresses:
                print(f"Fetching fresh balances for cluster {cluster_id} ({len(addresses)} addresses)...")
                from services.balance_aggregator import get_aggregator
                aggregator = get_aggregator()
                await aggregator.update_cluster(cluster_id, [addr.lower() for addr in addresses])
                
                # Re-fetch portfolio after update
                portfolio = await fetch_one(
                    """
                    SELECT 
                        cluster_id,
                        total_value_usd,
                        eth_value_usd,
                        stablecoin_value_usd,
                        defi_exposure_usd,
                        token_count,
                        wallet_count,
                        updated_at
                    FROM cluster_portfolios
                    WHERE cluster_id = %s
                    """,
                    (cluster_id,)
                )

        if not portfolio:
            # Return empty state if no data yet
            return {
                "cluster_id": cluster_id,
                "summary": {
                    "total_value_usd": 0,
                    "eth_value_usd": 0,
                    "stablecoin_value_usd": 0,
                    "defi_exposure_usd": 0,
                    "token_count": 0,
                    "wallet_count": len(addresses) if addresses else 0,
                    "updated_at": None
                },
                "assets": [],
                "allocation": {
                    "eth_percent": 0,
                    "stablecoin_percent": 0,
                    "other_erc20_percent": 0,
                    "defi_percent": 0
                },
                "flags": []
            }

        # Get asset holdings for all addresses in cluster
        if addresses:
            placeholders = ','.join(['%s'] * len(addresses))
            assets = await fetch_all(
                f"""
                SELECT 
                    token_symbol,
                    MAX(NULLIF(token_contract, '')) as token_contract,
                    SUM(balance) as total_balance,
                    SUM(balance_usd) as total_value_usd
                FROM wallet_balances
                WHERE address IN ({placeholders})
                GROUP BY token_symbol, IFNULL(NULLIF(token_contract, ''), '')
                ORDER BY total_value_usd DESC
                """,
                tuple(addresses)
            )
        else:
            assets = []

        # Calculate allocation percentages
        total = float(portfolio['total_value_usd'] or 0)
        allocation = {
            "eth_percent": round((float(portfolio['eth_value_usd'] or 0) / total * 100) if total > 0 else 0, 2),
            "stablecoin_percent": round((float(portfolio['stablecoin_value_usd'] or 0) / total * 100) if total > 0 else 0, 2),
            "defi_percent": round((float(portfolio['defi_exposure_usd'] or 0) / total * 100) if total > 0 else 0, 2),
        }
        allocation["other_erc20_percent"] = round(
            100 - allocation["eth_percent"] - allocation["stablecoin_percent"] - allocation["defi_percent"],
            2
        )

        # Generate intelligence flags
        flags = generate_intelligence_flags(portfolio, assets)

        # Format assets for response
        formatted_assets = [
            {
                "token_symbol": asset['token_symbol'],
                "token_contract": asset.get("token_contract") or None,
                "balance": float(asset['total_balance'] or 0),
                "value_usd": float(asset['total_value_usd'] or 0),
                "portfolio_percent": round((float(asset['total_value_usd'] or 0) / total * 100) if total > 0 else 0, 2)
            }
            for asset in assets
        ]

        return {
            "cluster_id": cluster_id,
            "summary": {
                "total_value_usd": float(portfolio['total_value_usd'] or 0),
                "eth_value_usd": float(portfolio['eth_value_usd'] or 0),
                "stablecoin_value_usd": float(portfolio['stablecoin_value_usd'] or 0),
                "defi_exposure_usd": float(portfolio['defi_exposure_usd'] or 0),
                "token_count": int(portfolio['token_count'] or 0),
                "wallet_count": int(portfolio['wallet_count'] or 0),
                "updated_at": _format_ts_utc(portfolio.get("updated_at"))
            },
            "assets": formatted_assets,
            "allocation": allocation,
            "flags": flags
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch MVA data: {str(e)}")


@router.get("/address/{address}")
async def get_address_mva(address: str):
    """
    Get Market Value Analysis for a single address.
    Automatically fetches balances if not in database or stale (>1 hour).
    """
    try:
        print(f"\n{'='*60}")
        print(f"MVA REQUEST for address: {address}")
        print(f"{'='*60}")

        addr = address.lower()

        def _row_stale(updated_at) -> bool:
            if not updated_at:
                return True
            u = updated_at
            if getattr(u, "tzinfo", None) is None:
                u = u.replace(tzinfo=timezone.utc)
            else:
                u = u.astimezone(timezone.utc)
            return (datetime.now(timezone.utc) - u).total_seconds() > 3600

        # Existing snapshot (aggregated; avoids duplicate ETH rows from legacy NULL keys)
        assets = await fetch_all(
            """
            SELECT 
                token_symbol,
                MAX(NULLIF(token_contract, '')) as token_contract,
                SUM(balance) as balance,
                SUM(balance_usd) as balance_usd,
                MAX(updated_at) as updated_at
            FROM wallet_balances
            WHERE address = %s
            GROUP BY token_symbol, IFNULL(NULLIF(token_contract, ''), '')
            ORDER BY balance_usd DESC
            """,
            (addr,),
        )

        latest_u = None
        for a in assets or []:
            t = a.get("updated_at")
            if t and (latest_u is None or t > latest_u):
                latest_u = t
        need_refresh = not assets or _row_stale(latest_u)
        if need_refresh:
            print("Fetching / refreshing on-chain balances...")
            from services.balance_aggregator import get_aggregator

            aggregator = get_aggregator()
            await aggregator.update_address(addr)
            assets = await fetch_all(
                """
                SELECT 
                    token_symbol,
                    MAX(NULLIF(token_contract, '')) as token_contract,
                    SUM(balance) as balance,
                    SUM(balance_usd) as balance_usd,
                    MAX(updated_at) as updated_at
                FROM wallet_balances
                WHERE address = %s
                GROUP BY token_symbol, IFNULL(NULLIF(token_contract, ''), '')
                ORDER BY balance_usd DESC
                """,
                (addr,),
            )
        
        print(f"Found {len(assets) if assets else 0} assets in database")
        if assets:
            for asset in assets[:3]:  # Show first 3
                print(f"  - {asset['token_symbol']}: {asset['balance']} (${asset['balance_usd']})")

        # Calculate summary
        total_value = sum(float(asset['balance_usd'] or 0) for asset in assets)
        eth_value = sum(float(asset['balance_usd'] or 0) for asset in assets if asset['token_symbol'] in ['ETH', 'WETH'])
        stablecoin_value = sum(float(asset['balance_usd'] or 0) for asset in assets if asset['token_symbol'] in ['USDT', 'USDC', 'DAI', 'BUSD'])

        # Calculate allocation
        allocation = {
            "eth_percent": round((eth_value / total_value * 100) if total_value > 0 else 0, 2),
            "stablecoin_percent": round((stablecoin_value / total_value * 100) if total_value > 0 else 0, 2),
            "defi_percent": 0,  # TODO: Calculate based on DeFi token detection
        }
        allocation["other_erc20_percent"] = round(
            100 - allocation["eth_percent"] - allocation["stablecoin_percent"],
            2
        )

        latest = None
        if assets:
            for a in assets:
                t = a.get("updated_at")
                if t and (latest is None or t > latest):
                    latest = t
        updated_iso = None
        if latest:
            if getattr(latest, "tzinfo", None) is None:
                latest = latest.replace(tzinfo=timezone.utc)
            else:
                latest = latest.astimezone(timezone.utc)
            updated_iso = latest.isoformat()

        summary = {
            "total_value_usd": total_value,
            "eth_value_usd": eth_value,
            "stablecoin_value_usd": stablecoin_value,
            "defi_exposure_usd": 0,
            "token_count": len(assets),
            "wallet_count": 1,
            "updated_at": updated_iso,
        }

        # Generate flags
        flags = generate_intelligence_flags(summary, assets)

        # Format assets
        formatted_assets = [
            {
                "token_symbol": asset['token_symbol'],
                "token_contract": asset.get("token_contract") or None,
                "balance": float(asset['balance'] or 0),
                "value_usd": float(asset['balance_usd'] or 0),
                "portfolio_percent": round((float(asset['balance_usd'] or 0) / total_value * 100) if total_value > 0 else 0, 2)
            }
            for asset in assets
        ]

        return {
            "address": address,
            "summary": summary,
            "assets": formatted_assets,
            "allocation": allocation,
            "flags": flags
        }

    except Exception as e:
        print(f"Error in address MVA: {e}")
        import traceback
        traceback.print_exc()
        # Return empty state instead of error
        return {
            "address": address,
            "summary": {
                "total_value_usd": 0,
                "eth_value_usd": 0,
                "stablecoin_value_usd": 0,
                "defi_exposure_usd": 0,
                "token_count": 0,
                "wallet_count": 1,
                "updated_at": None
            },
            "assets": [],
            "allocation": {
                "eth_percent": 0,
                "stablecoin_percent": 0,
                "other_erc20_percent": 0,
                "defi_percent": 0
            },
            "flags": []
        }


@router.get("/history/{entity_id}")
async def get_portfolio_history(
    entity_id: str,
    entity_type: str = Query("cluster", pattern="^(address|cluster)$"),
    days: int = Query(30, ge=1, le=365)
):
    """
    Get historical portfolio value for an entity.
    """
    try:
        history = await fetch_all(
            """
            SELECT 
                total_value_usd,
                eth_value_usd,
                stablecoin_value_usd,
                snapshot_at
            FROM portfolio_history
            WHERE entity_id = %s AND entity_type = %s
            AND snapshot_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
            ORDER BY snapshot_at ASC
            """,
            (entity_id, entity_type, days)
        )

        return {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "history": [
                {
                    "total_value_usd": float(h['total_value_usd'] or 0),
                    "eth_value_usd": float(h['eth_value_usd'] or 0),
                    "stablecoin_value_usd": float(h['stablecoin_value_usd'] or 0),
                    "timestamp": _format_ts_utc(h.get("snapshot_at")) or "",
                }
                for h in history
            ] if history else []
        }

    except Exception as e:
        err_no = getattr(e, "args", [None])[0]
        if err_no == 1146:
            try:
                await ensure_mva_schema()
                history = await fetch_all(
                    """
                    SELECT 
                        total_value_usd,
                        eth_value_usd,
                        stablecoin_value_usd,
                        snapshot_at
                    FROM portfolio_history
                    WHERE entity_id = %s AND entity_type = %s
                    AND snapshot_at >= DATE_SUB(NOW(), INTERVAL %s DAY)
                    ORDER BY snapshot_at ASC
                    """,
                    (entity_id, entity_type, days)
                )
                return {
                    "entity_id": entity_id,
                    "entity_type": entity_type,
                    "history": [
                        {
                            "total_value_usd": float(h['total_value_usd'] or 0),
                            "eth_value_usd": float(h['eth_value_usd'] or 0),
                            "stablecoin_value_usd": float(h['stablecoin_value_usd'] or 0),
                            "timestamp": _format_ts_utc(h.get("snapshot_at")) or "",
                        }
                        for h in history
                    ] if history else []
                }
            except Exception as e2:
                print(f"Error fetching history after schema init: {e2}")
        else:
            print(f"Error fetching history: {e}")
        return {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "history": []
        }


def _decimal_to_wei_str(eth_units: object) -> str:
    """Convert native ETH decimal balance to integer wei string (no floats)."""
    try:
        d = Decimal(str(eth_units or 0))
    except Exception:
        return "0"
    wei = (d * Decimal(10**18)).to_integral_value(rounding=ROUND_DOWN)
    return format(int(wei), "d")


@router.get("/directory")
async def get_mva_directory(
    limit: int = Query(25, ge=1, le=500),
    offset: int = Query(0, ge=0, le=100_000),
    q: str = Query("", max_length=66),
):
    """
    All known Ethereum addresses from the AML graph + pipeline tables, merged with cached MVA balances.
    Sorted by on-book USD (high → low); addresses without cache show zeros until balances are fetched.
    """
    try:
        await ensure_mva_schema()
    except Exception:
        pass

    search = (q or "").strip().lower()
    where_sql = ""
    where_args: tuple = ()
    if search:
        where_sql = " WHERE z.address LIKE %s "
        where_args = (f"%{search}%",)

    # Literal % must be %% — aiomysql applies Python %-formatting to the full query string.
    union_core = """
        SELECT LOWER(TRIM(address)) AS address FROM addresses
            WHERE CHAR_LENGTH(address) = 42 AND LOWER(address) LIKE '0x%%'
        UNION
        SELECT LOWER(TRIM(address)) FROM wallet_balances
            WHERE CHAR_LENGTH(address) = 42 AND LOWER(address) LIKE '0x%%'
        UNION
        SELECT LOWER(TRIM(address)) FROM placement_entity_addresses
            WHERE CHAR_LENGTH(address) = 42 AND LOWER(address) LIKE '0x%%'
        UNION
        SELECT LOWER(TRIM(address)) FROM layering_entity_addresses
            WHERE CHAR_LENGTH(address) = 42 AND LOWER(address) LIKE '0x%%'
    """

    count_sql = "SELECT COUNT(*) AS c FROM (" + union_core + ") z " + where_sql
    count_row = await fetch_one(count_sql, where_args)
    total = int(count_row["c"] or 0) if count_row else 0

    sql = (
        """
        SELECT
            z.address,
            COALESCE(w.total_value_usd, 0) AS total_value_usd,
            COALESCE(w.eth_total_units, 0) AS eth_total_units,
            COALESCE(w.eth_native_units, 0) AS eth_native_units,
            COALESCE(w.stablecoin_value_usd, 0) AS stablecoin_value_usd,
            COALESCE(w.token_slots, 0) AS token_slots,
            w.updated_at AS updated_at
        FROM (
        """
        + union_core
        + """
        ) z
        LEFT JOIN (
            SELECT
                LOWER(address) AS address,
                SUM(balance_usd) AS total_value_usd,
                SUM(CASE WHEN token_symbol IN ('ETH', 'WETH') THEN balance ELSE 0 END) AS eth_total_units,
                SUM(CASE WHEN token_symbol = 'ETH' THEN balance ELSE 0 END) AS eth_native_units,
                SUM(CASE WHEN token_symbol IN ('USDT', 'USDC', 'DAI', 'BUSD') THEN balance_usd ELSE 0 END) AS stablecoin_value_usd,
                COUNT(DISTINCT CONCAT(token_symbol, '|', IFNULL(token_contract, ''))) AS token_slots,
                MAX(updated_at) AS updated_at
            FROM wallet_balances
            GROUP BY LOWER(address)
        ) w ON z.address = w.address
        """
        + where_sql
        + " ORDER BY total_value_usd DESC, z.address ASC LIMIT %s OFFSET %s"
    )
    rows = await fetch_all(sql, where_args + (limit, offset)) or []

    items = []
    for row in rows:
        eth_native = row.get("eth_native_units") or 0
        eth_total = row.get("eth_total_units") or 0
        items.append(
            {
                "address": row["address"],
                "total_value_usd": float(row["total_value_usd"] or 0),
                "eth_total_units": float(eth_total),
                "eth_native_units": float(eth_native),
                "eth_wei": _decimal_to_wei_str(eth_native),
                "stablecoin_value_usd": float(row["stablecoin_value_usd"] or 0),
                "token_slots": int(row["token_slots"] or 0),
                "updated_at": _format_ts_utc(row.get("updated_at")),
            }
        )

    return {"total": total, "limit": limit, "offset": offset, "items": items}


def generate_intelligence_flags(portfolio: dict, assets: list) -> list:
    """
    Generate simple analytical flags based on portfolio characteristics.
    NO centralized risk engine, NO POI scoring, NO alert orchestration.
    """
    flags = []
    
    total_value = float(portfolio.get('total_value_usd', 0))
    stablecoin_value = float(portfolio.get('stablecoin_value_usd', 0))
    eth_value = float(portfolio.get('eth_value_usd', 0))
    
    # High Value Wallet
    if total_value > 100000:
        flags.append({
            "type": "high_value",
            "label": "High Value Wallet",
            "description": f"Portfolio value exceeds $100K (${total_value:,.2f})",
            "severity": "info"
        })
    
    # Stablecoin Heavy
    if total_value > 0 and (stablecoin_value / total_value) > 0.7:
        flags.append({
            "type": "stablecoin_heavy",
            "label": "Stablecoin Heavy",
            "description": f"Stablecoins represent {(stablecoin_value/total_value*100):.1f}% of portfolio",
            "severity": "warning"
        })
    
    # Dormant Wealth (no recent update)
    updated_at = portfolio.get('updated_at')
    if updated_at:
        from datetime import datetime, timedelta
        if isinstance(updated_at, str):
            s = updated_at.replace('Z', '+00:00')
            try:
                updated_at = datetime.fromisoformat(s)
            except ValueError:
                updated_at = None
        if updated_at is not None:
            if getattr(updated_at, 'tzinfo', None) is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            else:
                updated_at = updated_at.astimezone(timezone.utc)
        if updated_at is not None and datetime.now(timezone.utc) - updated_at > timedelta(days=30):
            flags.append({
                "type": "dormant",
                "label": "Dormant Wealth",
                "description": "No balance updates in 30+ days",
                "severity": "info"
            })
    
    # ETH Dominant
    if total_value > 0 and (eth_value / total_value) > 0.8:
        flags.append({
            "type": "eth_dominant",
            "label": "ETH Dominant",
            "description": f"ETH represents {(eth_value/total_value*100):.1f}% of portfolio",
            "severity": "info"
        })
    
    # Diversified Portfolio
    if len(assets) > 10:
        flags.append({
            "type": "diversified",
            "label": "Diversified Portfolio",
            "description": f"Holds {len(assets)} different tokens",
            "severity": "info"
        })
    
    return flags
