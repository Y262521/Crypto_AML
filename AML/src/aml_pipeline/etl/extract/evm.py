"""
Generic EVM Chain Extractor
============================
A single configurable extractor that handles all EVM-compatible chains:
  - Ethereum (already supported, now via this generic layer too)
  - BNB Chain
  - Polygon
  - Arbitrum
  - Base

No chain-specific code duplication. Pass a ChainConfig at construction
time and the extractor adapts automatically.

Architecture:
  EVMExtractor(chain_config)  →  fetch_block()  →  save_to_db()
                                 ↑                     ↑
                           Web3 RPC (Alchemy)     MongoDB raw_blocks
                                                  + raw_transactions (chain-tagged)

All raw documents are tagged with chain_name so multi-chain data can
coexist in the same MongoDB collections without collision.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

from pymongo import ReplaceOne
from web3 import Web3

from ...chains.registry import ChainConfig, get_chain
from ...config import Config, load_config
from ...utils.connections import (
    get_flat_transactions_mongo_collection,
    get_mongo_collection,
    get_mongo_client,
)
from .base import BaseExtractor
from .utils import build_flat_transaction_documents, rpc_call_with_retry, to_jsonable

logger = logging.getLogger(__name__)

_MAX_FETCH_BLOCKS_PER_RUN = 5


class EVMExtractor(BaseExtractor):
    """
    Generic extractor for any EVM-compatible chain.

    Pass a ChainConfig (from the registry) or a chain name string.
    The extractor uses the Alchemy RPC URL from either:
      1. The ChainConfig.rpc_url(api_key) method
      2. The cfg.eth_rpc_url fallback (for Ethereum backward-compat)

    All MongoDB documents are tagged with chain_name to allow
    multi-chain data to coexist in shared collections.
    """

    def __init__(
        self,
        cfg: Optional[Config] = None,
        chain: Optional[str | ChainConfig] = None,
        rpc_url: Optional[str] = None,
    ):
        super().__init__(cfg)

        # Resolve chain config
        if chain is None or chain == "ethereum":
            self.chain_config = get_chain("ethereum")
        elif isinstance(chain, str):
            self.chain_config = get_chain(chain)
        else:
            self.chain_config = chain

        # Resolve RPC URL: explicit override → env var → registry template
        self._rpc_url = self._resolve_rpc_url(rpc_url)

        # Web3 connection
        self.w3 = Web3(Web3.HTTPProvider(self._rpc_url))

        # Inject POA middleware for chains that use it (BNB, Polygon, Arbitrum)
        _POA_CHAINS = {"bnb", "polygon", "arbitrum", "base"}
        if self.chain_config.chain_name in _POA_CHAINS:
            try:
                from web3.middleware import ExtraDataToPOAMiddleware
                self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
            except ImportError:
                try:
                    from web3.middleware import geth_poa_middleware
                    self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
                except ImportError:
                    pass  # older web3 without POA middleware

        if not self.w3.is_connected():
            raise ConnectionError(
                f"Web3 provider not connected for chain {self.chain_config.chain_name}: "
                f"{self._rpc_url[:60]}…"
            )

        # MongoDB collections — shared, tagged by chain_name
        mongo_client = get_mongo_client(self.cfg)
        self.raw_collection = mongo_client[self.cfg.mongo_raw_db][self.cfg.mongo_raw_collection]
        self.transaction_collection = mongo_client[self.cfg.mongo_flat_tx_db][self.cfg.mongo_flat_tx_collection]
        self.collection = self.raw_collection

        self._prepare_collections()
        logger.info(
            "EVMExtractor ready: chain=%s  chain_id=%d  rpc=%s…",
            self.chain_config.chain_name,
            self.chain_config.chain_id,
            self._rpc_url[:50],
        )

    # ── Chain identity ────────────────────────────────────────────────────────

    @property
    def chain_name(self) -> str:
        return self.chain_config.chain_name

    @property
    def chain_id(self) -> int:
        return self.chain_config.chain_id

    @property
    def blockchain_type(self) -> str:
        return self.chain_config.blockchain_type

    @property
    def native_asset(self) -> str:
        return self.chain_config.native_asset

    # ── RPC URL resolution ────────────────────────────────────────────────────

    def _resolve_rpc_url(self, explicit_override: Optional[str]) -> str:
        """
        Priority order:
          1. explicit_override passed to constructor
          2. Chain-specific env var: {CHAIN_NAME_UPPER}_RPC (e.g. BNB_RPC)
          3. Chain-specific env var: {CHAIN_NAME_UPPER}_RPC_URL
          4. ALCHEMY_RPC (works for Ethereum; used as fallback for others too)
          5. Registry template filled with ALCHEMY_API_KEY
        """
        import os

        if explicit_override:
            return explicit_override

        chain_upper = self.chain_config.chain_name.upper().replace("-", "_")
        env_candidates = [
            f"{chain_upper}_RPC",
            f"{chain_upper}_RPC_URL",
        ]
        for env_var in env_candidates:
            val = os.getenv(env_var, "").strip()
            if val:
                return val

        # Ethereum fallback: use ALCHEMY_RPC directly
        if self.chain_config.chain_name == "ethereum":
            alchemy_rpc = os.getenv("ALCHEMY_RPC", "").strip()
            if alchemy_rpc:
                return alchemy_rpc

        # Generic: fill registry template with api key
        api_key = os.getenv("ALCHEMY_API_KEY", "").strip()
        if not api_key:
            # Try extracting key from existing ALCHEMY_RPC URL
            alchemy_rpc = os.getenv("ALCHEMY_RPC", "").strip()
            if "/v2/" in alchemy_rpc:
                api_key = alchemy_rpc.split("/v2/")[-1].strip("/")

        if api_key:
            return self.chain_config.rpc_url(api_key)

        # Last resort: return the template (will fail at connection but gives clear error)
        logger.warning(
            "No RPC URL found for chain %s. "
            "Set %s_RPC or ALCHEMY_API_KEY in .env",
            self.chain_config.chain_name,
            chain_upper,
        )
        return self.chain_config.rpc_url_template

    # ── MongoDB collection setup ──────────────────────────────────────────────

    def _prepare_collections(self) -> None:
        """Create MongoDB indexes for chain-tagged documents (idempotent)."""
        try:
            # Raw blocks: chain-scoped unique index on block_number
            self.raw_collection.create_index(
                [("chain_name", 1), ("block_number", 1)],
                unique=True,
                name=f"chain_block_unique_{self.chain_name}",
            )
            # Flat transactions: chain-scoped network + block index
            self.transaction_collection.create_index(
                [("network", 1), ("chain_name", 1), ("block.number", 1)],
                name="network_chain_block_idx",
            )
            self.transaction_collection.create_index(
                [("metadata.processed", 1), ("chain_name", 1), ("block.number", 1)],
                name="processed_chain_block_idx",
            )
        except Exception as exc:
            # Index creation failures are non-fatal (may already exist with different options)
            logger.debug("MongoDB index setup note: %s", exc)

    # ── Chain head ────────────────────────────────────────────────────────────

    def get_latest_block(self) -> int:
        """Return the latest block number from the chain's RPC."""
        return self.w3.eth.block_number

    def get_latest_saved_block(self) -> Optional[int]:
        """Return the latest block number already saved for this chain."""
        latest = self.raw_collection.find_one(
            {"chain_name": self.chain_name},
            sort=[("block_number", -1)],
        )
        if not latest:
            # For ethereum, also check legacy docs without chain_name
            if self.chain_name == "ethereum":
                latest = self.raw_collection.find_one(
                    {
                        "$or": [
                            {"chain_name": {"$exists": False}},
                            {"network": "ethereum-mainnet"},
                            {"network": "mainnet"},
                        ]
                    },
                    sort=[("block_number", -1)],
                )
        if not latest:
            return None
        block_num = int(latest.get("block_number", 0))
        # Sanity check: Solana slots are ~400M, ETH blocks are ~25M
        # If the returned value is unreasonably large for EVM, ignore it
        if self.blockchain_type == "EVM" and block_num > 100_000_000:
            return None
        return block_num

    # ── Block fetch ───────────────────────────────────────────────────────────

    def fetch_block(self, block_number: int) -> dict:
        """
        Fetch a full block with all receipts and logs from the EVM RPC.

        Returns a raw document dict tagged with chain identity fields.
        Structure mirrors the existing ETH raw document format so the
        transformer pipeline works unchanged.
        """
        block = rpc_call_with_retry(
            lambda: self.w3.eth.get_block(block_number, full_transactions=True)
        )

        receipts = []
        logs = []
        for tx in block["transactions"]:
            tx_hash = tx["hash"]
            receipt = rpc_call_with_retry(
                lambda: self.w3.eth.get_transaction_receipt(tx_hash)
            )
            receipts.append(receipt)
            logs.extend(receipt.get("logs", []))

        raw_document = {
            "block_number": block_number,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            # Chain identity — key addition vs original ETH extractor
            "chain_name": self.chain_name,
            "chain_id": self.chain_id,
            "blockchain_type": self.blockchain_type,
            "native_asset": self.native_asset,
            "network": self.chain_name,          # kept for backward-compat
            # Block data
            "transaction_count": len(block["transactions"]),
            "receipt_count": len(receipts),
            "log_count": len(logs),
            "block": block,
            "transactions": block["transactions"],
            "receipts": receipts,
            "logs": logs,
        }

        return to_jsonable(raw_document)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_flat_transaction_documents(
        self, block_number: int, flat_documents: list[dict]
    ) -> int:
        """Upsert chain-tagged flattened transaction docs."""
        tx_hashes = [doc["_id"] for doc in flat_documents]
        delete_query = {"chain_name": self.chain_name, "block.number": block_number}
        if tx_hashes:
            delete_query["_id"] = {"$nin": tx_hashes}
        self.transaction_collection.delete_many(delete_query)

        if flat_documents:
            ops = [
                ReplaceOne({"_id": doc["_id"]}, doc, upsert=True)
                for doc in flat_documents
            ]
            self.transaction_collection.bulk_write(ops, ordered=False)

        return len(flat_documents)

    def save_to_db(self, data: dict) -> int:
        """Upsert the raw block and its flattened transactions into MongoDB."""
        block_number = data.get("block_number")
        if block_number is None:
            raise ValueError("Raw block data is missing block_number")

        # Upsert raw block (chain-scoped)
        self.raw_collection.replace_one(
            {"chain_name": self.chain_name, "block_number": block_number},
            data,
            upsert=True,
        )

        # Build and save flat transaction docs (chain-tagged)
        flat_documents = build_flat_transaction_documents(data, self.chain_name)
        # Stamp chain identity on each flat doc
        for doc in flat_documents:
            doc["chain_name"]      = self.chain_name
            doc["chain_id"]        = self.chain_id
            doc["blockchain_type"] = self.blockchain_type
            doc["native_asset"]    = self.native_asset

        return self._save_flat_transaction_documents(block_number, flat_documents)

    # ── Main fetch loop ───────────────────────────────────────────────────────

    def fetch_and_store_raw(
        self,
        start_block: Optional[int] = None,
        batch: Optional[int] = None,
    ) -> Tuple[int, int]:
        """
        Fetch a batch of blocks and store them.

        Uses chain-specific start block from env/config if start_block is None.
        Falls back to cfg.eth_start_block for Ethereum (backward-compat).
        """
        import os

        latest_saved = self.get_latest_saved_block()

        if start_block is None:
            if latest_saved is not None:
                start_block = latest_saved + 1
            else:
                # Chain-specific env var: {CHAIN_NAME_UPPER}_START_BLOCK
                chain_upper = self.chain_name.upper().replace("-", "_")
                env_start = os.getenv(f"{chain_upper}_START_BLOCK", "").strip()
                if env_start and env_start.isdigit():
                    start_block = int(env_start)
                else:
                    start_block = self.cfg.eth_start_block

        batch_size = batch or self.cfg.eth_batch_size
        if batch_size > _MAX_FETCH_BLOCKS_PER_RUN:
            logger.warning(
                "[%s] Batch size capped at %d (requested %d)",
                self.chain_name, _MAX_FETCH_BLOCKS_PER_RUN, batch_size,
            )
            batch_size = _MAX_FETCH_BLOCKS_PER_RUN

        latest_available = self.get_latest_block()
        if start_block > latest_available:
            logger.info(
                "[%s] No new blocks (start=%d, latest=%d)",
                self.chain_name, start_block, latest_available,
            )
            return start_block, latest_available

        from_block = start_block
        to_block = min(from_block + batch_size - 1, latest_available)

        logger.info("[%s] Fetching blocks %d → %d", self.chain_name, from_block, to_block)

        total_transactions = 0
        for block_number in range(from_block, to_block + 1):
            raw_data = self.fetch_block(block_number)
            self.save_to_local_backup(raw_data, block_number)
            flattened_count = self.save_to_db(raw_data)
            total_transactions += flattened_count
            logger.info(
                "[%s] Saved block %d: %d txs",
                self.chain_name, block_number, flattened_count,
            )

        fetched_blocks = to_block - from_block + 1
        msg = (
            f"[{self.chain_name}] Saved blocks {from_block} → {to_block} "
            f"({fetched_blocks} blocks, {total_transactions} txs)"
        )
        print(msg)
        logger.info(msg)
        time.sleep(0.2)

        return from_block, to_block


# ── Convenience factory ───────────────────────────────────────────────────────

def get_evm_extractor(
    chain_name: str,
    cfg: Optional[Config] = None,
    rpc_url: Optional[str] = None,
) -> EVMExtractor:
    """
    Create an EVMExtractor for any supported EVM chain by name.

    Examples:
        eth = get_evm_extractor("ethereum")
        bnb = get_evm_extractor("bnb")
        poly = get_evm_extractor("polygon")
    """
    return EVMExtractor(cfg=cfg, chain=chain_name, rpc_url=rpc_url)
