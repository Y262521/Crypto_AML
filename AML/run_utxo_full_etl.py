"""Run full UTXO ETL: extract 3 blocks per chain, load to MySQL, run clustering."""
import sys, os, traceback
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, 'src')
from dotenv import load_dotenv
load_dotenv('C:/Users/yona/Desktop/Crypto_AML/crypto-aml-tracker/backend-py/.env')

from aml_pipeline.config import load_config
from aml_pipeline.etl.extract.utxo import UTXOExtractor
from aml_pipeline.etl.load.mariadb_loader import (
    create_tables_if_not_exist, load_utxo_pairs_to_mariadb
)
from aml_pipeline.utils.connections import get_maria_engine
from sqlalchemy import text

cfg = load_config()
create_tables_if_not_exist(cfg)

UTXO_CHAINS = ["bitcoin", "litecoin", "dogecoin", "bitcoin_cash"]

print("=" * 55)
print("UTXO FULL ETL (3 blocks per chain)")
print("=" * 55)

results = {}
for chain_name in UTXO_CHAINS:
    print(f"\n[{chain_name}] Extracting 3 blocks...")
    try:
        ext = UTXOExtractor(cfg=cfg, chain=chain_name)
        fb, tb = ext.fetch_and_store_raw(batch=3)
        results[chain_name] = {"status": "ok", "from": fb, "to": tb}
        print(f"  Blocks {fb} -> {tb}")
    except Exception as e:
        results[chain_name] = {"status": "error", "error": str(e)[:80]}
        print(f"  ERROR: {e}")
        traceback.print_exc()

print("\n" + "=" * 55)
print("LOADING TO MARIADB")
print("=" * 55)

for chain_name in UTXO_CHAINS:
    if results.get(chain_name, {}).get("status") != "ok":
        continue
    print(f"\n[{chain_name}] Loading to MySQL...")
    try:
        r = load_utxo_pairs_to_mariadb(cfg=cfg, chain_name=chain_name)
        print(f"  Loaded {r.get('transactions_loaded', 0)} rows")
    except Exception as e:
        print(f"  ERROR: {e}")

print("\n" + "=" * 55)
print("FINAL DB COUNTS")
print("=" * 55)

engine = get_maria_engine(cfg)
with engine.connect() as conn:
    total = conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar()
    rows = conn.execute(text(
        "SELECT COALESCE(chain_name,'ethereum') AS chain, COUNT(*) AS cnt "
        "FROM transactions GROUP BY chain_name ORDER BY cnt DESC"
    )).all()
    clusters = conn.execute(text("SELECT COUNT(*) FROM wallet_clusters")).scalar()
engine.dispose()

print(f"\nTotal transactions: {total:,}")
print("By chain:")
for r in rows:
    print(f"  {str(r[0]).ljust(16)}: {r[1]:,}")
print(f"Clusters: {clusters}")

print("\n" + "=" * 55)
print("RUNNING UTXO CLUSTERING")
print("=" * 55)

for chain_name in UTXO_CHAINS:
    if results.get(chain_name, {}).get("status") != "ok":
        continue
    print(f"\n[{chain_name}] Running clustering...")
    try:
        from aml_pipeline.clustering.utxo_engine import UTXOClusteringEngine
        engine_obj = UTXOClusteringEngine(cfg=cfg, chain_name=chain_name)
        cluster_results = engine_obj.run(persist=True, min_cluster_size=2)
        print(f"  Clusters found: {len(cluster_results)}")
    except Exception as e:
        print(f"  Clustering error: {e}")

print("\n" + "=" * 55)
print("RUNNING UTXO AML DETECTION")
print("=" * 55)

for chain_name in UTXO_CHAINS:
    if results.get(chain_name, {}).get("status") != "ok":
        continue
    print(f"\n[{chain_name}] Running AML detection...")
    try:
        from aml_pipeline.clustering.utxo_adapter import UTXOAdapter
        from aml_pipeline.analytics.utxo_aml import UTXOAMLDetector
        adapter = UTXOAdapter(cfg=cfg, chain_name=chain_name)
        txs = list(adapter.iter_transactions(source="mariadb"))
        print(f"  Loaded {len(txs)} transactions")
        detector = UTXOAMLDetector(cfg=cfg, chain_name=chain_name)
        aml_result = detector.run(txs)
        print(f"  CoinJoin hits:   {len(aml_result['coinjoin'])}")
        print(f"  Peeling hits:    {len(aml_result['change_peeling'])}")
        print(f"  Multi-hop hits:  {len(aml_result['multihop'])}")
        print(f"  Total AML hits:  {aml_result['total_hits']}")
    except Exception as e:
        print(f"  AML error: {e}")

print("\n" + "=" * 55)
print("UTXO ETL COMPLETE")
print("=" * 55)
print("Results:")
for chain, res in results.items():
    if res["status"] == "ok":
        print(f"  OK   {chain.ljust(14)}: blocks {res['from']} -> {res['to']}")
    else:
        print(f"  FAIL {chain.ljust(14)}: {res.get('error','?')}")
