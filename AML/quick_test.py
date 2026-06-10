#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

print("Testing import...")
try:
    from aml_pipeline.config import load_config
    print("Config import: OK")
    
    cfg = load_config()
    print(f"Config loaded: {cfg.mysql_db}")
    
    from aml_pipeline.clustering.eth_adapter import EthereumAdapter
    print("Adapter import: OK")
    
    adapter = EthereumAdapter(cfg)
    print(f"Adapter created: {adapter.chain_name}")
    
    print("\nAttempting to count transactions...")
    count = adapter._count_mariadb_transactions()
    print(f"Transaction count: {count}")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
