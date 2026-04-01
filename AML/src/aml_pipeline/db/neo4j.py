"""Neo4j access helpers for graph relationships."""

import logging
from typing import Iterable

from neo4j import GraphDatabase

from ..config import Config

logger = logging.getLogger(__name__)


def get_driver(cfg: Config):
    """Create a Neo4j driver for the configured URI."""
    return GraphDatabase.driver(cfg.neo4j_uri, auth=(cfg.neo4j_user, cfg.neo4j_password))


def load_relationships(cfg: Config, rows: Iterable[dict]) -> int:
    """Upsert transaction relationships into Neo4j."""
    data = list(rows)
    if not data:
        return 0

    query = """
    UNWIND $rows AS row
    MERGE (s:Account {id: row.sender_id})
    MERGE (r:Account {id: row.receiver_id})
    MERGE (t:Transaction {tx_id: row.tx_id})
    SET t.event_time = row.event_time,
        t.amount_usd = row.amount_usd,
        t.currency = row.currency,
        t.btc_amount = row.btc_amount
    MERGE (s)-[:SENT]->(t)
    MERGE (t)-[:RECEIVED_BY]->(r)
    """

    driver = get_driver(cfg)
    try:
        with driver.session() as session:
            session.execute_write(lambda tx: tx.run(query, rows=data))
    finally:
        driver.close()

    return len(data)
