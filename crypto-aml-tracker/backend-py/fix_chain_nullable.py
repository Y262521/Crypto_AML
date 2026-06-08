"""
Make chain_name nullable in alert tables and set all to NULL (cross-chain).
AML engines are cross-chain — storing 'ethereum' is misleading.
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

# Check current definition
tables_info = {
    "placement_detections": None,
    "layering_alerts": None,
    "integration_alerts": None,
}

for t in tables_info:
    cur.execute(f"SHOW COLUMNS FROM `{t}` WHERE Field='chain_name'")
    row = cur.fetchone()
    tables_info[t] = row
    print(f"{t} chain_name: {row}")

# Make chain_name nullable and set to NULL
for t, info in tables_info.items():
    if not info:
        print(f"  {t}: no chain_name column, skipping")
        continue
    try:
        # Alter to allow NULL
        cur.execute(f"ALTER TABLE `{t}` MODIFY COLUMN `chain_name` VARCHAR(64) NULL DEFAULT NULL")
        conn.commit()
        # Now set to NULL for all rows
        cur.execute(f"UPDATE `{t}` SET chain_name = NULL")
        rows = cur.rowcount
        conn.commit()
        print(f"  {t}: chain_name now nullable, cleared {rows} rows -> NULL (cross-chain)")
    except Exception as e:
        print(f"  {t}: ERROR {e}")

cur.close()
conn.close()
print("Done.")
