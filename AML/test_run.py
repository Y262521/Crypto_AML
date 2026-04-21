import sys
import logging
logging.basicConfig(level=logging.DEBUG)
sys.path.insert(0, "/home/hakim/Crypto_AML/AML/src")
sys.path.insert(0, "/home/hakim/Crypto_AML/AML/src/aml_pipeline")
from aml_pipeline.config import load_config
from aml_pipeline.analytics.placement import PlacementAnalysisEngine
cfg = load_config()
engine = PlacementAnalysisEngine(cfg=cfg)
try:
    print("Running engine...")
    engine.run(source="mariadb", persist=True)
    print("Success")
except Exception as e:
    import traceback
    traceback.print_exc()
