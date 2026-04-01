import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

def _get_env(name: str, default: Optional[str] = None):
    return os.getenv(name, default)

def _get_int(name: str, default: int) -> int:
    try:
        return int(_get_env(name, str(default)))
    except (TypeError, ValueError):
        return default

@dataclass(frozen=True)
class Config:
    base_dir: Path
    data_dir: Path
    raw_dir: Path
    staging_dir: Path
    processed_dir: Path
    log_level: str

    # MongoDB – raw blocks
    mongo_uri: str
    mongo_raw_db: str
    mongo_raw_collection: str
    # MongoDB – flattened transactions
    mongo_flat_tx_db: str
    mongo_flat_tx_collection: str
    # MongoDB – processed backup
    mongo_processed_db: str
    mongo_processed_collection: str

    # MySQL / MariaDB
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_db: str

    # Neo4j
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str
    neo4j_batch_size: int

    # Pipeline & AML
    eth_rpc_url: str
    eth_network: str
    eth_start_block: int
    eth_batch_size: int
    batch_size: int
    batch_size_transform: int
    aml_high_value_threshold: float

    # Clustering
    clustering_min_shared_counterparties: int
    clustering_temporal_window_seconds: int
    clustering_fan_threshold: int
    clustering_loop_max_depth: int


def load_config() -> Config:
    base_dir = Path(__file__).resolve().parents[2]
    load_dotenv(base_dir / ".env")

    data_dir = base_dir / "data"
    raw_dir = data_dir / "raw"
    staging_dir = data_dir / "staging"
    processed_dir = data_dir / "processed"

    for folder in [data_dir, raw_dir, staging_dir, processed_dir]:
        folder.mkdir(parents=True, exist_ok=True)

    return Config(
        base_dir=base_dir,
        data_dir=data_dir,
        raw_dir=raw_dir,
        staging_dir=staging_dir,
        processed_dir=processed_dir,
        log_level=_get_env("LOG_LEVEL", "INFO"),

        mongo_uri=_get_env("MONGO_URI", "mongodb://localhost:27017"),
        mongo_raw_db=_get_env("MONGO_RAW_DB", "aml_raw"),
        mongo_raw_collection=_get_env("MONGO_RAW_COLLECTION", "raw_blocks"),
        mongo_flat_tx_db=_get_env("MONGO_FLAT_DB", "aml_raw"),
        mongo_flat_tx_collection=_get_env("MONGO_FLAT_COLLECTION", "raw_transactions"),
        mongo_processed_db=_get_env("MONGO_PROCESSED_DB", "aml_raw"),
        mongo_processed_collection=_get_env("MONGO_PROCESSED_COLLECTION", "processed_transactions"),

        mysql_host=_get_env("MYSQL_HOST", "localhost"),
        mysql_port=_get_int("MYSQL_PORT", 3306),
        mysql_user=_get_env("MYSQL_USER", "root"),
        mysql_password=_get_env("MYSQL_PASSWORD", "1216mysql"),
        mysql_db=_get_env("MYSQL_DB", "aml_db"),

        neo4j_uri=_get_env("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=_get_env("NEO4J_USER", "neo4j"),
        neo4j_password=_get_env("NEO4J_PASSWORD", "neo4j1216"),
        neo4j_database=_get_env("NEO4J_DATABASE", "neo4j"),
        neo4j_batch_size=_get_int("NEO4J_BATCH_SIZE", 500),

        eth_rpc_url=_get_env("ALCHEMY_RPC"),
        eth_network=_get_env("ETH_NETWORK", "mainnet"),
        eth_start_block=_get_int("ETH_START_BLOCK", 23849990),
        eth_batch_size=_get_int("BATCH_SIZE", 10),
        batch_size=_get_int("BATCH_SIZE", 10),
        batch_size_transform=_get_int("TRANSFORM_BATCH_SIZE", 100),
        aml_high_value_threshold=float(_get_env("AML_THRESHOLD", "10.0")),

        clustering_min_shared_counterparties=_get_int("CLUSTER_MIN_SHARED_COUNTERPARTIES", 3),
        clustering_temporal_window_seconds=_get_int("CLUSTER_TEMPORAL_WINDOW_SECONDS", 60),
        clustering_fan_threshold=_get_int("CLUSTER_FAN_THRESHOLD", 5),
        clustering_loop_max_depth=_get_int("CLUSTER_LOOP_MAX_DEPTH", 6),
    )