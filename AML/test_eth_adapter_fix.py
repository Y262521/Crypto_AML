"""Test that EthereumAdapter now filters by chain correctly"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from aml_pipeline.config import load_config
from aml_pipeline.clustering.eth_adapter import EthereumAdapter
from collections import Counter

cfg = load_config()
adapter = EthereumAdapter(cfg)

print(f"Testing EthereumAdapter with chain_name={adapter.chain_name}")
print("\nLoading transactions...")

transactions = list(adapter.iter_transactions(source="mariadb"))
print(f"Total transactions loaded: {len(transactions)}")

if transactions:
    chain_counts = Counter(tx.chain_name for tx in transactions)
    print(f"\nTransactions by chain:")
    for chain, count in chain_counts.items():
        print(f"  {chain}: {count}")
    
    if len(chain_counts) > 1:
        print(f"\n❌ FAIL: Multiple chains detected! Should only be 'ethereum'")
        sys.exit(1)
    elif 'ethereum' not in chain_counts:
        print(f"\n❌ FAIL: Expected 'ethereum' but got {list(chain_counts.keys())}")
        sys.exit(1)
    else:
        print(f"\n✅ SUCCESS: Only 'ethereum' transactions loaded")
        sys.exit(0)
else:
    print("No transactions loaded")
    sys.exit(1)
