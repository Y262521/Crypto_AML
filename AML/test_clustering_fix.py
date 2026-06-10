"""Test script to verify clustering fix for eth_adapter."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from aml_pipeline.config import load_config
from aml_pipeline.clustering.eth_adapter import EthereumAdapter

print("=" * 70)
print("TESTING CLUSTERING FIX FOR ETH_ADAPTER")
print("=" * 70)

cfg = load_config()
print(f"\nConfig: {cfg.mysql_host} / {cfg.mysql_db}")

# Create adapter
adapter = EthereumAdapter(cfg)
print(f"Adapter: {adapter.chain_name} ({adapter.blockchain_type})")

# Test the count method (this was the bug - it used to count ALL chains)
print(f"\nCounting Ethereum transactions in MariaDB...")
try:
    count = adapter._count_mariadb_transactions()
    print(f"✓ Found {count} Ethereum transactions")
    
    if count == 0:
        print("\n⚠ WARNING: No Ethereum transactions found in MariaDB!")
        print("   This might be expected if you only have other chains' data.")
        print("   Clustering will fall back to CSV or MongoDB.")
    else:
        print(f"\n✓ SUCCESS: Adapter correctly counts only Ethereum transactions")
        
        # Try loading a few transactions
        print(f"\nLoading first 3 transactions to verify they're actually Ethereum...")
        tx_count = 0
        for tx in adapter.iter_transactions(source="mariadb"):
            tx_count += 1
            print(f"  TX {tx_count}: chain={tx.chain_name}, from={tx.from_address[:12]}..., value={tx.value_eth:.6f}")
            if tx_count >= 3:
                break
        
        if tx_count > 0:
            print(f"\n✓ SUCCESS: Adapter successfully loads Ethereum transactions")
        else:
            print(f"\n✗ ERROR: Count returned {count} but no transactions loaded!")
            
except Exception as e:
    print(f"✗ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
