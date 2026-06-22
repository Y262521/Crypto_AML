import asyncio
from dotenv import load_dotenv
import sys

load_dotenv('crypto-aml-tracker/backend-py/.env')

sys.path.append('crypto-aml-tracker/backend-py')
from db.mysql import fetch_all, connect_mysql, close_mysql

async def main():
    await connect_mysql()
    from db.mysql import pool
    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("ALTER TABLE placement_runs MODIFY chain_name VARCHAR(255) NOT NULL DEFAULT 'ethereum'")
                await cur.execute("""
                    UPDATE placement_runs
                    SET chain_name = 'ethereum,bnb,polygon,arbitrum,base,bitcoin,litecoin,dogecoin,bitcoin_cash,solana'
                    WHERE source = 'pipeline'
                """)
                print(f"Updated {cur.rowcount} pipeline runs to multi-chain.")
    finally:
        await close_mysql()

asyncio.run(main())
