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
        rows = await fetch_all("SELECT DISTINCT run_id FROM integration_alerts LIMIT 5;")
        for r in rows:
            print("integration run_id:", r)
            
        rows = await fetch_all("SELECT id, source FROM placement_runs LIMIT 5;")
        for r in rows:
            print("placement run:", r)
            
        rows = await fetch_all("SELECT COUNT(*) FROM integration_runs;")
        print("integration_runs count:", rows)
    finally:
        await close_mysql()

asyncio.run(main())
