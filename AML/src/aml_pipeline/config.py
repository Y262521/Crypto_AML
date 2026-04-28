import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

def _get_env(*names: str, default: Optional[str] = None):
    for name in names:
        value = os.getenv(name)
        if value not in (None, ""):
            return value
    return default

def _get_int(*names: str, default: int) -> int:
    try:
        return int(_get_env(*names, default=str(default)))
    except (TypeError, ValueError):
        return default


def _get_float(*names: str, default: float) -> float:
    try:
        return float(_get_env(*names, default=str(default)))
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

    # Pipeline
    eth_rpc_url: str
    eth_network: str
    eth_start_block: int
    eth_batch_size: int
    batch_size: int
    batch_size_transform: int
    high_value_threshold_eth: float

    # Wallet clustering
    clustering_min_shared_counterparties: int
    clustering_temporal_window_seconds: int
    clustering_fan_threshold: int
    clustering_loop_max_depth: int
    clustering_min_transfer_value_eth: float
    clustering_min_heuristic_support: int
    clustering_min_cluster_size: int
    clustering_cashout_window_seconds: int
    clustering_pass_through_window_seconds: int
    clustering_amount_similarity_ratio: float
    clustering_forwarding_value_tolerance_eth: float
    clustering_max_pattern_size: int

    # Placement analytics
    placement_structuring_window_minutes: int
    placement_structuring_min_tx_count: int
    placement_structuring_max_relative_variance: float
    placement_smurfing_min_unique_senders: int
    placement_smurfing_max_wallet_age_seconds: int
    placement_micro_max_tx_eth: float
    placement_micro_min_tx_count: int
    placement_micro_min_total_eth: float
    placement_origin_max_hops: int
    placement_origin_branching_limit: int
    placement_origin_service_tx_count: int
    placement_origin_service_degree: int

    # Layering analytics
    layering_service_profile_path: str
    layering_min_seed_confidence: float
    layering_service_tx_count: int
    layering_service_degree: int
    layering_peel_min_hops: int
    layering_peel_max_hops: int
    layering_peel_min_decay_ratio: float
    layering_peel_min_fragment_ratio: float
    layering_peel_max_fragment_ratio: float
    layering_peel_max_time_gap_seconds: int
    layering_mixing_min_interactions: int
    layering_mixing_min_repeated_denominations: int
    layering_mixing_max_time_gap_seconds: int
    layering_mixing_min_ego_density: float
    layering_bridge_amount_tolerance_ratio: float
    layering_bridge_max_latency_seconds: int
    layering_bridge_min_pairs: int
    layering_shell_window_seconds: int
    layering_shell_min_community_size: int
    layering_shell_min_internal_ratio: float
    layering_shell_min_density: float
    layering_shell_min_temporal_windows: int
    layering_depth_max_hops: int
    layering_depth_min_hops: int
    layering_depth_branching_limit: int
    layering_depth_min_value_retention: float
    layering_depth_max_latency_seconds: int
    layering_depth_min_score: float


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
        log_level=_get_env("LOG_LEVEL", default="INFO"),

        mongo_uri=_get_env("MONGO_URI", default="mongodb://localhost:27017"),
        mongo_raw_db=_get_env("MONGO_RAW_DB", "MONGO_DB", default="aml_raw"),
        mongo_raw_collection=_get_env("MONGO_RAW_COLLECTION", "MONGO_COLLECTION", default="raw_blocks"),
        mongo_flat_tx_db=_get_env("MONGO_FLAT_TX_DB", "MONGO_FLAT_DB", "MONGO_DB", default="aml_raw"),
        mongo_flat_tx_collection=_get_env(
            "MONGO_FLAT_TX_COLLECTION",
            "MONGO_FLAT_COLLECTION",
            default="raw_transactions",
        ),
        mongo_processed_db=_get_env("MONGO_PROCESSED_DB", "MONGO_DB", default="aml_raw"),
        mongo_processed_collection=_get_env(
            "MONGO_PROCESSED_COLLECTION",
            default="processed_transactions",
        ),

        mysql_host=_get_env("MYSQL_HOST", default="localhost"),
        mysql_port=_get_int("MYSQL_PORT", default=3306),
        mysql_user=_get_env("MYSQL_USER", default="hakim"),
        mysql_password=_get_env("MYSQL_PASSWORD", default="hakim22"),
        mysql_db=_get_env("MYSQL_DB", default="aml_db"),

        neo4j_uri=_get_env("NEO4J_URI", default="bolt://localhost:7687"),
        neo4j_user=_get_env("NEO4J_USER", default="neo4j"),
        neo4j_password=_get_env("NEO4J_PASSWORD", default="hakimaj22"),
        neo4j_database=_get_env("NEO4J_DATABASE", default="neo4j"),
        neo4j_batch_size=_get_int("NEO4J_BATCH_SIZE", default=500),

        eth_rpc_url=_get_env(
            "ALCHEMY_RPC",
            "RPC_URL",
            "PYTHON_RPC_URL",
            default="https://ethereum-rpc.publicnode.com",
        ),
        eth_network=_get_env("ETH_NETWORK", default="mainnet"),
        eth_start_block=_get_int("ETH_START_BLOCK", default=23849990),
        eth_batch_size=_get_int("ETH_BATCH_SIZE", "BATCH_SIZE", default=10),
        batch_size=_get_int("BATCH_SIZE", default=1000),
        batch_size_transform=_get_int("BATCH_SIZE_TRANSFORM", "TRANSFORM_BATCH_SIZE", default=300),
        high_value_threshold_eth=_get_float(
            "HIGH_VALUE_THRESHOLD_ETH",
            "AML_HIGH_VALUE_THRESHOLD",
            "AML_THRESHOLD",
            default=10.0,
        ),

        clustering_min_shared_counterparties=_get_int("CLUSTER_MIN_SHARED_COUNTERPARTIES", default=3),
        clustering_temporal_window_seconds=_get_int("CLUSTER_TEMPORAL_WINDOW_SECONDS", default=60),
        clustering_fan_threshold=_get_int("CLUSTER_FAN_THRESHOLD", default=5),
        clustering_loop_max_depth=_get_int("CLUSTER_LOOP_MAX_DEPTH", default=6),
        clustering_min_transfer_value_eth=_get_float("CLUSTER_MIN_TRANSFER_VALUE_ETH", default=0.001),
        clustering_min_heuristic_support=_get_int("CLUSTER_MIN_HEURISTIC_SUPPORT", default=1),
        clustering_min_cluster_size=_get_int("CLUSTER_MIN_CLUSTER_SIZE", default=2),
        clustering_cashout_window_seconds=_get_int("CLUSTER_CASHOUT_WINDOW_SECONDS", default=300),
        clustering_pass_through_window_seconds=_get_int("CLUSTER_PASS_THROUGH_WINDOW_SECONDS", default=1800),
        clustering_amount_similarity_ratio=_get_float("CLUSTER_AMOUNT_SIMILARITY_RATIO", default=0.05),
        clustering_forwarding_value_tolerance_eth=_get_float(
            "CLUSTER_FORWARDING_VALUE_TOLERANCE_ETH",
            default=0.01,
        ),
        clustering_max_pattern_size=_get_int("CLUSTER_MAX_PATTERN_SIZE", default=100),

        placement_structuring_window_minutes=_get_int(
            "PLACEMENT_STRUCTURING_WINDOW_MINUTES",
            default=30,
        ),
        placement_structuring_min_tx_count=_get_int(
            "PLACEMENT_STRUCTURING_MIN_TX_COUNT",
            default=4,
        ),
        placement_structuring_max_relative_variance=_get_float(
            "PLACEMENT_STRUCTURING_MAX_RELATIVE_VARIANCE",
            default=0.05,
        ),
        placement_smurfing_min_unique_senders=_get_int(
            "PLACEMENT_SMURFING_MIN_UNIQUE_SENDERS",
            default=6,
        ),
        placement_smurfing_max_wallet_age_seconds=_get_int(
            "PLACEMENT_SMURFING_MAX_WALLET_AGE_SECONDS",
            default=604800,
        ),
        placement_micro_max_tx_eth=_get_float(
            "PLACEMENT_MICRO_MAX_TX_ETH",
            default=0.1,
        ),
        placement_micro_min_tx_count=_get_int(
            "PLACEMENT_MICRO_MIN_TX_COUNT",
            default=8,
        ),
        placement_micro_min_total_eth=_get_float(
            "PLACEMENT_MICRO_MIN_TOTAL_ETH",
            default=1.0,
        ),
        placement_origin_max_hops=_get_int(
            "PLACEMENT_ORIGIN_MAX_HOPS",
            default=3,
        ),
        placement_origin_branching_limit=_get_int(
            "PLACEMENT_ORIGIN_BRANCHING_LIMIT",
            default=3,
        ),
        placement_origin_service_tx_count=_get_int(
            "PLACEMENT_ORIGIN_SERVICE_TX_COUNT",
            default=200,
        ),
        placement_origin_service_degree=_get_int(
            "PLACEMENT_ORIGIN_SERVICE_DEGREE",
            default=25,
        ),
        layering_service_profile_path=_get_env(
            "LAYERING_SERVICE_PROFILE_PATH",
            default="",
        ),
        layering_min_seed_confidence=_get_float(
            "LAYERING_MIN_SEED_CONFIDENCE",
            default=0.55,
        ),
        layering_service_tx_count=_get_int(
            "LAYERING_SERVICE_TX_COUNT",
            default=200,
        ),
        layering_service_degree=_get_int(
            "LAYERING_SERVICE_DEGREE",
            default=25,
        ),
        layering_peel_min_hops=_get_int(
            "LAYERING_PEEL_MIN_HOPS",
            default=3,
        ),
        layering_peel_max_hops=_get_int(
            "LAYERING_PEEL_MAX_HOPS",
            default=6,
        ),
        layering_peel_min_decay_ratio=_get_float(
            "LAYERING_PEEL_MIN_DECAY_RATIO",
            default=0.02,
        ),
        layering_peel_min_fragment_ratio=_get_float(
            "LAYERING_PEEL_MIN_FRAGMENT_RATIO",
            default=0.01,
        ),
        layering_peel_max_fragment_ratio=_get_float(
            "LAYERING_PEEL_MAX_FRAGMENT_RATIO",
            default=0.35,
        ),
        layering_peel_max_time_gap_seconds=_get_int(
            "LAYERING_PEEL_MAX_TIME_GAP_SECONDS",
            default=7200,
        ),
        layering_mixing_min_interactions=_get_int(
            "LAYERING_MIXING_MIN_INTERACTIONS",
            default=2,
        ),
        layering_mixing_min_repeated_denominations=_get_int(
            "LAYERING_MIXING_MIN_REPEATED_DENOMINATIONS",
            default=2,
        ),
        layering_mixing_max_time_gap_seconds=_get_int(
            "LAYERING_MIXING_MAX_TIME_GAP_SECONDS",
            default=21600,
        ),
        layering_mixing_min_ego_density=_get_float(
            "LAYERING_MIXING_MIN_EGO_DENSITY",
            default=0.18,
        ),
        layering_bridge_amount_tolerance_ratio=_get_float(
            "LAYERING_BRIDGE_AMOUNT_TOLERANCE_RATIO",
            default=0.03,
        ),
        layering_bridge_max_latency_seconds=_get_int(
            "LAYERING_BRIDGE_MAX_LATENCY_SECONDS",
            default=86400,
        ),
        layering_bridge_min_pairs=_get_int(
            "LAYERING_BRIDGE_MIN_PAIRS",
            default=1,
        ),
        layering_shell_window_seconds=_get_int(
            "LAYERING_SHELL_WINDOW_SECONDS",
            default=43200,
        ),
        layering_shell_min_community_size=_get_int(
            "LAYERING_SHELL_MIN_COMMUNITY_SIZE",
            default=4,
        ),
        layering_shell_min_internal_ratio=_get_float(
            "LAYERING_SHELL_MIN_INTERNAL_RATIO",
            default=0.72,
        ),
        layering_shell_min_density=_get_float(
            "LAYERING_SHELL_MIN_DENSITY",
            default=0.28,
        ),
        layering_shell_min_temporal_windows=_get_int(
            "LAYERING_SHELL_MIN_TEMPORAL_WINDOWS",
            default=2,
        ),
        layering_depth_max_hops=_get_int(
            "LAYERING_DEPTH_MAX_HOPS",
            default=6,
        ),
        layering_depth_min_hops=_get_int(
            "LAYERING_DEPTH_MIN_HOPS",
            default=4,
        ),
        layering_depth_branching_limit=_get_int(
            "LAYERING_DEPTH_BRANCHING_LIMIT",
            default=3,
        ),
        layering_depth_min_value_retention=_get_float(
            "LAYERING_DEPTH_MIN_VALUE_RETENTION",
            default=0.55,
        ),
        layering_depth_max_latency_seconds=_get_int(
            "LAYERING_DEPTH_MAX_LATENCY_SECONDS",
            default=86400,
        ),
        layering_depth_min_score=_get_float(
            "LAYERING_DEPTH_MIN_SCORE",
            default=0.58,
        ),
    )
