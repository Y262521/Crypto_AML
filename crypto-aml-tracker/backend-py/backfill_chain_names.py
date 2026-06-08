"""
Backfill chain_name on placement_detections, layering_alerts, integration_alerts
and wallet_clusters based on the chain_name of matching transactions.

Run once after upgrading the backend:
  python backfill_chain_names.py
"""
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import pymysql
import pymysql.cursors

cfg = dict(
    host=os.getenv("MYSQL_HOST", "127.0.0.1"),
    port=int(os.getenv("MYSQL_PORT", 3306)),
    user=os.getenv("MYSQL_USER", "root"),
    password=os.getenv("MYSQL_PASSWORD", ""),
    db=os.getenv("MYSQL_DB", "aml_clean"),
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

conn = pymysql.connect(**cfg)
cur = conn.cursor()

print("=" * 60)
print("Backfilling chain_name on alert tables...")

# ── 1. placement_detections ──────────────────────────────────────────────────
# The entity_id is either a wallet address (starts with 0x for ETH) or
# a cluster id (C-xxx). For addresses, match directly to transactions.
print("\n[1/4] placement_detections...")
cur.execute("""
    UPDATE placement_detections pd
    JOIN (
        SELECT from_address AS address, chain_name
        FROM transactions
        WHERE chain_name IS NOT NULL
        GROUP BY from_address, chain_name
        ORDER BY COUNT(*) DESC
    ) t ON t.address = pd.entity_id
    SET pd.chain_name = t.chain_name
    WHERE pd.chain_name IS NULL
""")
rows1a = cur.rowcount
print(f"  Updated {rows1a} rows via from_address match")

cur.execute("""
    UPDATE placement_detections pd
    JOIN (
        SELECT to_address AS address, chain_name
        FROM transactions
        WHERE chain_name IS NOT NULL
        GROUP BY to_address, chain_name
        ORDER BY COUNT(*) DESC
    ) t ON t.address = pd.entity_id
    SET pd.chain_name = t.chain_name
    WHERE pd.chain_name IS NULL
""")
rows1b = cur.rowcount
print(f"  Updated {rows1b} more rows via to_address match")

# For cluster IDs, look up addresses in cluster and find their chain
cur.execute("""
    UPDATE placement_detections pd
    JOIN addresses a ON a.cluster_id = pd.entity_id
    JOIN (
        SELECT from_address AS address, chain_name
        FROM transactions
        WHERE chain_name IS NOT NULL
        GROUP BY from_address, chain_name
        ORDER BY COUNT(*) DESC
    ) t ON t.address = a.address
    SET pd.chain_name = t.chain_name
    WHERE pd.chain_name IS NULL
""")
rows1c = cur.rowcount
print(f"  Updated {rows1c} more cluster rows")

conn.commit()

# ── 2. layering_alerts ───────────────────────────────────────────────────────
print("\n[2/4] layering_alerts...")
cur.execute("""
    UPDATE layering_alerts la
    JOIN (
        SELECT from_address AS address, chain_name
        FROM transactions
        WHERE chain_name IS NOT NULL
        GROUP BY from_address, chain_name
        ORDER BY COUNT(*) DESC
    ) t ON t.address = la.entity_id
    SET la.chain_name = t.chain_name
    WHERE la.chain_name IS NULL
""")
rows2a = cur.rowcount
cur.execute("""
    UPDATE layering_alerts la
    JOIN (
        SELECT to_address AS address, chain_name
        FROM transactions
        WHERE chain_name IS NOT NULL
        GROUP BY to_address, chain_name
        ORDER BY COUNT(*) DESC
    ) t ON t.address = la.entity_id
    SET la.chain_name = t.chain_name
    WHERE la.chain_name IS NULL
""")
rows2b = cur.rowcount
cur.execute("""
    UPDATE layering_alerts la
    JOIN addresses a ON a.cluster_id = la.entity_id
    JOIN (
        SELECT from_address AS address, chain_name
        FROM transactions
        WHERE chain_name IS NOT NULL
        GROUP BY from_address, chain_name
        ORDER BY COUNT(*) DESC
    ) t ON t.address = a.address
    SET la.chain_name = t.chain_name
    WHERE la.chain_name IS NULL
""")
rows2c = cur.rowcount
conn.commit()
print(f"  Updated {rows2a + rows2b + rows2c} rows")

# ── 3. integration_alerts ────────────────────────────────────────────────────
print("\n[3/4] integration_alerts...")
cur.execute("""
    UPDATE integration_alerts ia
    JOIN (
        SELECT from_address AS address, chain_name
        FROM transactions
        WHERE chain_name IS NOT NULL
        GROUP BY from_address, chain_name
        ORDER BY COUNT(*) DESC
    ) t ON t.address = ia.entity_id
    SET ia.chain_name = t.chain_name
    WHERE ia.chain_name IS NULL
""")
rows3a = cur.rowcount
cur.execute("""
    UPDATE integration_alerts ia
    JOIN (
        SELECT to_address AS address, chain_name
        FROM transactions
        WHERE chain_name IS NOT NULL
        GROUP BY to_address, chain_name
        ORDER BY COUNT(*) DESC
    ) t ON t.address = ia.entity_id
    SET ia.chain_name = t.chain_name
    WHERE ia.chain_name IS NULL
""")
rows3b = cur.rowcount
conn.commit()
print(f"  Updated {rows3a + rows3b} rows")

# ── 4. wallet_clusters (already has chain_name but may be NULL for old rows) ─
print("\n[4/4] wallet_clusters via addresses table...")
cur.execute("""
    UPDATE wallet_clusters wc
    JOIN addresses a ON a.cluster_id = wc.id
    JOIN (
        SELECT from_address AS address, chain_name
        FROM transactions
        WHERE chain_name IS NOT NULL
        GROUP BY from_address, chain_name
        ORDER BY COUNT(*) DESC
    ) t ON t.address = a.address
    SET wc.chain_name = t.chain_name
    WHERE wc.chain_name IS NULL
""")
rows4 = cur.rowcount
conn.commit()
print(f"  Updated {rows4} rows")

# ── Summary ──────────────────────────────────────────────────────────────────
print("\n--- Chain distribution after backfill ---")
for tbl in ["placement_detections", "layering_alerts", "integration_alerts", "wallet_clusters"]:
    try:
        cur.execute(f"SELECT COALESCE(chain_name,'(NULL)') as chain, COUNT(*) as cnt FROM `{tbl}` GROUP BY chain_name ORDER BY cnt DESC LIMIT 8")
        rows = cur.fetchall()
        print(f"\n{tbl}:")
        for r in rows:
            print(f"  {r['chain']}: {r['cnt']}")
    except Exception as e:
        print(f"  {tbl}: ERROR {e}")

cur.close()
conn.close()
print("\n=== Backfill complete ===")
