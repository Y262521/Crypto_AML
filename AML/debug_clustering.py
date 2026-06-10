"""
Debug script to check clustering data flow
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from aml_pipeline.config import load_config
from sqlalchemy import text
from aml_pipeline.utils.connections import get_maria_engine

cfg = load_config()
print(f"Database: {cfg.mysql_db}")

engine = get_maria_engine(cfg)

with engine.connect() as conn:
    # Check total transactions
    total = conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar_one()
    print(f"Total transactions: {total}")
    
    # Check chains
    chains = conn.execute(text("SELECT DISTINCT COALESCE(chain_name, 'ethereum') as chain FROM transactions")).scalars().all()
    print(f"Chains in DB: {chains}")
    
    # Check ethereum-specific transactions
    eth_count = conn.execute(
        text("SELECT COUNT(*) FROM transactions WHERE chain_name = 'ethereum' OR chain_name IS NULL")
    ).scalar_one()
    print(f"Ethereum transactions: {eth_count}")
    
    # Sample a few transactions
    sample = conn.execute(
        text("""
            SELECT tx_hash, block_number, from_address, to_address, value_eth, 
                   COALESCE(chain_name, 'ethereum') as chain
            FROM transactions 
            LIMIT 5
        """)
    ).mappings().all()
    
    print("\nSample transactions:")
    for row in sample:
        print(f"  {row['tx_hash'][:10]}... block={row['block_number']} chain={row['chain']} value={row['value_eth']}")

engine.dispose()

# Now test the adapter
print("\n" + "="*60)
print("Testing EthereumAdapter...")
print("="*60)

from aml_pipeline.clustering.eth_adapter import EthereumAdapter

adapter = EthereumAdapter(cfg)
print(f"Adapter chain_name: {adapter.chain_name}")

# Test count
mariadb_count = adapter._count_mariadb_transactions()
print(f"MariaDB transaction count (via adapter): {mariadb_count}")

# Test iteration
print("\nTesting iter_transactions with source='auto'...")
tx_count = 0
sample_txs = []
for tx in adapter.iter_transactions(source="auto"):
    tx_count += 1
    if tx_count <= 3:
        sample_txs.append(tx)
    if tx_count >= 100:
        break

print(f"Transactions yielded: {tx_count}")
if sample_txs:
    print("\nSample TxRecords:")
    for tx in sample_txs:
        print(f"  {tx.tx_hash[:10]}... chain={tx.chain_name} from={tx.from_address[:10]}... to={tx.to_address[:10]}...")
else:
    print("  No transactions yielded!")

# Test with explicit mariadb
print("\nTesting iter_transactions with source='mariadb'...")
tx_count2 = 0
for tx in adapter.iter_transactions(source="mariadb"):
    tx_count2 += 1
    if tx_count2 >= 100:
        break
print(f"Transactions yielded with mariadb source: {tx_count2}")
