"""Debug script to understand clustering data source issue."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from aml_pipeline.config import load_config
from sqlalchemy import text
from aml_pipeline.utils.connections import get_maria_engine

print("=" * 60)
print("DEBUGGING CLUSTERING DATA SOURCE")
print("=" * 60)

cfg = load_config()
print(f"\nConfig loaded: {cfg.mysql_host} / {cfg.mysql_db}")
print(f"Min cluster size: {cfg.clustering_min_cluster_size}")

# Check database
engine = get_maria_engine(cfg)
try:
    with engine.connect() as conn:
        print("\n" + "-" * 60)
        print("DATABASE STATS")
        print("-" * 60)
        
        # Count total transactions
        total = conn.execute(text('SELECT COUNT(*) FROM transactions')).scalar()
        print(f"Total transactions in DB: {total}")
        
        # Count by chain
        by_chain = conn.execute(
            text('''
                SELECT 
                    COALESCE(chain_name, 'NULL') as chain, 
                    COUNT(*) as count 
                FROM transactions 
                GROUP BY chain_name
            ''')
        ).fetchall()
        print(f"\nTransactions by chain:")
        for row in by_chain:
            print(f"  {row[0]}: {row[1]}")
        
        # Count ethereum specifically (using the same query the adapter uses)
        eth_count = conn.execute(
            text("""
                SELECT COUNT(*) 
                FROM transactions
                WHERE chain_name = 'ethereum' OR (chain_name IS NULL AND 'ethereum' = 'ethereum')
            """)
        ).scalar()
        print(f"\nEthereum transactions (adapter query): {eth_count}")
        
        # Sample some transactions
        print(f"\nSample of first 5 transactions:")
        sample = conn.execute(
            text('SELECT tx_hash, from_address, to_address, chain_name, value_eth FROM transactions LIMIT 5')
        ).fetchall()
        for row in sample:
            print(f"  {row[0][:16]}... from={row[1][:10]}... to={row[2][:10] if row[2] else 'None'}... chain={row[3]} value={row[4]}")
finally:
    engine.dispose()

print("\n" + "-" * 60)
print("ADAPTER TEST")
print("-" * 60)

# Test the adapter
from aml_pipeline.clustering.eth_adapter import EthereumAdapter

adapter = EthereumAdapter(cfg)
print(f"Adapter chain: {adapter.chain_name}")
print(f"Adapter type: {adapter.blockchain_type}")

# Count what the adapter would load
print(f"\nTrying to load transactions from adapter (source='auto')...")
tx_count = 0
try:
    for tx in adapter.iter_transactions(source="auto"):
        tx_count += 1
        if tx_count <= 3:
            print(f"  TX {tx_count}: {tx.tx_hash[:16]}... from={tx.from_address[:10]}... to={tx.to_address[:10] if tx.to_address else 'None'}...")
        if tx_count >= 5:
            print(f"  (stopping after 5 for brevity)")
            break
    print(f"\nAdapter successfully loaded {tx_count} transactions (stopped early for testing)")
except Exception as e:
    print(f"ERROR loading from adapter: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
