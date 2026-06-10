import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from aml_pipeline.config import load_config
from sqlalchemy import text
from aml_pipeline.utils.connections import get_maria_engine

cfg = load_config()
engine = get_maria_engine(cfg)

with engine.connect() as conn:
    total = conn.execute(text("SELECT COUNT(*) FROM transactions")).scalar_one()
    print(f"TOTAL_TXS: {total}")
    
    chains = list(conn.execute(text("SELECT DISTINCT COALESCE(chain_name, 'NULL') as c FROM transactions")).scalars())
    print(f"CHAINS: {','.join(chains)}")
    
    eth = conn.execute(text("SELECT COUNT(*) FROM transactions WHERE chain_name = 'ethereum' OR chain_name IS NULL")).scalar_one()
    print(f"ETH_TXS: {eth}")

engine.dispose()
