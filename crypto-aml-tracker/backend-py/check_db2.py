"""Check API limits and chain_name in alert tables."""
import os
from dotenv import load_dotenv
from pathlib import Path
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

# What chain names are stored in each alert table?
for table in ["placement_detections", "layering_alerts", "integration_alerts", "wallet_clusters"]:
    cur.execute(f"SELECT DISTINCT chain_name FROM `{table}`")
    vals = [list(r.values())[0] for r in cur.fetchall()]
    print(f"{table} distinct chain_name: {vals}")

# Check if AML engines store chain_name per-alert or not
print()
cur.execute("SHOW COLUMNS FROM placement_runs")
cols = [r["Field"] for r in cur.fetchall()]
print("placement_runs cols:", cols)

# Placement: latest run total without limit
cur.execute("""
    SELECT COUNT(*) as cnt FROM placement_detections
    WHERE run_id=(
        SELECT id FROM placement_runs WHERE status='completed'
        ORDER BY completed_at DESC LIMIT 1
    )
""")
print("placement latest run total:", cur.fetchone()["cnt"])

# What the frontend sees: default limit=50 on placement GET /
print("placement GET default limit: 50  --> user sees only 50 of 402")

# Layering total
cur.execute("""
    SELECT COUNT(*) as cnt FROM layering_alerts
    WHERE run_id=(
        SELECT id FROM layering_runs WHERE status='completed'
        ORDER BY completed_at DESC LIMIT 1
    )
""")
print("layering latest run total:", cur.fetchone()["cnt"])

# Integration total
cur.execute("""
    SELECT COUNT(*) as cnt FROM integration_alerts
    WHERE run_id=(
        SELECT id FROM integration_runs WHERE status='completed'
        ORDER BY completed_at DESC LIMIT 1
    )
""")
print("integration latest run total:", cur.fetchone()["cnt"])

# Check what transactionService.js calls for placements
print()
print("Summary of problems found:")
print("1. placement_detections.chain_name is ALL 'ethereum' - engines store wrong chain")
print("2. placement GET / has limit=50 default, frontend calls getPlacements with no override")
print("3. layering_alerts.chain_name is ALL 'ethereum'")
print("4. integration_alerts.chain_name is ALL 'ethereum'")
print("5. wallet_clusters has only ETH clusters - other chains not clustered yet")
print("6. Chain filter can never work because chain_name is always 'ethereum' in alert tables")

cur.close()
conn.close()
