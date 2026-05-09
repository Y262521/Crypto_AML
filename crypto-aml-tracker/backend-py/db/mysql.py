"""
MySQL connection for the FastAPI backend.
Reads from the clean MySQL database populated by the ETL pipeline.
Uses aiomysql for async access.
"""

import os
import aiomysql

pool = None


async def connect_mysql():
    global pool
    pool = await aiomysql.create_pool(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        user=os.getenv("MYSQL_USER", "hakim"),
        password=os.getenv("MYSQL_PASSWORD", "hakim22"),
        db=os.getenv("MYSQL_DB", "aml_db"),
        charset="utf8mb4",
        use_unicode=True,
        autocommit=True,
        minsize=1,
        maxsize=10,
    )
    print(f"MySQL connected → {os.getenv('MYSQL_DB', 'aml_db')}")

async def close_mysql():
    global pool
    if pool is not None:
        pool.close()
        await pool.wait_closed()
        pool = None


def get_pool():
    return pool


async def fetch_all(sql: str, args=None) -> list[dict]:
    """Execute a SELECT and return all rows as dicts."""
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, args or ())
            return await cur.fetchall()


async def fetch_one(sql: str, args=None) -> dict | None:
    """Execute a SELECT and return the first row as a dict."""
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql, args or ())
            return await cur.fetchone()
