import os
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
import httpx
from db.mongo import get_db
from db.neo4j import get_driver

router = APIRouter()
NODE_URL = "https://ethereum-rpc.publicnode.com"

# Cluster name mapping (mirrors clustering.py)
CLUSTER_NAMES = {
    0: "Normal",
    1: "High Velocity",
    2: "Fan-Out",
    3: "High Value",
    4: "Contract Call",
    5: "New Counterparty + High Value",
    6: "Multi-Signal",
}

# ── helpers ──────────────────────────────────────────────────────────────────

async def rpc(method: str, params: list = []):
    async with httpx.AsyncClient() as client:
        r = await client.post(NODE_URL, json={
            "jsonrpc": "2.0", "id": 1, "method": method, "params": params
        }, timeout=15)
        return r.json().get("result")

def calc_risk_score(amount: float, receiver: str, sender_freq: int) -> int:
    score = 0
    if sender_freq >= 10:   score += 50
    elif sender_freq >= 5:  score += 30
    elif sender_freq >= 3:  score += 15
    if amount >= 10:        score += 30
    elif amount >= 1:       score += 15
    elif amount >= 0.1:     score += 5
    if receiver == "Contract Creation": score += 20
    return min(score, 100)

def get_risk_label(score: int) -> str:
    if score >= 70: return "High"
    if score >= 40: return "Medium"
    return "Low"

def _to_float(value) -> float:
    """Safely convert Decimal128, string, int, or float to float."""
    if value is None:
        return 0.0
    # Handle MongoDB Decimal128
    type_name = type(value).__name__
    if type_name == 'Decimal128':
        return float(value.to_decimal())
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

def map_raw_tx(tx_doc: dict, sender_freq: int = 1) -> dict:
    """Map AML pipeline raw_transaction document → frontend-friendly format."""
    block = tx_doc.get("block", {})
    address_pair = tx_doc.get("address_pair", {})
    value = tx_doc.get("value", {})

    sender = (address_pair.get("from") or "").lower()
    receiver = (address_pair.get("to") or "Contract Creation").lower()
    amount = _to_float(value.get("eth"))

    # Use AML pipeline risk flags if available, else calculate
    risk_flag_high = bool(tx_doc.get("metadata", {}).get("risk_level") == "high")
    score = calc_risk_score(amount, receiver, sender_freq)
    if risk_flag_high:
        score = max(score, 70)
    label = get_risk_label(score)

    ts_raw = block.get("timestamp")
    if isinstance(ts_raw, (int, float)):
        ts = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc).strftime("%m/%d/%Y, %I:%M:%S %p")
    elif isinstance(ts_raw, datetime):
        ts = ts_raw.strftime("%m/%d/%Y, %I:%M:%S %p")
    else:
        ts = str(ts_raw or "")

    return {
        "hash":        tx_doc.get("tx_hash") or str(tx_doc.get("_id", "")),
        "sender":      sender,
        "receiver":    receiver,
        "amount":      f"{amount:.6f}",
        "timestamp":   ts,
        "blockNumber": str(block.get("number") or ""),
        "riskScore":   score,
        "riskLabel":   label,
    }

def map_processed_tx(tx_doc: dict) -> dict:
    """Map AML pipeline processed_transaction document → frontend-friendly format."""
    sender = (tx_doc.get("from_address") or "").lower()
    receiver = (tx_doc.get("to_address") or "Contract Creation").lower()
    amount = _to_float(tx_doc.get("value_eth"))

    risk_high = bool(tx_doc.get("risk_flag_high_value"))
    risk_contract = bool(tx_doc.get("risk_flag_contract"))
    score = 0
    if risk_high:    score += 40
    if risk_contract: score += 20
    if tx_doc.get("is_suspicious_basic"): score += 30
    score = min(score, 100)
    label = get_risk_label(score)

    ts_raw = tx_doc.get("timestamp")
    if isinstance(ts_raw, datetime):
        ts = ts_raw.strftime("%m/%d/%Y, %I:%M:%S %p")
    else:
        ts = str(ts_raw or "")

    return {
        "hash":        tx_doc.get("tx_hash", ""),
        "sender":      sender,
        "receiver":    receiver,
        "amount":      f"{amount:.6f}",
        "timestamp":   ts,
        "blockNumber": str(tx_doc.get("block_number") or ""),
        "riskScore":   score,
        "riskLabel":   label,
    }

async def sync_to_neo4j(tx: dict):
    """Sync a transaction to Neo4j using Address/TRANSFER schema."""
    driver = get_driver()
    if not driver:
        return
    async with driver.session() as session:
        await session.run(
            """
            MERGE (s:Address {address: $sender})
            MERGE (r:Address {address: $receiver})
            MERGE (s)-[rel:TRANSFER {hash: $hash}]->(r)
            ON CREATE SET rel.amount = $amount,
                          rel.timestamp = $timestamp,
                          rel.blockNumber = $blockNumber
            """,
            sender=tx["sender"], receiver=tx["receiver"],
            hash=tx["hash"], amount=tx["amount"],
            timestamp=tx["timestamp"], blockNumber=tx["blockNumber"]
        )

# ── routes ───────────────────────────────────────────────────────────────────

async def _fetch_and_save_latest_block(db) -> list:
    """Fetch the latest Ethereum block, save to MongoDB + Neo4j, return mapped results."""
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
        amount = int(tx["value"], 16) / 1e18
        receiver = tx.get("to") or "Contract Creation"
        score = calc_risk_score(amount, receiver, freq.get(tx["from"], 1))
        label = get_risk_label(score)
        doc = {
            "hash":        tx["hash"],
            "sender":      tx["from"],
            "receiver":    receiver,
            "amount":      f"{amount:.6f}",
            "timestamp":   ts,
            "blockNumber": block["number"],
            "riskScore":   score,
            "riskLabel":   label,
        }
        # Save to our own transactions collection
        await db.transactions.update_one(
            {"hash": doc["hash"]}, {"$set": doc}, upsert=True
        )
        if tx.get("to"):
            try: await sync_to_neo4j(doc)
            except Exception: pass
        results.append(doc)
    return results


@router.post("/refresh")
async def refresh_transactions():
    """Force-fetch the latest Ethereum block and return fresh data."""
    db = get_db()
    try:
        results = await _fetch_and_save_latest_block(db)
        return results
    except Exception as e:
        print(f"Error in refresh_transactions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def get_transactions():
    db = get_db()
    try:
        # 1. Try our own transactions collection (written by refresh)
        own = await db.transactions.find(
            {}, {"_id": 0}
        ).sort("_id", -1).limit(200).to_list(200)
        if own:
            return own

        # 2. Try AML pipeline's processed_transactions
        processed = await db.processed_transactions.find(
            {}, {"_id": 0}
        ).sort("_id", -1).limit(200).to_list(200)
        if processed:
            return [map_processed_tx(tx) for tx in processed]

        # 3. Fall back to raw_transactions from the pipeline
        raw = await db.raw_transactions.find(
            {}, {}
        ).sort("_id", -1).limit(200).to_list(200)
        if raw:
            return [map_raw_tx(tx) for tx in raw]

        # 4. Last resort: fetch live
        results = await _fetch_and_save_latest_block(db)
        return results

    except Exception as e:
        print(f"Error in get_transactions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph")
async def get_graph(search: str = ""):
    db = get_db()
    driver = get_driver()
    try:
        # ── SEARCH MODE: find this address across ALL data ──────────────────
        if search:
            term = search.strip().lower()

            # 1. Search Neo4j for all edges involving this address
            if driver:
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

            # 2. Search our own transactions collection
            own = await db.transactions.find(
                {"$or": [
                    {"sender":   {"$regex": term, "$options": "i"}},
                    {"receiver": {"$regex": term, "$options": "i"}},
                ]},
                {"_id": 0, "sender": 1, "receiver": 1,
                 "hash": 1, "amount": 1, "timestamp": 1}
            ).to_list(300)
            if own:
                return [tx for tx in own if tx.get("receiver") != "Contract Creation"]

            # 3. Search processed_transactions
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
                        "timestamp": str(tx.get("timestamp") or ""),
                    }
                    for tx in proc if tx.get("to_address")
                ]

            return []  # address not found anywhere

        # ── DEFAULT MODE: show latest block graph ────────────────────────────
        # Find latest block number
        latest_own = await db.transactions.find_one({}, {"blockNumber": 1}, sort=[("_id", -1)])
        latest_proc = await db.processed_transactions.find_one({}, {"block_number": 1}, sort=[("_id", -1)])

        block_number = None
        use_own = False
        if latest_own:
            block_number = latest_own.get("blockNumber")
            use_own = True
        elif latest_proc:
            block_number = latest_proc.get("block_number")

        if not block_number:
            return []

        # Query Neo4j for that block
        if driver:
            async with driver.session() as session:
                result = await session.run(
                    """
                    MATCH (s:Address)-[rel:TRANSFER]->(r:Address)
                    WHERE rel.blockNumber = $blockNumber
                       OR rel.block_number = $blockNumber
                    RETURN s.address AS sender, r.address AS receiver,
                           rel.tx_hash AS hash,
                           COALESCE(rel.value_eth, rel.amount) AS amount,
                           rel.timestamp AS timestamp
                    LIMIT 300
                    """,
                    blockNumber=str(block_number)
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

        # Fallback to MongoDB
        if use_own:
            txs = await db.transactions.find(
                {"blockNumber": block_number,
                 "receiver": {"$ne": "Contract Creation"}},
                {"_id": 0, "sender": 1, "receiver": 1,
                 "hash": 1, "amount": 1, "timestamp": 1}
            ).to_list(500)
            return txs
        else:
            txs = await db.processed_transactions.find(
                {"block_number": block_number,
                 "to_address": {"$ne": None, "$exists": True}},
                {"_id": 0, "from_address": 1, "to_address": 1,
                 "tx_hash": 1, "value_eth": 1, "timestamp": 1}
            ).to_list(500)
            return [
                {
                    "sender":    (tx.get("from_address") or "").lower(),
                    "receiver":  (tx.get("to_address") or "").lower(),
                    "hash":      tx.get("tx_hash", ""),
                    "amount":    f"{_to_float(tx.get('value_eth')):.6f}",
                    "timestamp": str(tx.get("timestamp") or ""),
                }
                for tx in txs
            ]

    except Exception as e:
        print(f"Error in get_graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_alerts():
    """
    Return flagged transactions with cluster labels and risk scores.
    Builds alerts on-the-fly from processed_transactions using heuristic rules.
    """
    db = get_db()
    try:
        # Pull processed transactions — these have risk flags from the AML pipeline
        txs = await db.processed_transactions.find(
            {}, {"_id": 0}
        ).sort("_id", -1).limit(1000).to_list(1000)

        if not txs:
            # Fall back to our own transactions collection
            txs = await db.transactions.find(
                {}, {"_id": 0}
            ).sort("_id", -1).limit(1000).to_list(1000)

        alerts = []
        # Count sender frequency for velocity detection
        sender_counts: dict[str, int] = {}
        sender_receivers: dict[str, set] = {}

        for tx in txs:
            sender = (tx.get("from_address") or tx.get("sender") or "").lower()
            receiver = (tx.get("to_address") or tx.get("receiver") or "").lower()
            if sender:
                sender_counts[sender] = sender_counts.get(sender, 0) + 1
                if sender not in sender_receivers:
                    sender_receivers[sender] = set()
                if receiver:
                    sender_receivers[sender].add(receiver)

        for tx in txs:
            sender   = (tx.get("from_address") or tx.get("sender") or "").lower()
            receiver = (tx.get("to_address") or tx.get("receiver") or "").lower()
            amount   = _to_float(tx.get("value_eth") or tx.get("amount"))
            tx_hash  = tx.get("tx_hash") or tx.get("hash") or ""
            timestamp = str(tx.get("timestamp") or "")
            block_number = str(tx.get("block_number") or tx.get("blockNumber") or "")

            is_high_value    = bool(tx.get("risk_flag_high_value")) or amount >= 10.0
            is_contract      = bool(tx.get("risk_flag_contract") or tx.get("is_contract_call"))
            is_suspicious    = bool(tx.get("is_suspicious_basic"))
            velocity         = sender_counts.get(sender, 0)
            unique_receivers = len(sender_receivers.get(sender, set()))

            # Determine cluster
            flags = 0
            reasons = []

            if velocity >= 6:
                flags += 1
                reasons.append("high_velocity")
            if unique_receivers >= 5:
                flags += 1
                reasons.append("fan_out")
            if is_high_value:
                flags += 1
                reasons.append("high_value")
            if is_contract:
                flags += 1
                reasons.append("contract_call")
            if is_suspicious:
                flags += 1
                reasons.append("suspicious_basic")

            if flags == 0:
                continue  # skip normal transactions

            if flags >= 2:
                cluster_id = 6
                cluster_name = "Multi-Signal"
            elif "high_velocity" in reasons:
                cluster_id, cluster_name = 1, "High Velocity"
            elif "fan_out" in reasons:
                cluster_id, cluster_name = 2, "Fan-Out"
            elif "high_value" in reasons:
                cluster_id, cluster_name = 3, "High Value"
            elif "contract_call" in reasons:
                cluster_id, cluster_name = 4, "Contract Call"
            else:
                cluster_id, cluster_name = 5, "New Counterparty + High Value"

            # Risk score
            score = min(
                (40 if is_high_value else 0) +
                (20 if is_contract else 0) +
                (15 if velocity >= 6 else 0) +
                (20 if unique_receivers >= 5 else 0) +
                (10 if is_suspicious else 0) +
                (10 if flags >= 2 else 0),
                100
            )

            alerts.append({
                "hash":         tx_hash,
                "sender":       sender,
                "receiver":     receiver,
                "amount":       f"{amount:.6f}",
                "timestamp":    timestamp,
                "blockNumber":  block_number,
                "riskScore":    score,
                "riskLabel":    "High" if score >= 70 else "Medium" if score >= 40 else "Low",
                "clusterLabel": cluster_id,
                "clusterName":  cluster_name,
                "reasons":      reasons,
            })

        # Sort by risk score descending
        alerts.sort(key=lambda x: x["riskScore"], reverse=True)
        return alerts[:200]

    except Exception as e:
        print(f"Error in get_alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics")
async def get_analytics():
    """Return aggregated analytics data for charts."""
    db = get_db()
    try:
        # Pull from processed_transactions first, fall back to own transactions
        txs = await db.processed_transactions.find({}, {"_id": 0}).to_list(5000)
        if not txs:
            txs = await db.transactions.find({}, {"_id": 0}).to_list(5000)

        if not txs:
            return {
                "riskDistribution": [],
                "clusterBreakdown": [],
                "topSenders": [],
                "amountBuckets": [],
                "totalTransactions": 0,
                "totalFlagged": 0,
                "totalEth": 0,
            }

        # Compute sender frequency and unique receivers
        sender_counts: dict[str, int] = {}
        sender_receivers: dict[str, set] = {}
        for tx in txs:
            sender = (tx.get("from_address") or tx.get("sender") or "").lower()
            receiver = (tx.get("to_address") or tx.get("receiver") or "").lower()
            if sender:
                sender_counts[sender] = sender_counts.get(sender, 0) + 1
                sender_receivers.setdefault(sender, set())
                if receiver:
                    sender_receivers[sender].add(receiver)

        risk_counts = {"Low": 0, "Medium": 0, "High": 0}
        cluster_counts: dict[str, int] = {}
        total_eth = 0.0
        amount_buckets = {"0-0.1": 0, "0.1-1": 0, "1-10": 0, "10+": 0}
        flagged = 0

        for tx in txs:
            sender   = (tx.get("from_address") or tx.get("sender") or "").lower()
            amount   = _to_float(tx.get("value_eth") or tx.get("amount"))
            is_high  = bool(tx.get("risk_flag_high_value")) or amount >= 10.0
            is_cont  = bool(tx.get("risk_flag_contract") or tx.get("is_contract_call"))
            is_susp  = bool(tx.get("is_suspicious_basic"))
            velocity = sender_counts.get(sender, 0)
            unique_r = len(sender_receivers.get(sender, set()))

            total_eth += amount

            # Amount buckets
            if amount < 0.1:
                amount_buckets["0-0.1"] += 1
            elif amount < 1:
                amount_buckets["0.1-1"] += 1
            elif amount < 10:
                amount_buckets["1-10"] += 1
            else:
                amount_buckets["10+"] += 1

            # Cluster
            flags = sum([
                velocity >= 6,
                unique_r >= 5,
                is_high,
                is_cont,
                is_susp,
            ])
            if flags >= 2:
                cluster = "Multi-Signal"
            elif velocity >= 6:
                cluster = "High Velocity"
            elif unique_r >= 5:
                cluster = "Fan-Out"
            elif is_high:
                cluster = "High Value"
            elif is_cont:
                cluster = "Contract Call"
            elif is_susp:
                cluster = "Suspicious"
            else:
                cluster = "Normal"

            cluster_counts[cluster] = cluster_counts.get(cluster, 0) + 1

            # Risk score
            score = min(
                (40 if is_high else 0) + (20 if is_cont else 0) +
                (15 if velocity >= 6 else 0) + (20 if unique_r >= 5 else 0) +
                (10 if is_susp else 0), 100
            )
            if score >= 70:
                risk_counts["High"] += 1
                flagged += 1
            elif score >= 40:
                risk_counts["Medium"] += 1
                flagged += 1
            else:
                risk_counts["Low"] += 1

        # Top 10 senders by tx count
        top_senders = sorted(sender_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "riskDistribution": [
                {"name": k, "value": v} for k, v in risk_counts.items()
            ],
            "clusterBreakdown": [
                {"name": k, "value": v}
                for k, v in sorted(cluster_counts.items(), key=lambda x: x[1], reverse=True)
                if k != "Normal"
            ],
            "topSenders": [
                {"address": f"{a[:8]}...{a[-4:]}", "full": a, "count": c}
                for a, c in top_senders
            ],
            "amountBuckets": [
                {"range": k, "count": v} for k, v in amount_buckets.items()
            ],
            "totalTransactions": len(txs),
            "totalFlagged": flagged,
            "totalEth": round(total_eth, 4),
        }

    except Exception as e:
        print(f"Error in get_analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
