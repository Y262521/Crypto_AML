"""
Generic UTXO Chain Extractor
==============================
Handles all UTXO-based chains via Alchemy's blockchain REST API:
  - Bitcoin (BTC)
  - Litecoin (LTC)
  - Dogecoin (DOGE)
  - Bitcoin Cash (BCH)

UTXO transactions differ fundamentally from EVM:
  - One transaction has MULTIPLE inputs (senders) and MULTIPLE outputs (receivers)
  - There is no single from_address / to_address
  - We explode each UTXO tx into N×M TxRecord rows (one per input→output pair)
    so the rest of the pipeline (clustering, AML) works unchanged

Alchemy UTXO API endpoints used:
  GET /v2/{network}/block/{block_hash_or_number}
  GET /v2/{network}/transaction/{txid}
  GET /v2/{network}/getblockcount  (chain head)

All raw docs are stored in the shared MongoDB raw_blocks collection
tagged with chain_name so multi-chain data coexists cleanly.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

from pymongo import ReplaceOne

from ...chains.registry import ChainConfig, get_chain, BLOCKCHAIN_TYPE_UTXO
from ...config import Config, load_config
from ...utils.connections import get_mongo_client
from .base import BaseExtractor

logger = logging.getLogger(__name__)

_MAX_FETCH_BLOCKS_PER_RUN = 3   # UTXO blocks can be huge — be conservative
_REQUEST_TIMEOUT = 90           # seconds — increased for large tx responses


class UTXOExtractor(BaseExtractor):
    """
    Generic UTXO chain extractor using Alchemy's blockchain REST API.

    Fetches blocks + transactions, normalises UTXO inputs/outputs into
    the same raw document format used by EVM extractors (chain-tagged),
    and explodes each tx into input→output TxRecord pairs for downstream.
    """

    def __init__(
        self,
        cfg: Optional[Config] = None,
        chain: Optional[str | ChainConfig] = None,
        rpc_url: Optional[str] = None,
    ):
        super().__init__(cfg)

        # Resolve chain config
        if chain is None or chain == "bitcoin":
            self.chain_config = get_chain("bitcoin")
        elif isinstance(chain, str):
            self.chain_config = get_chain(chain)
        else:
            self.chain_config = chain

        if self.chain_config.blockchain_type != BLOCKCHAIN_TYPE_UTXO:
            raise ValueError(
                f"UTXOExtractor requires a UTXO chain, got: "
                f"{self.chain_config.chain_name} ({self.chain_config.blockchain_type})"
            )

        self._api_base = self._resolve_api_base(rpc_url)

        # MongoDB — shared collections tagged by chain_name
        mongo_client = get_mongo_client(self.cfg)
        self.raw_collection = mongo_client[self.cfg.mongo_raw_db][self.cfg.mongo_raw_collection]
        self.transaction_collection = mongo_client[self.cfg.mongo_flat_tx_db][self.cfg.mongo_flat_tx_collection]
        self.collection = self.raw_collection

        self._prepare_collections()
        logger.info(
            "UTXOExtractor ready: chain=%s  api=%s…",
            self.chain_config.chain_name,
            self._api_base[:60],
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
        return BLOCKCHAIN_TYPE_UTXO

    @property
    def native_asset(self) -> str:
        return self.chain_config.native_asset

    # ── API URL resolution ────────────────────────────────────────────────────

    def _resolve_api_base(self, explicit: Optional[str]) -> str:
        """
        Build the Alchemy REST API base URL for this UTXO chain.

        Alchemy UTXO hostname pattern:
          https://bitcoin-mainnet.g.alchemy.com/v2/{api_key}
          https://litecoin-mainnet.g.alchemy.com/v2/{api_key}
          https://dogecoin-mainnet.g.alchemy.com/v2/{api_key}
          https://bitcoincash-mainnet.g.alchemy.com/v2/{api_key}

        Env var names (checked in order):
          BITCOIN_RPC, LITECOIN_RPC, DOGECOIN_RPC, BITCOINCASH_RPC
        """
        import os

        if explicit:
            return explicit

        # Map chain_name → env var name
        env_var_map = {
            "bitcoin":      "BITCOIN_RPC",
            "litecoin":     "LITECOIN_RPC",
            "dogecoin":     "DOGECOIN_RPC",
            "bitcoin_cash": "BITCOINCASH_RPC",
        }

        # Try the canonical env var first
        canonical_env = env_var_map.get(self.chain_name)
        if canonical_env:
            val = os.getenv(canonical_env, "").strip()
            if val:
                return val

        # Fallback: try generic uppercase pattern
        chain_upper = self.chain_name.upper().replace("_", "")
        for env_var in [f"{chain_upper}_RPC", f"{chain_upper}_API_URL"]:
            val = os.getenv(env_var, "").strip()
            if val:
                return val

        # Derive from ALCHEMY_API_KEY using Alchemy's full hostname
        alchemy_hostname_map = {
            "bitcoin":      "bitcoin-mainnet",
            "litecoin":     "litecoin-mainnet",
            "dogecoin":     "dogecoin-mainnet",
            "bitcoin_cash": "bitcoincash-mainnet",
        }
        api_key = os.getenv("ALCHEMY_API_KEY", "").strip()
        if not api_key:
            alchemy_rpc = os.getenv("ALCHEMY_RPC", "").strip()
            if "/v2/" in alchemy_rpc:
                api_key = alchemy_rpc.split("/v2/")[-1].strip("/")

        if api_key:
            hostname = alchemy_hostname_map.get(self.chain_name, f"{self.chain_name}-mainnet")
            return f"https://{hostname}.g.alchemy.com/v2/{api_key}"

        logger.warning(
            "No API URL for UTXO chain %s. Set %s in .env",
            self.chain_name, canonical_env or f"{chain_upper}_RPC",
        )
        return self.chain_config.rpc_url_template

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _get(self, path: str, retries: int = 3) -> dict:
        """
        POST JSON-RPC to Alchemy UTXO endpoint.
        Alchemy UTXO uses Bitcoin-Core-compatible JSON-RPC over POST,
        not REST GET endpoints.
        """
        # Extract method name from path (e.g. "getblockcount" → method)
        method = path.split("?")[0].strip("/")
        return self._rpc(method, [], retries=retries)

    def _rpc(self, method: str, params: list, retries: int = 3) -> dict:
        """POST a Bitcoin-Core-compatible JSON-RPC request to Alchemy UTXO API."""
        import urllib.request, urllib.error
        payload = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }).encode()
        req = urllib.request.Request(
            self._api_base,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as r:
                    data = json.loads(r.read())
                    if "error" in data and data["error"]:
                        err = data["error"]
                        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                        raise RuntimeError(f"RPC error: {msg}")
                    return data.get("result", {})
            except urllib.error.HTTPError as e:
                last_exc = e
                if e.code == 429:
                    wait = 2 ** attempt
                    logger.warning("[%s] Rate limited, waiting %ds", self.chain_name, wait)
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"[{self.chain_name}] HTTP {e.code}") from e
            except RuntimeError:
                raise
            except Exception as exc:
                last_exc = exc
                logger.warning("[%s] RPC attempt %d failed: %s", self.chain_name, attempt, exc)
                time.sleep(1.0 * attempt)
        raise RuntimeError(
            f"[{self.chain_name}] RPC {method} failed after {retries} attempts: {last_exc}"
        )

    # ── MongoDB collection setup ──────────────────────────────────────────────

    def _prepare_collections(self) -> None:
        try:
            self.raw_collection.create_index(
                [("chain_name", 1), ("block_number", 1)],
                unique=True,
                name=f"utxo_chain_block_{self.chain_name}",
            )
            self.transaction_collection.create_index(
                [("chain_name", 1), ("block.number", 1)],
                name=f"utxo_chain_block_tx_{self.chain_name}",
            )
        except Exception as exc:
            logger.debug("[%s] MongoDB index note: %s", self.chain_name, exc)

    # ── Chain head ────────────────────────────────────────────────────────────

    def get_latest_block(self) -> int:
        """Return the current chain tip block height."""
        result = self._rpc("getblockcount", [])
        return int(result)

    def get_latest_saved_block(self) -> Optional[int]:
        latest = self.raw_collection.find_one(
            {"chain_name": self.chain_name},
            sort=[("block_number", -1)],
        )
        if not latest:
            return None
        return int(latest.get("block_number"))

    # ── UTXO normalisation ────────────────────────────────────────────────────

    @staticmethod
    def _satoshis_to_native(satoshis: float | int | None) -> float:
        """Convert satoshis (or smallest unit) to native asset units."""
        if satoshis is None:
            return 0.0
        return float(satoshis) / 1e8

    def _extract_input_addresses(self, vin: list[dict]) -> list[dict]:
        """
        Extract sender reference from UTXO inputs.
        Uses prev_txid:vout as a synthetic identifier since Alchemy
        does not return input addresses inline. The CIO heuristic groups
        by tx_hash so actual address resolution is not needed for clustering.
        """
        inputs = []
        for inp in vin[:10]:
            if inp.get("coinbase"):
                continue
            prev_txid = inp.get("txid", "")
            prev_vout = inp.get("vout", 0)
            if not prev_txid:
                continue
            inputs.append({
                "address": f"utxo:{prev_txid[:16]}:{prev_vout}",
                "value_satoshi": 0,
            })
        return inputs

    def _extract_output_addresses(self, vout: list[dict]) -> list[dict]:
        """Extract receiver addresses and values from UTXO outputs."""
        outputs = []
        for out in vout:
            spk = out.get("scriptPubKey", {})
            # Alchemy verbosity=2: address is in scriptPubKey.address (single) or addresses (list)
            sp = (
                spk.get("address")
                or (spk.get("addresses") or [None])[0]
                or out.get("scriptpubkey_address")
                or out.get("addr")
                or out.get("address")
            )
            if sp:
                value_btc = float(out.get("value", 0))
                # If value looks like BTC (small float), convert to satoshis
                if isinstance(out.get("value"), float):
                    value_sat = int(value_btc * 1e8)
                else:
                    value_sat = int(out.get("value", 0))
                outputs.append({
                    "address": str(sp).strip(),
                    "value_satoshi": value_sat,
                })
        return outputs

    def _build_flat_utxo_documents(
        self,
        raw_document: dict,
    ) -> list[dict]:
        """
        Explode UTXO transactions into normalised flat documents.

        Each flat document represents one input→output pair, matching the
        structure of EVM flat transaction documents so downstream pipeline
        code works unchanged.

        For a transaction with M inputs and N outputs we create M×N pairs.
        We cap at 50 outputs and 10 inputs per tx to avoid memory blow-up
        on very large CoinJoin transactions.
        """
        block_number = raw_document.get("block_number")
        block_hash   = raw_document.get("block_hash", "")
        block_ts     = raw_document.get("block_timestamp")
        fetched_at   = raw_document.get("fetched_at")
        chain_name   = raw_document.get("chain_name", self.chain_name)

        documents = []
        seen_ids: set[str] = set()

        # Cap transactions per block to avoid excessive RPC calls
        # (getrawtransaction is called once per tx for input resolution)
        max_txs = 20
        tx_list = raw_document.get("transactions", [])
        if len(tx_list) > max_txs:
            logger.debug(
                "[%s] Block %d has %d txs — capping at %d for input resolution",
                chain_name, block_number, len(tx_list), max_txs,
            )
            tx_list = tx_list[:max_txs]

        for tx in tx_list:
            txid = tx.get("txid") or tx.get("hash") or tx.get("tx_hash")
            if not txid:
                continue

            inputs  = self._extract_input_addresses(tx.get("vin", []))
            outputs = self._extract_output_addresses(tx.get("vout", []))

            if not inputs or not outputs:
                continue

            # Cap to prevent memory issues on CoinJoin txs
            inputs  = inputs[:10]
            outputs = outputs[:50]

            # Total output value for proportional splitting
            total_out_sat = sum(o["value_satoshi"] for o in outputs) or 1

            # Create one flat doc per (input, output) pair
            for idx_in, inp in enumerate(inputs):
                from_addr = inp["address"]
                if from_addr == "COINBASE":
                    continue   # Skip coinbase inputs

                for idx_out, out in enumerate(outputs):
                    to_addr = out["address"]
                    if not to_addr or from_addr == to_addr:
                        continue

                    # Apportion the input's value proportionally to outputs
                    if inp["value_satoshi"] > 0:
                        value_sat = int(
                            inp["value_satoshi"]
                            * out["value_satoshi"]
                            / total_out_sat
                        )
                    else:
                        value_sat = out["value_satoshi"]

                    value_native = self._satoshis_to_native(value_sat)

                    # Unique document ID: txid + input_idx + output_idx
                    doc_id = f"{txid}:{idx_in}:{idx_out}"
                    if doc_id in seen_ids:
                        continue
                    seen_ids.add(doc_id)

                    documents.append({
                        "_id": doc_id,
                        "tx_hash": txid,
                        "tx_pair_id": doc_id,
                        "chain_name": chain_name,
                        "chain_id": self.chain_id,
                        "blockchain_type": BLOCKCHAIN_TYPE_UTXO,
                        "native_asset": self.native_asset,
                        "network": chain_name,
                        "block": {
                            "number": block_number,
                            "hash": block_hash,
                            "timestamp": block_ts,
                        },
                        "address_pair": {
                            "from": from_addr.lower(),
                            "to": to_addr.lower(),
                        },
                        "value": {
                            "satoshi": value_sat,
                            "native": value_native,
                            "eth": value_native,        # alias for compat
                            "usd_at_execution": None,
                        },
                        "utxo": {
                            "input_index": idx_in,
                            "output_index": idx_out,
                            "input_count": len(inputs),
                            "output_count": len(outputs),
                            "total_inputs": len(tx.get("vin", [])),
                            "total_outputs": len(tx.get("vout", [])),
                        },
                        "gas": {
                            "gas_limit": None,
                            "gas_used": None,
                        },
                        "forensics": {
                            "input_data": "0x",
                            "is_contract": False,
                            "is_contract_creation": False,
                            "method_id": "0x",
                            "receipt_status": 1,
                        },
                        "metadata": {
                            "fetched_at": fetched_at,
                            "processed": False,
                            "processed_at": None,
                            "label_status": "PENDING",
                        },
                    })

        return documents

    # ── Block fetch ───────────────────────────────────────────────────────────

    def fetch_block(self, block_number: int) -> dict:
        """
        Fetch a UTXO block with transactions via JSON-RPC.

        Strategy:
          1. getblockhash(height) → block_hash
          2. getblock(hash, 1) → block header + tx hashes only (verbosity=1)
             This avoids downloading full 5MB+ blocks with all tx data.
          3. For the first N transactions, fetch via getrawtransaction
             to get input/output addresses for AML analysis.
        """
        # Step 1: hash for this height
        block_hash = self._rpc("getblockhash", [block_number])
        if not block_hash or not isinstance(block_hash, str):
            raise RuntimeError(
                f"[{self.chain_name}] getblockhash({block_number}) = {block_hash}"
            )

        # Step 2: get block with verbosity=1 (tx hashes only, no full data)
        # This is much smaller and faster than verbosity=2
        block_data = self._rpc("getblock", [block_hash, 1])
        if not block_data or not isinstance(block_data, dict):
            raise RuntimeError(
                f"[{self.chain_name}] getblock({block_hash}) returned unexpected data"
            )

        tx_hashes = block_data.get("tx") or []
        block_time = block_data.get("time")

        # Step 3: Fetch full tx data for first N transactions (skip coinbase at index 0)
        MAX_TXS = 15
        full_txs = []
        for txid in tx_hashes[1:MAX_TXS + 1]:  # skip coinbase (index 0)
            try:
                tx_data = self._rpc("getrawtransaction", [txid, True])
                if isinstance(tx_data, dict):
                    full_txs.append(tx_data)
            except Exception as exc:
                logger.debug("[%s] Could not fetch tx %s: %s", self.chain_name, txid[:16], exc)
            time.sleep(0.05)  # small delay to avoid rate limiting

        raw_document = {
            "block_number":      block_number,
            "block_hash":        block_hash,
            "block_timestamp":   block_time,
            "fetched_at":        datetime.now(timezone.utc).isoformat(),
            "chain_name":        self.chain_name,
            "chain_id":          self.chain_id,
            "blockchain_type":   BLOCKCHAIN_TYPE_UTXO,
            "native_asset":      self.native_asset,
            "network":           self.chain_name,
            "transaction_count": len(full_txs),
            "transactions":      full_txs,
            "block_raw": {
                "hash":       block_hash,
                "height":     block_number,
                "nTx":        len(tx_hashes),
                "time":       block_time,
                "difficulty": block_data.get("difficulty"),
                "size":       block_data.get("size"),
                "weight":     block_data.get("weight"),
            },
        }

        return self._to_jsonable(raw_document)

    @staticmethod
    def _to_jsonable(obj):
        """Recursively convert non-JSON-safe objects."""
        if isinstance(obj, dict):
            return {k: UTXOExtractor._to_jsonable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [UTXOExtractor._to_jsonable(v) for v in obj]
        if isinstance(obj, bytes):
            return obj.hex()
        return obj

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_flat_documents(self, block_number: int, docs: list[dict]) -> int:
        """Upsert UTXO flat pair documents for a single block."""
        doc_ids = [d["_id"] for d in docs]
        del_q = {"chain_name": self.chain_name, "block.number": block_number}
        if doc_ids:
            del_q["_id"] = {"$nin": doc_ids}
        self.transaction_collection.delete_many(del_q)

        if docs:
            ops = [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in docs]
            self.transaction_collection.bulk_write(ops, ordered=False)
        return len(docs)

    def save_to_db(self, data: dict) -> int:
        """Save raw UTXO block + flat input/output pair docs to MongoDB."""
        block_number = data.get("block_number")
        if block_number is None:
            raise ValueError("UTXO raw document is missing block_number")

        self.raw_collection.replace_one(
            {"chain_name": self.chain_name, "block_number": block_number},
            data,
            upsert=True,
        )
        flat_docs = self._build_flat_utxo_documents(data)
        return self._save_flat_documents(block_number, flat_docs)

    # ── Main fetch loop ───────────────────────────────────────────────────────

    def fetch_and_store_raw(
        self,
        start_block: Optional[int] = None,
        batch: Optional[int] = None,
    ) -> Tuple[int, int]:
        """Fetch a batch of UTXO blocks and store them."""
        import os

        latest_saved = self.get_latest_saved_block()

        if start_block is None:
            if latest_saved is not None:
                start_block = latest_saved + 1
            else:
                chain_upper = self.chain_name.upper().replace("_", "")
                env_start = os.getenv(f"{chain_upper}_START_BLOCK", "").strip()
                if env_start and env_start.isdigit():
                    start_block = int(env_start)
                else:
                    # Sensible defaults for each UTXO chain
                    defaults = {
                        "bitcoin":      840000,
                        "litecoin":     2600000,
                        "dogecoin":     5000000,
                        "bitcoin_cash": 850000,
                    }
                    start_block = defaults.get(self.chain_name, 1)

        batch_size = min(batch or self.cfg.eth_batch_size, _MAX_FETCH_BLOCKS_PER_RUN)

        try:
            latest_available = self.get_latest_block()
        except Exception as exc:
            logger.warning("[%s] Cannot get chain tip: %s", self.chain_name, exc)
            return start_block, start_block

        if start_block > latest_available:
            logger.info(
                "[%s] No new blocks (start=%d, latest=%d)",
                self.chain_name, start_block, latest_available,
            )
            return start_block, latest_available

        from_block = start_block
        to_block   = min(from_block + batch_size - 1, latest_available)

        logger.info("[%s] Fetching blocks %d → %d", self.chain_name, from_block, to_block)

        total_pairs = 0
        for block_number in range(from_block, to_block + 1):
            try:
                raw_data = self.fetch_block(block_number)
                self.save_to_local_backup(raw_data, block_number)
                pair_count = self.save_to_db(raw_data)
                total_pairs += pair_count
                logger.info(
                    "[%s] Block %d: %d txs → %d input/output pairs",
                    self.chain_name, block_number,
                    raw_data.get("transaction_count", 0),
                    pair_count,
                )
            except Exception as exc:
                logger.warning(
                    "[%s] Block %d failed (skipping): %s",
                    self.chain_name, block_number, exc,
                )
            time.sleep(0.3)

        msg = (
            f"[{self.chain_name}] Saved blocks {from_block} → {to_block} "
            f"({to_block - from_block + 1} blocks, {total_pairs} tx pairs)"
        )
        print(msg)
        logger.info(msg)
        return from_block, to_block
