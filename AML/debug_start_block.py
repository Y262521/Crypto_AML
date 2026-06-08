import sys
sys.path.insert(0, 'src')
from dotenv import load_dotenv
load_dotenv('C:/Users/yona/Desktop/Crypto_AML/crypto-aml-tracker/backend-py/.env')
from aml_pipeline.config import load_config
from aml_pipeline.utils.connections import get_mongo_client

cfg = load_config()
client = get_mongo_client(cfg)
col = client[cfg.mongo_raw_db][cfg.mongo_raw_collection]

# What does find_one(sort=[block_number,-1]) return?
latest_all = col.find_one(sort=[("block_number", -1)])
print("Highest block_number in collection (all chains):", latest_all.get("block_number") if latest_all else "None")
print("  chain_name:", latest_all.get("chain_name", "MISSING") if latest_all else "None")

# With ETH filter
latest_eth = col.find_one(
    {"$or": [{"chain_name": "ethereum"}, {"chain_name": {"$exists": False}}]},
    sort=[("block_number", -1)]
)
print("\nHighest ETH block_number:", latest_eth.get("block_number") if latest_eth else "None")
print("  chain_name:", latest_eth.get("chain_name", "MISSING") if latest_eth else "None")

# Test EVMExtractor
from aml_pipeline.etl.extract.evm import EVMExtractor
ext = EVMExtractor.__new__(EVMExtractor)
ext.cfg = cfg
from aml_pipeline.chains.registry import get_chain
ext.chain_config = get_chain("ethereum")
ext.raw_collection = col
latest = ext.get_latest_saved_block()
print("\nEVMExtractor.get_latest_saved_block():", latest)

client.close()
print("\nLatest ETH block from RPC: checking...")
