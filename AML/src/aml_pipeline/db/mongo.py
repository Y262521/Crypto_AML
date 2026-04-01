"""MongoDB access helpers for flattened raw transaction data."""

import logging
from datetime import datetime
from typing import Iterable, Optional

from ..config import Config
from ..utils.connections import get_flat_transactions_mongo_collection

logger = logging.getLogger(__name__)


def get_collection(cfg: Config):
    """Return the configured flattened-transaction MongoDB collection."""
    return get_flat_transactions_mongo_collection(cfg)


def fetch_transactions(
    cfg: Config,
    since_dt: Optional[datetime] = None,
) -> Iterable[dict]:
    """Stream flattened transaction documents from MongoDB, optionally filtered by time."""
    collection = get_collection(cfg)
    query = {}
    if since_dt is not None:
        query = {"block.timestamp": {"$gt": since_dt}}
        logger.info("Extracting flattened transactions since %s", since_dt.isoformat())
    else:
        logger.info("Extracting all flattened transactions")

    cursor = collection.find(query).sort([("block.number", 1), ("forensics.transaction_index", 1)]).batch_size(
        cfg.batch_size
    )
    for doc in cursor:
        doc["_id"] = str(doc.get("_id"))
        yield doc
