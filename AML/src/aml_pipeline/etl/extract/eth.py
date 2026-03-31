"""Ethereum raw block extractor implementation."""

import logging
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

from pymongo import ReplaceOne

from .base import BaseExtractor
from .connections import (
    get_flat_transaction_collection,
    get_raw_collection,
    get_web3,
    prepare_extraction_collections,
)
from .utils import build_flat_transaction_documents, rpc_call_with_retry, to_jsonable

logger = logging.getLogger(__name__)


class EthereumExtractor(BaseExtractor):
    """Ethereum-specific extractor that pulls blocks, txs, receipts, and logs."""

    def __init__(self, cfg=None):
        """Initialize Web3 and Mongo connections."""
        super().__init__(cfg)
        self.w3 = get_web3(self.cfg)
        self.raw_collection = get_raw_collection(self.cfg)
        self.transaction_collection = get_flat_transaction_collection(self.cfg)
        self.collection = self.raw_collection
        prep_summary = prepare_extraction_collections(self.cfg)
        if prep_summary["duplicate_docs_deleted"] > 0:
            logger.warning(
                "Deleted %s duplicate raw block documents before extraction",
                prep_summary["duplicate_docs_deleted"],
            )

    def get_latest_block(self) -> int:
        """Return the latest Ethereum block number from the RPC."""
        return self.w3.eth.block_number

    def get_latest_saved_block(self) -> Optional[int]:
        """Return the latest block number already saved to MongoDB."""
        latest = self.raw_collection.find_one(sort=[("block_number", -1)])
        if not latest:
            return None
        return int(latest.get("block_number"))

    def _save_flat_transaction_documents(self, block_number: int, flat_documents: list[dict]) -> int:
        """Upsert flattened transaction documents for a single block."""
        tx_hashes = [document["_id"] for document in flat_documents]
        delete_query = {"block.number": block_number}
        if tx_hashes:
            delete_query["_id"] = {"$nin": tx_hashes}
        self.transaction_collection.delete_many(delete_query)

        if flat_documents:
            operations = [
                ReplaceOne({"_id": document["_id"]}, document, upsert=True)
                for document in flat_documents
            ]
            self.transaction_collection.bulk_write(operations, ordered=False)

        return len(flat_documents)

    def fetch_block(self, block_number: int) -> dict:
        """Fetch a full block, receipts, and logs as a raw document."""
        block = rpc_call_with_retry(lambda: self.w3.eth.get_block(block_number, full_transactions=True))

        receipts = []
        logs = []
        for tx in block["transactions"]:
            tx_hash = tx["hash"]
            receipt = rpc_call_with_retry(lambda: self.w3.eth.get_transaction_receipt(tx_hash))
            receipts.append(receipt)
            logs.extend(receipt.get("logs", []))

        raw_document = {
            "block_number": block_number,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "network": self.cfg.eth_network,
            "transaction_count": len(block["transactions"]),
            "receipt_count": len(receipts),
            "log_count": len(logs),
            "block": block,
            "transactions": block["transactions"],
            "receipts": receipts,
            "logs": logs,
        }

        return to_jsonable(raw_document)

    def save_to_db(self, data: dict) -> int:
        """Upsert the raw block and its flattened transactions into MongoDB."""
        block_number = data.get("block_number")
        if block_number is None:
            raise ValueError("Raw block data is missing block_number")
        self.raw_collection.replace_one({"block_number": block_number}, data, upsert=True)

        flat_documents = build_flat_transaction_documents(data, self.cfg.eth_network)
        return self._save_flat_transaction_documents(block_number, flat_documents)

    def fetch_and_store_raw(
        self,
        start_block: Optional[int] = None,
        batch: Optional[int] = None,
    ) -> Tuple[int, int]:
        """Fetch a batch of blocks and store them in MongoDB + local backup."""
        latest_saved = self.get_latest_saved_block()
        if start_block is None:
            start_block = (latest_saved + 1) if latest_saved is not None else self.cfg.eth_start_block

        batch_size = batch or self.cfg.eth_batch_size
        if batch_size > 100:
            logger.warning("Batch size capped at 100 (requested %s)", batch_size)
            batch_size = 100

        from_block = start_block
        to_block = from_block + batch_size - 1

        logger.info("Fetching blocks %s -> %s", from_block, to_block)

        total_transactions = 0
        for block_number in range(from_block, to_block + 1):
            raw_data = self.fetch_block(block_number)
            # Save backup before Mongo insert to avoid _id serialization issues.
            self.save_to_local_backup(raw_data, block_number)
            flattened_count = self.save_to_db(raw_data)
            total_transactions += flattened_count
            logger.info(
                "Saved block %s with %s txs to raw_blocks and %s flattened tx docs",
                block_number,
                len(raw_data.get("transactions", [])),
                flattened_count,
            )

        message = f"Saved blocks {from_block} -> {to_block} ({batch_size} blocks)"
        print(message)
        logger.info(message)
        logger.info("Saved %s flattened transaction documents", total_transactions)
        time.sleep(0.2)

        return from_block, to_block


def test_connection(cfg=None) -> None:
    """Quick health check for Web3 + Mongo connections."""
    extractor = EthereumExtractor(cfg)
    _ = extractor.get_latest_block()
    _ = extractor.collection
    logger.info("Web3 and MongoDB connections look healthy")


def backfill_flat_transactions_from_raw_blocks(
    cfg=None,
    start_block: Optional[int] = None,
    end_block: Optional[int] = None,
) -> dict:
    """Populate the flattened raw transaction collection from existing raw block docs."""
    extractor = EthereumExtractor(cfg)
    query = {}
    if start_block is not None and end_block is not None:
        query["block_number"] = {"$gte": start_block, "$lte": end_block}

    summary = {"blocks_processed": 0, "transactions_written": 0}
    cursor = extractor.raw_collection.find(query).sort("block_number", 1)
    for raw_block in cursor:
        block_number = raw_block.get("block_number")
        if block_number is None:
            continue
        flat_documents = build_flat_transaction_documents(raw_block, extractor.cfg.eth_network)
        summary["transactions_written"] += extractor._save_flat_transaction_documents(
            block_number,
            flat_documents,
        )
        summary["blocks_processed"] += 1

    logger.info(
        "Backfilled %s flattened transactions from %s raw blocks",
        summary["transactions_written"],
        summary["blocks_processed"],
    )
    return summary
