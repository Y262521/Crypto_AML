"""Connection helpers shared across MongoDB, MariaDB, and Neo4j."""

from typing import TYPE_CHECKING

from pymongo import MongoClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL

from ..config import Config, load_config

if TYPE_CHECKING:
    from neo4j import Driver


def get_mongo_client(cfg: Config | None = None) -> MongoClient:
    """Return a MongoDB client using configured URI."""
    cfg = cfg or load_config()
    return MongoClient(cfg.mongo_uri)


def get_mongo_collection(cfg: Config | None = None):
    """Return the configured raw-block MongoDB collection."""
    cfg = cfg or load_config()
    client = get_mongo_client(cfg)
    return client[cfg.mongo_raw_db][cfg.mongo_raw_collection]


def get_flat_transactions_mongo_collection(cfg: Config | None = None):
    """Return the MongoDB collection used for flattened raw transactions."""
    cfg = cfg or load_config()
    client = get_mongo_client(cfg)
    return client[cfg.mongo_flat_tx_db][cfg.mongo_flat_tx_collection]


def get_processed_mongo_collection(cfg: Config | None = None):
    """Return the MongoDB collection used to back up processed records."""
    cfg = cfg or load_config()
    client = get_mongo_client(cfg)
    return client[cfg.mongo_processed_db][cfg.mongo_processed_collection]


def get_maria_engine(
    cfg: Config | None = None,
    include_database: bool = True,
) -> Engine:
    """Return a SQLAlchemy engine for MariaDB."""
    cfg = cfg or load_config()
    database = cfg.mysql_db if include_database else None
    url = URL.create(
        "mysql+pymysql",
        username=cfg.mysql_user,
        password=cfg.mysql_password,
        host=cfg.mysql_host,
        port=cfg.mysql_port,
        database=database,
    )
    return create_engine(url, pool_pre_ping=True, future=True)


def get_neo4j_driver(cfg: Config | None = None) -> "Driver":
    """Return a Neo4j driver using configured credentials."""
    from neo4j import GraphDatabase

    cfg = cfg or load_config()
    return GraphDatabase.driver(cfg.neo4j_uri, auth=(cfg.neo4j_user, cfg.neo4j_password))
