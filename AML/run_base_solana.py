"""Fetch 3 blocks for Base and Solana specifically."""
import sys, os, json
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, 'src')
from dotenv import load_dotenv
load_dotenv('C:/Users/yona/Desktop/Crypto_AML/crypto-aml-tracker/backend-py/.env')

from aml_pipeline.config import load_config
cfg = load_config()
from aml_pipeline.etl.load.mariadb_loader import create_tables_if_not_exist, load_utxo_pairs_to_mariadb
create_tables_if_not_exist(cfg)

results = {}

# ── Base (EVM) ────────────────────────────────────────────────────────────────
print("=" * 50)
print("[base] Extracting 3 blocks...")
print("=" * 50)
try:
    from aml_pipeline.etl.extract.evm import EVMExtractor
    ext = EVMExtractor(cfg=cfg, chain="base")
    print("[base] Latest saved block: " + str(ext.get_latest_saved_block()))
    fb, tb = ext.fetch_and_store_raw(batch=3)
    results["base"] = {"status": "ok", "from": fb, "to": tb}
    print("[base] OK - blocks " + str(fb) + " -> " + str(tb))
    # Load to MySQL
    load_utxo_pairs_to_mariadb(cfg=cfg, chain_name="base")
    print("[base] Loaded to MySQL")
except Exception as e:
    results["base"] = {"status": "error", "error": str(e)}
    print("[base] ERROR: " + str(e))

# ── Solana (Account-based) ────────────────────────────────────────────────────
print()
print("=" * 50)
print("[solana] Extracting 3 slots...")
print("=" * 50)
try:
    from aml_pipeline.etl.extract.solana import SolanaExtractor
    sol = SolanaExtractor(cfg=cfg)
    print("[solana] Latest saved slot: " + str(sol.get_latest_saved_block()))
    print("[solana] Current chain height: " + str(sol.get_latest_block()))
    fs, ts = sol.fetch_and_store_raw(batch=3)
    results["solana"] = {"status": "ok", "from": fs, "to": ts}
    print("[solana] OK - slots " + str(fs) + " -> " + str(ts))
    load_utxo_pairs_to_mariadb(cfg=cfg, chain_name="solana")
    print("[solana] Loaded to MySQL")
except Exception as e:
    results["solana"] = {"status": "error", "error": str(e)}
    print("[solana] ERROR: " + str(e))

# ── DB summary ────────────────────────────────────────────────────────────────
print()
print("=" * 50)
print("DB COUNTS BY CHAIN")
print("=" * 50)
from aml_pipeline.utils.connections import get_maria_engine
from sqlalchemy import text
engine = get_maria_engine(cfg)
with engine.connect() as conn:
    rows = conn.execute(text(
        "SELECT COALESCE(chain_name,'ethereum') AS chain, COUNT(*) AS cnt "
        "FROM transactions GROUP BY chain_name ORDER BY cnt DESC"
    )).all()
    total = conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar()
engine.dispose()

print("Total: " + str(total))
for r in rows:
    mark = " <-- just fetched" if r[0] in ("base","solana") else ""
    print("  " + str(r[0]).ljust(16) + ": " + str(r[1]) + mark)

print()
for chain, res in results.items():
    if res["status"] == "ok":
        print("[" + chain + "] SUCCESS: blocks/slots " + str(res['from']) + " -> " + str(res['to']))
    else:
        print("[" + chain + "] FAILED: " + str(res.get('error','?')))
