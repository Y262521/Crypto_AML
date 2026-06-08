import sys
sys.path.insert(0, 'src')
from dotenv import load_dotenv
load_dotenv('C:/Users/yona/Desktop/Crypto_AML/crypto-aml-tracker/backend-py/.env')
from aml_pipeline.config import load_config
from aml_pipeline.utils.connections import get_maria_engine
from sqlalchemy import text

cfg = load_config()
engine = get_maria_engine(cfg)

with engine.connect() as conn:
    # Check placement runs
    runs = conn.execute(text(
        "SELECT id, status, completed_at, summary_json FROM placement_runs ORDER BY completed_at DESC LIMIT 5"
    )).all()
    print("Placement runs:")
    for r in runs:
        print(f"  {r[0]} | {r[1]} | {r[2]}")

    # Check placement detections count
    det = conn.execute(text("SELECT COUNT(*) FROM placement_detections")).scalar()
    print(f"\nPlacement detections total: {det:,}")

    # Check if there are detections linked to latest run
    if runs:
        latest = runs[0][0]
        det_latest = conn.execute(text(
            "SELECT COUNT(*) FROM placement_detections WHERE run_id = :rid"
        ), {"rid": latest}).scalar()
        print(f"Detections for latest run ({latest[:20]}...): {det_latest:,}")

    # Check placement_entities to see if chain_name is populated
    ents = conn.execute(text(
        "SELECT entity_id, entity_type, validation_status FROM placement_entities LIMIT 5"
    )).all()
    print(f"\nSample placement_entities:")
    for e in ents:
        print(f"  {str(e[0])[:30]} | {e[1]} | {e[2]}")

engine.dispose()
print("\nDone.")
