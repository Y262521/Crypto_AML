from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from blockchain_engine.models import NormalizedTransaction


class SqliteIndexer:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "blockchain_index.db"
        self._initialize()

    def _initialize(self) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("PRAGMA temp_store=MEMORY")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS normalized_transactions (
                    chain TEXT NOT NULL,
                    tx_hash TEXT NOT NULL,
                    block_number INTEGER,
                    timestamp TEXT NOT NULL,
                    from_address TEXT NOT NULL,
                    to_address TEXT,
                    value REAL NOT NULL,
                    asset TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    tx_type TEXT NOT NULL DEFAULT 'transfer',
                    method_id TEXT,
                    token_contract TEXT,
                    token_symbol TEXT,
                    raw_json TEXT NOT NULL,
                    PRIMARY KEY (chain, tx_hash)
                )
                """
            )
            # Migration: add tx_type if missing
            try:
                connection.execute("ALTER TABLE normalized_transactions ADD COLUMN tx_type TEXT NOT NULL DEFAULT 'transfer'")
            except sqlite3.OperationalError:
                # Column already exists
                pass
            
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_normalized_transactions_timestamp
                ON normalized_transactions (timestamp DESC)
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_normalized_transactions_address
                ON normalized_transactions (chain, from_address, to_address)
                """
            )

    def append(self, transactions: list[NormalizedTransaction]) -> None:
        if not transactions:
            return
        with sqlite3.connect(self.db_path) as connection:
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.executemany(
                """
                INSERT OR REPLACE INTO normalized_transactions (
                    chain,
                    tx_hash,
                    block_number,
                    timestamp,
                    from_address,
                    to_address,
                    value,
                    asset,
                    direction,
                    tx_type,
                    method_id,
                    token_contract,
                    token_symbol,
                    raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        tx.chain,
                        tx.tx_hash,
                        tx.block_number,
                        tx.timestamp.isoformat(),
                        tx.from_address,
                        tx.to_address,
                        tx.value,
                        tx.asset,
                        tx.direction,
                        tx.tx_type,
                        tx.method_id,
                        tx.token_contract,
                        tx.token_symbol,
                        json.dumps(tx.raw, default=str),
                    )
                    for tx in transactions
                ],
            )

    def read_all(self, limit: int | None = None) -> list[dict]:
        with sqlite3.connect(self.db_path) as connection:
            query = """
                SELECT
                    chain,
                    tx_hash,
                    block_number,
                    timestamp,
                    from_address,
                    to_address,
                    value,
                    asset,
                    direction,
                    method_id,
                    token_contract,
                    token_symbol,
                    raw_json
                FROM normalized_transactions
                ORDER BY timestamp DESC
                """
            params: tuple[int, ...] = ()
            if limit is not None:
                query += " LIMIT ?"
                params = (limit,)
            cursor = connection.execute(
                query,
                params,
            )
            rows = cursor.fetchall()

        return [
            {
                "chain": row[0],
                "tx_hash": row[1],
                "block_number": row[2],
                "timestamp": row[3],
                "from_address": row[4],
                "to_address": row[5],
                "value": row[6],
                "asset": row[7],
                "direction": row[8],
                "method_id": row[9],
                "token_contract": row[10],
                "token_symbol": row[11],
                "raw": json.loads(row[12]),
            }
            for row in rows
        ]

    def get_address_stats(self, chain: str, address: str) -> dict[str, Any]:
        lower_address = address.lower()
        with sqlite3.connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                SELECT 
                    SUM(CASE WHEN LOWER(to_address) = ? THEN value ELSE 0 END) as incoming,
                    SUM(CASE WHEN LOWER(from_address) = ? THEN value ELSE 0 END) as outgoing,
                    COUNT(*) as tx_count
                FROM normalized_transactions
                WHERE chain = ?
                  AND (LOWER(from_address) = ? OR LOWER(COALESCE(to_address, '')) = ?)
                """,
                (lower_address, lower_address, chain, lower_address, lower_address),
            )
            row = cursor.fetchone()
        
        return {
            "incoming_total": row[0] or 0.0,
            "outgoing_total": row[1] or 0.0,
            "transaction_count": row[2] or 0,
        }

    def read_by_tx_hash(self, tx_hash: str) -> dict | None:
        with sqlite3.connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                SELECT
                    chain,
                    tx_hash,
                    block_number,
                    timestamp,
                    from_address,
                    to_address,
                    value,
                    asset,
                    direction,
                    method_id,
                    token_contract,
                    token_symbol,
                    raw_json
                FROM normalized_transactions
                WHERE tx_hash = ?
                LIMIT 1
                """,
                (tx_hash,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return {
            "chain": row[0],
            "tx_hash": row[1],
            "block_number": row[2],
            "timestamp": row[3],
            "from_address": row[4],
            "to_address": row[5],
            "value": row[6],
            "asset": row[7],
            "direction": row[8],
            "method_id": row[9],
            "token_contract": row[10],
            "token_symbol": row[11],
            "raw": json.loads(row[12]),
        }

    def read_by_address(self, chain: str, address: str, limit: int = 25) -> list[dict]:
        lower_address = address.lower()
        with sqlite3.connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                SELECT
                    chain,
                    tx_hash,
                    block_number,
                    timestamp,
                    from_address,
                    to_address,
                    value,
                    asset,
                    direction,
                    method_id,
                    token_contract,
                    token_symbol,
                    raw_json
                FROM normalized_transactions
                WHERE chain = ?
                  AND (LOWER(from_address) = ? OR LOWER(COALESCE(to_address, '')) = ?)
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (chain, lower_address, lower_address, limit),
            )
            rows = cursor.fetchall()
        return [
            {
                "chain": row[0],
                "tx_hash": row[1],
                "block_number": row[2],
                "timestamp": row[3],
                "from_address": row[4],
                "to_address": row[5],
                "value": row[6],
                "asset": row[7],
                "direction": row[8],
                "method_id": row[9],
                "token_contract": row[10],
                "token_symbol": row[11],
                "raw": json.loads(row[12]),
            }
            for row in rows
        ]
