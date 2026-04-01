"""Connection helpers for extractor RPC and MongoDB."""

from __future__ import annotations

from web3 import Web3

from ...config import Config, load_config
from ...utils.connections import (
    get_flat_transactions_mongo_collection,
    get_mongo_collection,
)


def get_web3(cfg: Config | None = None) -> Web3:
    """Create and validate a Web3 client for the configured RPC."""
    cfg = cfg or load_config()
    w3 = Web3(Web3.HTTPProvider(cfg.eth_rpc_url))
    if not w3.is_connected():
        raise ConnectionError("Web3 provider not connected")
    return w3


def get_raw_collection(cfg: Config | None = None):
    """Return the MongoDB collection used for raw blocks."""
    cfg = cfg or load_config()
    return get_mongo_collection(cfg)


def get_flat_transaction_collection(cfg: Config | None = None):
    """Return the MongoDB collection used for flattened raw transactions."""
    cfg = cfg or load_config()
    return get_flat_transactions_mongo_collection(cfg)


def _has_unique_block_index(collection) -> bool:
    """Return whether the raw block collection already enforces unique block numbers."""
    for index in collection.index_information().values():
        if index.get("key") == [("block_number", 1)] and index.get("unique"):
            return True
    return False


def _deduplicate_raw_blocks(collection) -> int:
    """Delete duplicate raw block documents while keeping the newest copy per block."""
    deleted = 0
    pipeline = [
        {
            "$group": {
                "_id": "$block_number",
                "documents": {
                    "$push": {
                        "_id": "$_id",
                        "fetched_at": "$fetched_at",
                    }
                },
                "count": {"$sum": 1},
            }
        },
        {"$match": {"count": {"$gt": 1}}},
    ]

    for group in collection.aggregate(pipeline):
        documents = sorted(
            group["documents"],
            key=lambda document: (
                document.get("fetched_at") or "",
                str(document["_id"]),
            ),
        )
        duplicate_ids = [document["_id"] for document in documents[:-1]]
        if not duplicate_ids:
            continue
        deleted += collection.delete_many({"_id": {"$in": duplicate_ids}}).deleted_count

    return deleted


def prepare_raw_collection(cfg: Config | None = None) -> dict:
    """Create indexes and clean legacy duplicates so raw block storage stays idempotent."""
    collection = get_raw_collection(cfg)
    duplicate_docs_deleted = 0

    if not _has_unique_block_index(collection):
        duplicate_docs_deleted = _deduplicate_raw_blocks(collection)
        collection.create_index("block_number", unique=True, name="block_number_unique")

    collection.create_index(
        [("transformed", 1), ("block_number", 1)],
        name="transformed_block_number_idx",
    )

    return {"duplicate_docs_deleted": duplicate_docs_deleted}


def prepare_flat_transaction_collection(cfg: Config | None = None) -> None:
    """Create the indexes used by the flattened raw transaction collection."""
    collection = get_flat_transaction_collection(cfg)
    collection.create_index([("network", 1), ("block.number", 1)], name="network_block_number_idx")
    collection.create_index([("metadata.processed", 1), ("block.number", 1)], name="processed_block_number_idx")
    collection.create_index("block.timestamp", name="block_timestamp_idx")
    collection.create_index("address_pair.from", name="address_from_idx")
    collection.create_index("address_pair.to", name="address_to_idx")
    collection.create_index("forensics.method_id", name="method_id_idx")


def prepare_extraction_collections(cfg: Config | None = None) -> dict:
    """Prepare both raw-block and flattened-transaction MongoDB collections."""
    summary = prepare_raw_collection(cfg)
    prepare_flat_transaction_collection(cfg)
    return summary
