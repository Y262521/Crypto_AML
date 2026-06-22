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
        print("--- PLACEMENT RUNS ---")
        rows = await fetch_all("SELECT source, chain_name, COUNT(*) as cnt FROM placement_runs GROUP BY source, chain_name;")
        for r in rows:
            print(r)
            
        print("\n--- CLUSTERS ---")
        rows = await fetch_all("SELECT chain_name, COUNT(*) as cnt FROM wallet_clusters GROUP BY chain_name;")
        for r in rows:
            print(r)
            
        print("\n--- LAYERING ---")
        rows = await fetch_all("SELECT chain_name, COUNT(*) as cnt FROM layering_alerts GROUP BY chain_name;")
        for r in rows:
            print(r)
            
        print("\n--- INTEGRATION ---")
        rows = await fetch_all("SELECT chain_name, COUNT(*) as cnt FROM integration_alerts GROUP BY chain_name;")
        for r in rows:
            print(r)
            
    finally:
        await close_mysql()

asyncio.run(main())
