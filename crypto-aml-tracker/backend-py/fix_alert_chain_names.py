"""
Fix alert chain_name values.

The AML engines (placement/layering/integration) run on ALL chain transactions
together — they are cross-chain engines. Storing chain_name='ethereum' is wrong.
Set chain_name=NULL in all alert tables so the chain filter shows all alerts
for any chain selection.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")
import pymysql

conn = pymysql.connect(
    host=os.getenv("MYSQL_HOST", "127.0.0.1"),
    port=int(os.getenv("MYSQL_PORT", 3306)),
    user=os.getenv("MYSQL_USER", "root"),
    password=os.getenv("MYSQL_PASSWORD", ""),
    database=os.getenv("MYSQL_DB", "aml_clean"),
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)
cur = conn.cursor()

tables = ["placement_detections", "layering_alerts", "integration_alerts"]
for t in tables:
    try:
        cur.execute(f"UPDATE `{t}` SET chain_name = NULL WHERE chain_name = 'ethereum'")
        rows = cur.rowcount
        conn.commit()
        print(f"  {t}: cleared chain_name on {rows} rows → now NULL (cross-chain)")
    except Exception as e:
        print(f"  {t}: ERROR {e}")

cur.close()
conn.close()
print("Done — alerts are now chain_name=NULL (cross-chain, show under all filters)")
