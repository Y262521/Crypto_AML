import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from aml_pipeline.config import load_config
from aml_pipeline.utils.connections import get_maria_engine
from sqlalchemy import text

cfg = load_config()
engine = get_maria_engine(cfg)
try:
    with engine.connect() as conn:
        count = conn.execute(
            text("SELECT COUNT(*) FROM wallet_clusters WHERE chain_name = 'ethereum'")
        ).scalar_one()
        print(f"Clusters in database: {count}")
        
        # Check addresses with cluster_id
        addr_count = conn.execute(
            text("SELECT COUNT(*) FROM addresses WHERE cluster_id IS NOT NULL")
        ).scalar_one()
        print(f"Addresses with cluster assignment: {addr_count}")
finally:
    engine.dispose()
