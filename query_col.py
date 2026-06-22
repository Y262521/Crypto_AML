import asyncio
from dotenv import load_dotenv
import sys

load_dotenv('crypto-aml-tracker/backend-py/.env')

sys.path.append('crypto-aml-tracker/backend-py')
from db.mysql import fetch_all, connect_mysql, close_mysql

async def main():
    await connect_mysql()
    try:
        rows = await fetch_all("SHOW COLUMNS FROM placement_runs LIKE 'chain_name';")
        print(rows)
    finally:
        await close_mysql()

asyncio.run(main())
