import asyncio
from dotenv import load_dotenv
import sys

# Load env
load_dotenv('crypto-aml-tracker/backend-py/.env')

sys.path.append('crypto-aml-tracker/backend-py')
from db.mysql import fetch_all, connect_mysql, close_mysql

async def main():
    await connect_mysql()
    try:
        rows = await fetch_all("""
            SELECT
                COALESCE(ia.chain_name, 'ethereum') AS chain_name,
                COUNT(*) AS integration_count
            FROM integration_alerts ia
            JOIN placement_runs pr ON ia.run_id = pr.id
            GROUP BY COALESCE(ia.chain_name, 'ethereum')
        """)
        print("Integration count query result:")
        for r in rows:
            print(r)
    finally:
        await close_mysql()

asyncio.run(main())
