"""
Transaction routes.

Data priority:
  - Transactions / Alerts / Analytics  → MySQL (aml_db.transactions)
  - Graph                               → Neo4j (:Address)-[:TRANSFER]->(:Address)
  - Fallback for both                   → MongoDB (processed_transactions / raw_transactions)
"""

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
import httpx

from db.mysql import fetch_all, fetch_one, get_pool
from db.neo4j import get_driver
from db.mongo import get_db

router = APIRouter()
NODE_URL = "https://ethereum-rpc.publicnode.com"

# ── helpers ───────────────────────────────────────────────────────────────────

async def rpc(method: str, params: list = []):
    async with httpx.AsyncClient() as client:
        r = await client.post(NODE_URL, json={
            "jsonrpc": "2.0", "id": 1, "method": method, "params": params
        }, timeout=15)
        return r.json().get("result")


def _to_float(value) -> float:
    if value is None:
        return 0.0
    try:
        if hasattr(value, "to_decimal"):
            return float(value.to_decimal())
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _fmt_ts(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%m/%d/%Y, %I:%M:%S %p")
    return str(value)


def _risk_score(row: dict) -> int:
    score = 0
    if row.get("risk_flag_high_value"):  score += 40
    if row.get("risk_flag_contract"):    score += 20
    if row.get("is_suspicious_basic"):   score += 30
    return min(score, 100)


def _risk_label(score: int) -> str:
    if score >= 70: return "High"
    if score >= 40: return "Medium"
    return "Low"


def _map_mysql_tx(row: dict) -> dict:
    """Map a MySQL transactions row → frontend format."""
    amount = _to_float(row.get("value_eth"))
    score  = _risk_score(row)
    return {
        "hash":        row.get("tx_hash", ""),
        "sender":      (row.get("from_address") or "").lower(),
        "receiver":    (row.get("to_address") or "Contract Creation").lower(),
        "amount":      f"{amount:.6f}",
        "timestamp":   _fmt_ts(row.get("timestamp")),
        "blockNumber": str(row.get("block_number") or ""),
        "riskScore":   score,
        "riskLabel":   _risk_label(score),
        "txType":      row.get("tx_type", ""),
        "isContractCall": bool(row.get("is_contract_call")),
    }


def _map_mongo_processed(tx: dict) -> dict:
    amount = _to_float(tx.get("value_eth"))
    score  = 0
    if tx.get("risk_flag_high_value"):  score += 40
    if tx.get("risk_flag_contract"):    score += 20
    if tx.get("is_suspicious_basic"):   score += 30
    score = min(score, 100)
    return {
        "hash":        tx.get("tx_hash", ""),
        "sender":      (tx.get("from_address") or "").lower(),
        "receiver":    (tx.get("to_address") or "Contract Creation").lower(),
        "amount":      f"{amount:.6f}",
        "timestamp":   _fmt_ts(tx.get("timestamp")),
        "blockNumber": str(tx.get("block_number") or ""),
        "riskScore":   score,
        "riskLabel":   _risk_label(score),
    }


# ── /refresh ──────────────────────────────────────────────────────────────────

@router.post("/refresh")
async def refresh_transactions():
    """Fetch the latest Ethereum block, save to MongoDB, return results."""
    db = get_db()
    try:
        block = await rpc("eth_getBlockByNumber", ["latest", True])
        if not block:
            raise ValueError("Empty block response")

        ts = datetime.fromtimestamp(
            int(block["timestamp"], 16), tz=timezone.utc
        ).strftime("%m/%d/%Y, %I:%M:%S %p")

        freq: dict[str, int] = {}
        for tx in block["transactions"]:
            freq[tx["from"]] = freq.get(tx["from"], 0) + 1

        results = []
        for tx in block["transactions"]:
            amount   = int(tx["value"], 16) / 1e18
            receiver = tx.get("to") or "Contract Creation"
            score    = min(
                (30 if amount >= 10 else 15 if amount >= 1 else 5 if amount >= 0.1 else 0) +
                (20 if receiver == "Contract Creation" else 0) +
                (50 if freq.get(tx["from"], 1) >= 10 else 30 if freq.get(tx["from"], 1) >= 5 else 0),
                100
            )
            doc = {
                "hash":        tx["hash"],
                "sender":      tx["from"],
                "receiver":    receiver,
                "amount":      f"{amount:.6f}",
                "timestamp":   ts,
                "blockNumber": block["number"],
                "riskScore":   score,
                "riskLabel":   _risk_label(score),
            }
            await db.transactions.update_one(
                {"hash": doc["hash"]}, {"$set": doc}, upsert=True
            )
            results.append(doc)
        return results
    except Exception as e:
        print(f"Error in refresh_transactions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── GET / ─────────────────────────────────────────────────────────────────────

@router.get("/")
async def get_transactions():
    """
    Return latest 200 transactions.
    Priority: MySQL → MongoDB processed → MongoDB raw
    """
    # 1. MySQL (primary — populated by AML ETL pipeline)
    if get_pool():
        try:
            rows = await fetch_all(
                "SELECT * FROM transactions ORDER BY block_number DESC LIMIT 200"
            )
            if rows:
                return [_map_mysql_tx(r) for r in rows]
        except Exception as e:
            print(f"MySQL read failed, falling back: {e}")

    # 2. MongoDB fallback
    db = get_db()
    try:
        processed = await db.processed_transactions.find(
            {}, {"_id": 0}
        ).sort("_id", -1).limit(200).to_list(200)
        if processed:
            return [_map_mongo_processed(tx) for tx in processed]

        own = await db.transactions.find(
            {}, {"_id": 0}
        ).sort("_id", -1).limit(200).to_list(200)
        if own:
            return own
    except Exception as e:
        print(f"MongoDB fallback failed: {e}")

    return []


# ── GET /graph ────────────────────────────────────────────────────────────────

@router.get("/graph")
async def get_graph(search: str = ""):
    """
    Return graph edges for visualization.
    Priority: Neo4j → MySQL graph_edges → MongoDB
    """
    driver = get_driver()

    # ── SEARCH MODE ──────────────────────────────────────────────────────────
    if search:
        term = search.strip().lower()

        # 1. Neo4j search
        if driver:
            try:
                async with driver.session() as session:
                    result = await session.run(
                        """
                        MATCH (s:Address)-[rel:TRANSFER]->(r:Address)
                        WHERE toLower(s.address) CONTAINS $term
                           OR toLower(r.address) CONTAINS $term
                        RETURN s.address AS sender, r.address AS receiver,
                               rel.tx_hash AS hash,
                               COALESCE(rel.value_eth, rel.amount) AS amount,
                               rel.timestamp AS timestamp
                        LIMIT 300
                        """,
                        term=term
                    )
                    edges = [
                        {
                            "sender":    r["sender"],
                            "receiver":  r["receiver"],
                            "hash":      r["hash"] or "",
                            "amount":    str(r["amount"] or "0"),
                            "timestamp": str(r["timestamp"] or ""),
                        }
                        async for r in result
                    ]
                    if edges:
                        return edges
            except Exception as e:
                print(f"Neo4j search failed: {e}")

        # 2. MySQL graph_edges search
        if get_pool():
            try:
                rows = await fetch_all(
                    """SELECT tx_hash, from_address, to_address, value_eth, timestamp
                       FROM graph_edges
                       WHERE from_address LIKE %s OR to_address LIKE %s
                       LIMIT 300""",
                    (f"%{term}%", f"%{term}%")
                )
                if rows:
                    return [
                        {
                            "sender":    (r["from_address"] or "").lower(),
                            "receiver":  (r["to_address"] or "").lower(),
                            "hash":      r["tx_hash"] or "",
                            "amount":    f"{_to_float(r['value_eth']):.6f}",
                            "timestamp": _fmt_ts(r.get("timestamp")),
                        }
                        for r in rows if r.get("to_address")
                    ]
            except Exception as e:
                print(f"MySQL graph search failed: {e}")

        # 3. MongoDB fallback
        db = get_db()
        try:
            proc = await db.processed_transactions.find(
                {"$or": [
                    {"from_address": {"$regex": term, "$options": "i"}},
                    {"to_address":   {"$regex": term, "$options": "i"}},
                ]},
                {"_id": 0, "from_address": 1, "to_address": 1,
                 "tx_hash": 1, "value_eth": 1, "timestamp": 1}
            ).to_list(300)
            if proc:
                return [
                    {
                        "sender":    (tx.get("from_address") or "").lower(),
                        "receiver":  (tx.get("to_address") or "").lower(),
                        "hash":      tx.get("tx_hash", ""),
                        "amount":    f"{_to_float(tx.get('value_eth')):.6f}",
                        "timestamp": _fmt_ts(tx.get("timestamp")),
                    }
                    for tx in proc if tx.get("to_address")
                ]
        except Exception as e:
            print(f"MongoDB graph search failed: {e}")

        return []

    # ── DEFAULT MODE: latest block ────────────────────────────────────────────

    # 1. Get latest block number from MySQL
    block_number = None
    if get_pool():
        try:
            row = await fetch_one(
                "SELECT block_number FROM graph_edges ORDER BY block_number DESC LIMIT 1"
            )
            if row:
                block_number = str(row["block_number"])
        except Exception as e:
            print(f"MySQL block lookup failed: {e}")

    # 2. Query Neo4j for that block
    if driver and block_number:
        try:
            async with driver.session() as session:
                result = await session.run(
                    """
                    MATCH (s:Address)-[rel:TRANSFER]->(r:Address)
                    WHERE rel.block_number = $bn OR rel.blockNumber = $bn
                    RETURN s.address AS sender, r.address AS receiver,
                           rel.tx_hash AS hash,
                           COALESCE(rel.value_eth, rel.amount) AS amount,
                           rel.timestamp AS timestamp
                    LIMIT 500
                    """,
                    bn=block_number
                )
                edges = [
                    {
                        "sender":    r["sender"],
                        "receiver":  r["receiver"],
                        "hash":      r["hash"] or "",
                        "amount":    str(r["amount"] or "0"),
                        "timestamp": str(r["timestamp"] or ""),
                    }
                    async for r in result
                ]
                if edges:
                    return edges
        except Exception as e:
            print(f"Neo4j graph query failed: {e}")

    # 3. MySQL graph_edges fallback
    if get_pool() and block_number:
        try:
            rows = await fetch_all(
                """SELECT tx_hash, from_address, to_address, value_eth, timestamp
                   FROM graph_edges
                   WHERE block_number = %s AND to_address IS NOT NULL
                   LIMIT 500""",
                (block_number,)
            )
            if rows:
                return [
                    {
                        "sender":    (r["from_address"] or "").lower(),
                        "receiver":  (r["to_address"] or "").lower(),
                        "hash":      r["tx_hash"] or "",
                        "amount":    f"{_to_float(r['value_eth']):.6f}",
                        "timestamp": _fmt_ts(r.get("timestamp")),
                    }
                    for r in rows
                ]
        except Exception as e:
            print(f"MySQL graph_edges fallback failed: {e}")

    return []


# ── GET /alerts ───────────────────────────────────────────────────────────────

@router.get("/alerts")
async def get_alerts():
    """Return flagged transactions from MySQL with AML cluster labels."""
    rows = []

    # 1. MySQL
    if get_pool():
        try:
            rows = await fetch_all(
                """SELECT * FROM transactions
                   WHERE risk_flag_high_value = 1
                      OR risk_flag_contract = 1
                      OR is_suspicious_basic = 1
                   ORDER BY block_number DESC
                   LIMIT 1000"""
            )
        except Exception as e:
            print(f"MySQL alerts failed: {e}")

    # 2. MongoDB fallback
    if not rows:
        db = get_db()
        try:
            mongo_rows = await db.processed_transactions.find(
                {}, {"_id": 0}
            ).sort("_id", -1).limit(1000).to_list(1000)
            rows = mongo_rows
        except Exception as e:
            print(f"MongoDB alerts fallback failed: {e}")

    if not rows:
        return []

    # Compute sender frequency for velocity/fan-out detection
    sender_counts: dict[str, int] = {}
    sender_receivers: dict[str, set] = {}
    for tx in rows:
        sender   = (tx.get("from_address") or tx.get("sender") or "").lower()
        receiver = (tx.get("to_address") or tx.get("receiver") or "").lower()
        if sender:
            sender_counts[sender] = sender_counts.get(sender, 0) + 1
            sender_receivers.setdefault(sender, set())
            if receiver:
                sender_receivers[sender].add(receiver)

    alerts = []
    for tx in rows:
        sender   = (tx.get("from_address") or tx.get("sender") or "").lower()
        receiver = (tx.get("to_address") or tx.get("receiver") or "Contract Creation").lower()
        amount   = _to_float(tx.get("value_eth") or tx.get("amount"))
        tx_hash  = tx.get("tx_hash") or tx.get("hash") or ""
        block_number = str(tx.get("block_number") or tx.get("blockNumber") or "")

        is_high_value = bool(tx.get("risk_flag_high_value")) or amount >= 10.0
        is_contract   = bool(tx.get("risk_flag_contract") or tx.get("is_contract_call"))
        is_suspicious = bool(tx.get("is_suspicious_basic"))
        velocity      = sender_counts.get(sender, 0)
        unique_recv   = len(sender_receivers.get(sender, set()))

        reasons = []
        if velocity >= 6:      reasons.append("high_velocity")
        if unique_recv >= 5:   reasons.append("fan_out")
        if is_high_value:      reasons.append("high_value")
        if is_contract:        reasons.append("contract_call")
        if is_suspicious:      reasons.append("suspicious_basic")

        if not reasons:
            continue

        flags = len(reasons)
        if flags >= 2:
            cluster_name = "Multi-Signal"
        elif "high_velocity" in reasons:
            cluster_name = "High Velocity"
        elif "fan_out" in reasons:
            cluster_name = "Fan-Out"
        elif "high_value" in reasons:
            cluster_name = "High Value"
        elif "contract_call" in reasons:
            cluster_name = "Contract Call"
        else:
            cluster_name = "New Counterparty + High Value"

        score = min(
            (40 if is_high_value else 0) + (20 if is_contract else 0) +
            (15 if velocity >= 6 else 0) + (20 if unique_recv >= 5 else 0) +
            (10 if is_suspicious else 0) + (10 if flags >= 2 else 0),
            100
        )

        alerts.append({
            "hash":        tx_hash,
            "sender":      sender,
            "receiver":    receiver,
            "amount":      f"{amount:.6f}",
            "timestamp":   _fmt_ts(tx.get("timestamp")),
            "blockNumber": block_number,
            "riskScore":   score,
            "riskLabel":   _risk_label(score),
            "clusterName": cluster_name,
            "reasons":     reasons,
        })

    alerts.sort(key=lambda x: x["riskScore"], reverse=True)
    return alerts[:200]


# ── GET /analytics ────────────────────────────────────────────────────────────

@router.get("/analytics")
async def get_analytics():
    """Return aggregated analytics from MySQL."""
    rows = []

    if get_pool():
        try:
            rows = await fetch_all("SELECT * FROM transactions LIMIT 5000")
        except Exception as e:
            print(f"MySQL analytics failed: {e}")

    if not rows:
        db = get_db()
        try:
            rows = await db.processed_transactions.find(
                {}, {"_id": 0}
            ).to_list(5000)
        except Exception as e:
            print(f"MongoDB analytics fallback failed: {e}")

    if not rows:
        return {
            "riskDistribution": [], "topSenders": [],
            "amountBuckets": [], "totalTransactions": 0,
            "totalFlagged": 0, "totalEth": 0,
        }

    sender_counts: dict[str, int] = {}
    sender_receivers: dict[str, set] = {}
    for tx in rows:
        sender   = (tx.get("from_address") or tx.get("sender") or "").lower()
        receiver = (tx.get("to_address") or tx.get("receiver") or "").lower()
        if sender:
            sender_counts[sender] = sender_counts.get(sender, 0) + 1
            sender_receivers.setdefault(sender, set())
            if receiver:
                sender_receivers[sender].add(receiver)

    risk_counts    = {"Low": 0, "Medium": 0, "High": 0}
    amount_buckets = {"0-0.1": 0, "0.1-1": 0, "1-10": 0, "10+": 0}
    total_eth      = 0.0
    flagged        = 0

    for tx in rows:
        sender   = (tx.get("from_address") or tx.get("sender") or "").lower()
        amount   = _to_float(tx.get("value_eth") or tx.get("amount"))
        is_high  = bool(tx.get("risk_flag_high_value")) or amount >= 10.0
        is_cont  = bool(tx.get("risk_flag_contract") or tx.get("is_contract_call"))
        is_susp  = bool(tx.get("is_suspicious_basic"))
        velocity = sender_counts.get(sender, 0)
        unique_r = len(sender_receivers.get(sender, set()))

        total_eth += amount

        if amount < 0.1:   amount_buckets["0-0.1"] += 1
        elif amount < 1:   amount_buckets["0.1-1"] += 1
        elif amount < 10:  amount_buckets["1-10"]  += 1
        else:              amount_buckets["10+"]   += 1

        score = min(
            (40 if is_high else 0) + (20 if is_cont else 0) +
            (15 if velocity >= 6 else 0) + (20 if unique_r >= 5 else 0) +
            (10 if is_susp else 0), 100
        )
        if score >= 70:
            risk_counts["High"] += 1; flagged += 1
        elif score >= 40:
            risk_counts["Medium"] += 1; flagged += 1
        else:
            risk_counts["Low"] += 1

    top_senders = sorted(sender_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "riskDistribution": [{"name": k, "value": v} for k, v in risk_counts.items()],
        "topSenders": [
            {"address": f"{a[:8]}...{a[-4:]}", "full": a, "count": c}
            for a, c in top_senders
        ],
        "amountBuckets": [{"range": k, "count": v} for k, v in amount_buckets.items()],
        "totalTransactions": len(rows),
        "totalFlagged": flagged,
        "totalEth": round(total_eth, 4),
    }
