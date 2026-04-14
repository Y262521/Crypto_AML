import os
from pathlib import Path

from dotenv import load_dotenv


ENV_PATH = Path(__file__).resolve().with_name(".env")
load_dotenv(ENV_PATH)


def get_env(*names: str, default: str | None = None) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return value
    return default


def get_mongo_db_name() -> str:
    return get_env("MONGO_PROCESSED_DB", "MONGO_DB", "MONGO_RAW_DB", default="aml_raw")


def get_processed_collection_name() -> str:
    return get_env("MONGO_PROCESSED_COLLECTION", default="processed_transactions")


def get_cluster_collection_name() -> str:
    return get_env("MONGO_ADDRESS_CLUSTERS_COLLECTION", default="address_clusters")


def get_rpc_url() -> str:
    return get_env(
        "ALCHEMY_RPC",
        "RPC_URL",
        "PYTHON_RPC_URL",
        default="https://ethereum-rpc.publicnode.com",
    )
