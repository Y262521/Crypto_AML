"""
Master multi-chain ETL + AML engine runner.
Fetches blocks from every supported chain, loads to MySQL,
then runs clustering, placement, layering, and integration
engines per-chain so every alert gets the correct chain_name.

Chains:
  EVM    : ethereum, bnb, polygon, arbitrum, base
  UTXO   : bitcoin, litecoin, dogecoin, bitcoin_cash
  Account: solana
"""
import sys, os, time
sys.path.insert(0, 'src')
from dotenv import load_dotenv
load_dotenv('C:/Users/yona/Desktop/Crypto_AML/crypto-aml-tracker/backend-py/.env')

from aml_pipeline.config import load_config
from aml_pipeline.etl.load.mariadb_loader import (
    create_tables_if_not_exist,
    load_utxo_pairs_to_mariadb,
)
from aml_pipeline.utils.connections import get_maria_engine
from sqlalchemy import text

cfg = load_config()
create_tables_if_not_exist(cfg)

results = {}
ok_chains = []   # chains that actually extracted data

# ── EVM chains ────────────────────────────────────────────────────────────────
EVM_CHAINS = ["ethereum", "bnb", "polygon", "arbitrum", "base"]

print("\n[EVM CHAINS — EXTRACT + LOAD]")
for chain_name in EVM_CHAINS:
    print(f"  {chain_name}...", end=" ", flush=True)
    try:
        from aml_pipeline.etl.extract.evm import EVMExtractor
        ext = EVMExtractor(cfg=cfg, chain=chain_name)
        fb, tb = ext.fetch_and_store_raw(batch=3)
        results[chain_name] = {"status": "ok", "from": fb, "to": tb}
        print(f"OK blocks {fb}->{tb}")

        if chain_name == "ethereum":
            from aml_pipeline.etl.transform.transformer import transform_raw_to_aml
            t = transform_raw_to_aml(start_block=fb, end_block=tb, cfg=cfg)
            from aml_pipeline.etl.load.mariadb_loader import load_to_mariadb
            load_to_mariadb(cfg=cfg, chain_name="ethereum")
            print(f"    Loaded {t['transactions_created']} ETH txs to MySQL")
        else:
            load_utxo_pairs_to_mariadb(cfg=cfg, chain_name=chain_name)
            print(f"    Loaded to MySQL")
        ok_chains.append(chain_name)
    except ConnectionError as e:
        results[chain_name] = {"status": "no_rpc"}
        print(f"SKIP (no RPC: {str(e)[:40]})")
    except Exception as e:
        results[chain_name] = {"status": "error", "error": str(e)[:80]}
        print(f"ERROR: {str(e)[:80]}")

# ── UTXO chains ───────────────────────────────────────────────────────────────
UTXO_CHAINS = ["bitcoin", "litecoin", "dogecoin", "bitcoin_cash"]

print("\n[UTXO CHAINS — EXTRACT + LOAD]")
for chain_name in UTXO_CHAINS:
    print(f"  {chain_name}...", end=" ", flush=True)
    try:
        from aml_pipeline.etl.extract.utxo import UTXOExtractor
        ext = UTXOExtractor(cfg=cfg, chain=chain_name)
        fb, tb = ext.fetch_and_store_raw(batch=3)
        results[chain_name] = {"status": "ok", "from": fb, "to": tb}
        print(f"OK blocks {fb}->{tb}")
        load_utxo_pairs_to_mariadb(cfg=cfg, chain_name=chain_name)
        print(f"    Loaded to MySQL")
        ok_chains.append(chain_name)
    except Exception as e:
        results[chain_name] = {"status": "error", "error": str(e)[:80]}
        print(f"ERROR: {str(e)[:80]}")

# ── Solana ────────────────────────────────────────────────────────────────────
print("\n[SOLANA — EXTRACT + LOAD]")
print("  solana...", end=" ", flush=True)
try:
    from aml_pipeline.etl.extract.solana import SolanaExtractor
    ext = SolanaExtractor(cfg=cfg)
    fs, ts_ = ext.fetch_and_store_raw(batch=3)
    results["solana"] = {"status": "ok", "from": fs, "to": ts_}
    print(f"OK slots {fs}->{ts_}")
    load_utxo_pairs_to_mariadb(cfg=cfg, chain_name="solana")
    print(f"    Loaded to MySQL")
    ok_chains.append("solana")
except Exception as e:
    results["solana"] = {"status": "error", "error": str(e)[:80]}
    print(f"ERROR: {str(e)[:80]}")

# ── CLUSTERING — per chain ────────────────────────────────────────────────────
print("\n[CLUSTERING — PER CHAIN]")
cluster_counts = {}
for chain_name in ok_chains:
    print(f"  {chain_name}...", end=" ", flush=True)
    try:
        if chain_name in EVM_CHAINS:
            from aml_pipeline.clustering.engine import ClusteringEngine
            eng = ClusteringEngine(cfg=cfg, chain_name=chain_name)
            res = eng.run(persist=True, min_cluster_size=cfg.clustering_min_cluster_size)
        elif chain_name in UTXO_CHAINS:
            from aml_pipeline.clustering.utxo_engine import UTXOClusteringEngine
            eng = UTXOClusteringEngine(cfg=cfg, chain_name=chain_name)
            res = eng.run(persist=True, min_cluster_size=1)
        elif chain_name == "solana":
            from aml_pipeline.clustering.solana_engine import SolanaClusteringEngine
            eng = SolanaClusteringEngine(cfg=cfg)
            res = eng.run(persist=True, min_cluster_size=2)
        else:
            print("SKIP (unknown type)")
            continue
        cluster_counts[chain_name] = len(res)
        print(f"OK  {len(res)} clusters")
    except Exception as e:
        cluster_counts[chain_name] = 0
        print(f"ERROR: {str(e)[:80]}")

# ── PLACEMENT — per chain ─────────────────────────────────────────────────────
print("\n[PLACEMENT — PER CHAIN]")
placement_counts = {}
eth_placement_result = None
for chain_name in ok_chains:
    print(f"  {chain_name}...", end=" ", flush=True)
    try:
        from aml_pipeline.analytics.placement import PlacementAnalysisEngine
        eng = PlacementAnalysisEngine(cfg=cfg, chain_name=chain_name)
        res = eng.run(source="mariadb", persist=True)
        placement_counts[chain_name] = len(res.placements)
        if chain_name == "ethereum":
            eth_placement_result = res
        print(f"OK  {len(res.placements)} alerts")
    except Exception as e:
        placement_counts[chain_name] = 0
        print(f"ERROR: {str(e)[:80]}")

# ── LAYERING — per chain ──────────────────────────────────────────────────────
print("\n[LAYERING — PER CHAIN]")
layering_counts = {}
eth_layering_result = None
for chain_name in ok_chains:
    print(f"  {chain_name}...", end=" ", flush=True)
    try:
        from aml_pipeline.analytics.layering import LayeringAnalysisEngine
        eng = LayeringAnalysisEngine(cfg=cfg, chain_name=chain_name)
        seed = eth_placement_result if chain_name == "ethereum" else None
        res = eng.run(source="mariadb", persist=True, placement_result=seed)
        layering_counts[chain_name] = len(res.alerts)
        if chain_name == "ethereum":
            eth_layering_result = res
        print(f"OK  {len(res.alerts)} alerts")
    except Exception as e:
        layering_counts[chain_name] = 0
        print(f"ERROR: {str(e)[:80]}")

# ── INTEGRATION — per chain ───────────────────────────────────────────────────
print("\n[INTEGRATION — PER CHAIN]")
integration_counts = {}
for chain_name in ok_chains:
    print(f"  {chain_name}...", end=" ", flush=True)
    try:
        from aml_pipeline.analytics.integration import IntegrationAnalysisEngine
        eng = IntegrationAnalysisEngine(cfg=cfg, chain_name=chain_name)
        seed = eth_layering_result if chain_name == "ethereum" else None
        res = eng.run(source="mariadb", persist=True, layering_result=seed)
        integration_counts[chain_name] = len(res.alerts)
        print(f"OK  {len(res.alerts)} alerts")
    except Exception as e:
        integration_counts[chain_name] = 0
        print(f"ERROR: {str(e)[:80]}")

# ── SUMMARY ───────────────────────────────────────────────────────────────────
print("\n============================================================")
print("  FINAL DATABASE COUNTS")
print("============================================================")

engine = get_maria_engine(cfg)
with engine.connect() as conn:
    total_tx = conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar()
    tx_rows = conn.execute(text(
        "SELECT COALESCE(chain_name,'ethereum') AS chain, COUNT(*) AS cnt "
        "FROM transactions GROUP BY chain_name ORDER BY cnt DESC"
    )).all()
    total_clusters = conn.execute(text("SELECT COUNT(*) FROM wallet_clusters")).scalar()
    cluster_rows = conn.execute(text(
        "SELECT COALESCE(chain_name,'ethereum') AS chain, COUNT(*) AS cnt "
        "FROM wallet_clusters GROUP BY chain_name ORDER BY cnt DESC"
    )).all()
    total_pl = conn.execute(text("SELECT COUNT(*) FROM placement_detections")).scalar()
    pl_rows = conn.execute(text(
        "SELECT COALESCE(chain_name,'(none)') AS chain, COUNT(*) AS cnt "
        "FROM placement_detections GROUP BY chain_name ORDER BY cnt DESC"
    )).all()
    total_la = conn.execute(text("SELECT COUNT(*) FROM layering_alerts")).scalar()
    la_rows = conn.execute(text(
        "SELECT COALESCE(chain_name,'(none)') AS chain, COUNT(*) AS cnt "
        "FROM layering_alerts GROUP BY chain_name ORDER BY cnt DESC"
    )).all()
    total_ia = conn.execute(text("SELECT COUNT(*) FROM integration_alerts")).scalar()
    ia_rows = conn.execute(text(
        "SELECT COALESCE(chain_name,'(none)') AS chain, COUNT(*) AS cnt "
        "FROM integration_alerts GROUP BY chain_name ORDER BY cnt DESC"
    )).all()
engine.dispose()

print(f"\n  Transactions : {total_tx:,}")
for r in tx_rows:
    print(f"    {str(r[0]).ljust(16)}: {r[1]:,}")

print(f"\n  Clusters     : {total_clusters:,}")
for r in cluster_rows:
    print(f"    {str(r[0]).ljust(16)}: {r[1]:,}")

print(f"\n  Placement    : {total_pl:,}")
for r in pl_rows:
    print(f"    {str(r[0]).ljust(16)}: {r[1]:,}")

print(f"\n  Layering     : {total_la:,}")
for r in la_rows:
    print(f"    {str(r[0]).ljust(16)}: {r[1]:,}")

print(f"\n  Integration  : {total_ia:,}")
for r in ia_rows:
    print(f"    {str(r[0]).ljust(16)}: {r[1]:,}")

print("\n  Extraction results:")
all_ok = True
for chain, res in results.items():
    if res["status"] == "ok":
        print(f"    OK   {chain.ljust(16)}: {res['from']} -> {res['to']}")
    elif res["status"] == "no_rpc":
        print(f"    SKIP {chain.ljust(16)}: no RPC configured")
    else:
        print(f"    FAIL {chain.ljust(16)}: {res.get('error','?')}")
        all_ok = False

print("\n============================================================")
print("  STATUS:", "ALL OK" if all_ok else "SOME CHAINS FAILED (see above)")
print("============================================================")
