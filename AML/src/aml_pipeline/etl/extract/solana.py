"""
Solana Chain Extractor
=======================
Fetches Solana blocks, transactions, account activity, and token transfers
via Alchemy's Solana JSON-RPC API.

Solana's account model differs from both EVM and UTXO:
  - Transactions are fee-payer driven (one account pays all fees)
  - Multiple instructions per transaction (programs invoked)
  - Token transfers use SPL token program instructions
  - No "from/to" in a single field — must parse instruction accounts

Normalisation strategy:
  - Native SOL transfers   → TxRecord(from=sender, to=receiver, value=lamports/1e9)
  - SPL token transfers    → TxRecord with token metadata in extra fields
  - Fee payer              → recorded so fee-payer heuristic can cluster wallets
  - Program invocations    → recorded for program-interaction heuristic

All flat docs stored in MongoDB raw_transactions tagged chain_name="solana"
so the rest of the pipeline works unchanged.

Alchemy Solana RPC endpoints used:
  getBlockHeight           — current slot (chain tip)
  getBlock                 — full block with transactions
  getTransaction           — single transaction detail
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional, Tuple

import requests

from ...chains.registry import get_chain, BLOCKCHAIN_TYPE_ACCOUNT
from ...config import Config, load_config
from ...utils.connections import get_mongo_client
from .base import BaseExtractor

logger = logging.getLogger(__name__)

_MAX_FETCH_SLOTS_PER_RUN = 5
_REQUEST_TIMEOUT         = 30
_LAMPORTS_PER_SOL        = 1_000_000_000

# Known Solana program IDs (public)
SYSTEM_PROGRAM    = "11111111111111111111111111111111"
SPL_TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022        = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
MEMO_PROGRAM      = "MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr"


class SolanaExtractor(BaseExtractor):
    """
    Solana-specific extractor using Alchemy JSON-RPC.

    Fetches slots (Solana's equivalent of blocks), extracts transactions,
    and normalises SOL + SPL token transfers into flat documents.
    """

    def __init__(
        self,
        cfg: Optional[Config] = None,
        rpc_url: Optional[str] = None,
    ):
        super().__init__(cfg)
        self.chain_config = get_chain("solana")
        self._rpc_url = self._resolve_rpc_url(rpc_url)

        # MongoDB — shared collections
        mongo_client = get_mongo_client(self.cfg)
        self.raw_collection = mongo_client[self.cfg.mongo_raw_db][self.cfg.mongo_raw_collection]
        self.transaction_collection = mongo_client[self.cfg.mongo_flat_tx_db][self.cfg.mongo_flat_tx_collection]
        self.collection = self.raw_collection

        self._prepare_collections()
        logger.info(
            "SolanaExtractor ready: rpc=%s…",
            self._rpc_url[:60],
        )

    # ── Chain identity ────────────────────────────────────────────────────────

    @property
    def chain_name(self) -> str:
        return "solana"

    @property
    def chain_id(self) -> int:
        return 900

    @property
    def blockchain_type(self) -> str:
        return BLOCKCHAIN_TYPE_ACCOUNT

    @property
    def native_asset(self) -> str:
        return "SOL"

    # ── RPC URL resolution ────────────────────────────────────────────────────

    def _resolve_rpc_url(self, explicit: Optional[str]) -> str:
        import os
        if explicit:
            return explicit

        for env_var in ["SOLANA_RPC", "SOL_RPC", "SOLANA_RPC_URL"]:
            val = os.getenv(env_var, "")
            if val and isinstance(val, str):
                val = val.strip()
                if val:
                    return val

        api_key = os.getenv("ALCHEMY_API_KEY", "")
        if api_key and isinstance(api_key, str):
            api_key = api_key.strip()

        if not api_key:
            alchemy_rpc = os.getenv("ALCHEMY_RPC", "")
            if isinstance(alchemy_rpc, str) and "/v2/" in alchemy_rpc:
                api_key = alchemy_rpc.split("/v2/")[-1].strip("/")

        if api_key:
            return f"https://solana-mainnet.g.alchemy.com/v2/{api_key}"

        logger.warning(
            "No Solana RPC URL found. Set SOLANA_RPC or ALCHEMY_API_KEY in .env"
        )
        return "https://solana-mainnet.g.alchemy.com/v2/demo"

    # ── MongoDB indexes ───────────────────────────────────────────────────────

    def _prepare_collections(self) -> None:
        try:
            self.raw_collection.create_index(
                [("chain_name", 1), ("block_number", 1)],
                unique=True,
                name="solana_slot_unique",
            )
            self.transaction_collection.create_index(
                [("chain_name", 1), ("block.number", 1)],
                name="solana_block_tx_idx",
            )
        except Exception as exc:
            logger.debug("Solana MongoDB index note: %s", exc)

    # ── JSON-RPC helpers ──────────────────────────────────────────────────────

    def _rpc(self, method: str, params: list, retries: int = 3) -> Any:
        """Send a Solana JSON-RPC request."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                resp = requests.post(
                    self._rpc_url,
                    json=payload,
                    timeout=120,           # 2 min — Solana getBlock can be large
                    headers={"Content-Type": "application/json"},
                    stream=False,
                )
                if resp.status_code == 429:
                    wait = 2 ** attempt
                    logger.warning("[solana] Rate limited, waiting %ds", wait)
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()

                # RPC-level error (e.g. slot too old, not available)
                if "error" in data and data["error"] is not None:
                    err = data["error"]
                    msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
                    raise RuntimeError(f"RPC error: {msg}")

                return data.get("result")

            except RuntimeError:
                raise   # propagate RPC errors immediately (no retry)
            except Exception as exc:
                last_exc = exc
                logger.warning("[solana] RPC attempt %d failed: %s", attempt, exc)
                time.sleep(1.0 * attempt)

        raise RuntimeError(f"[solana] RPC {method} failed after {retries} attempts: {last_exc}")

    # ── Chain head ────────────────────────────────────────────────────────────

    def get_latest_block(self) -> int:
        """Return current slot height."""
        result = self._rpc("getBlockHeight", [])
        return int(result)

    def get_latest_saved_block(self) -> Optional[int]:
        latest = self.raw_collection.find_one(
            {"chain_name": "solana"},
            sort=[("block_number", -1)],
        )
        if not latest:
            return None
        return int(latest.get("block_number"))

    # ── Transaction parsing ───────────────────────────────────────────────────

    def _parse_sol_transfer(self, tx: dict, slot: int, block_time: Optional[int]) -> list[dict]:
        """
        Extract SOL native transfers from a transaction's pre/post balances.
        Handles jsonParsed format where accountKeys are dicts with 'pubkey' field.
        """
        meta = tx.get("meta", {}) or {}
        msg  = (tx.get("transaction", {}) or {}).get("message", {}) or {}

        # In "accounts" mode, accountKeys may be directly on transaction
        # In "full"/"jsonParsed" mode, they are in transaction.message.accountKeys
        tx_obj = tx.get("transaction", {}) or {}
        raw_keys = (
            msg.get("accountKeys", [])
            or tx_obj.get("accountKeys", [])
            or []
        )
        account_keys = []
        for k in raw_keys:
            if isinstance(k, dict):
                account_keys.append(str(k.get("pubkey", "") or ""))
            else:
                account_keys.append(str(k) if k else "")

        pre_bals  = meta.get("preBalances",  []) or []
        post_bals = meta.get("postBalances", []) or []

        if not account_keys or not pre_bals or not post_bals:
            return []

        fee_payer = account_keys[0] if account_keys else ""
        fee       = int(meta.get("fee", 0) or 0)
        sig       = ""
        # Signatures can be at transaction.signatures or just signatures
        sigs = tx_obj.get("signatures", []) or tx.get("signatures", [])
        if sigs:
            sig = str(sigs[0])[:88] if sigs[0] else ""

        programs = self._extract_programs(msg, account_keys)

        transfers = []
        for i, key in enumerate(account_keys):
            if i >= len(pre_bals) or i >= len(post_bals):
                break
            try:
                delta = int(post_bals[i]) - int(pre_bals[i])
            except (TypeError, ValueError):
                continue
            if delta <= 0:
                continue

            sender = None
            for j, src_key in enumerate(account_keys):
                if j == i:
                    continue
                if j >= len(pre_bals) or j >= len(post_bals):
                    continue
                try:
                    src_delta = int(post_bals[j]) - int(pre_bals[j])
                except (TypeError, ValueError):
                    continue
                if src_delta < 0 and abs(src_delta) >= delta:
                    sender = src_key
                    break

            if sender and key != sender and key and sender:
                transfers.append({
                    "tx_hash":       sig,
                    "from_address":  sender,
                    "to_address":    key,
                    "value_lamports": delta,
                    "value_sol":     delta / _LAMPORTS_PER_SOL,
                    "fee_payer":     fee_payer,
                    "fee_lamports":  fee,
                    "programs":      programs,
                    "slot":          slot,
                    "block_time":    block_time,
                    "transfer_type": "sol_native",
                    "token_mint":    None,
                    "token_symbol":  "SOL",
                })

        return transfers

    def _parse_token_transfers(self, tx: dict, slot: int, block_time: Optional[int]) -> list[dict]:
        """
        Extract SPL token transfers from transaction token balance changes.
        Handles jsonParsed format where accountKeys are dicts with 'pubkey' field.
        """
        meta = tx.get("meta", {}) or {}
        pre_tok  = meta.get("preTokenBalances",  []) or []
        post_tok = meta.get("postTokenBalances", []) or []

        msg = (tx.get("transaction", {}) or {}).get("message", {}) or {}
        raw_keys = msg.get("accountKeys", []) or []
        account_keys = []
        for k in raw_keys:
            if isinstance(k, dict):
                account_keys.append(str(k.get("pubkey", "") or ""))
            else:
                account_keys.append(str(k) if k else "")

        fee_payer = account_keys[0] if account_keys else ""
        sig = ""
        sigs = tx.get("transaction", {}).get("signatures", [])
        if sigs:
            sig = str(sigs[0]) if sigs[0] else ""

        pre_index: dict[tuple, dict] = {}
        for entry in pre_tok:
            key = (entry.get("accountIndex"), entry.get("mint"))
            pre_index[key] = entry

        transfers = []
        for post_entry in post_tok:
            acc_idx = post_entry.get("accountIndex")
            mint    = post_entry.get("mint")
            key     = (acc_idx, mint)
            pre_e   = pre_index.get(key, {})

            pre_ui  = float((pre_e.get("uiTokenAmount") or {}).get("uiAmount") or 0)
            post_ui = float((post_entry.get("uiTokenAmount") or {}).get("uiAmount") or 0)
            delta   = post_ui - pre_ui

            if delta <= 0 or acc_idx is None:
                continue

            try:
                to_addr = account_keys[int(acc_idx)] if int(acc_idx) < len(account_keys) else ""
            except (TypeError, ValueError):
                to_addr = ""
            owner    = str(post_entry.get("owner", "") or "")
            decimals = int((post_entry.get("uiTokenAmount") or {}).get("decimals", 0) or 0)

            transfers.append({
                "tx_hash":        sig,
                "from_address":   fee_payer,
                "to_address":     to_addr,
                "value_lamports": 0,
                "value_sol":      0.0,
                "fee_payer":      fee_payer,
                "fee_lamports":   int(meta.get("fee", 0) or 0),
                "programs":       self._extract_programs(msg, account_keys),
                "slot":           slot,
                "block_time":     block_time,
                "transfer_type":  "spl_token",
                "token_mint":     mint,
                "token_amount":   delta,
                "token_decimals": decimals,
                "token_owner":    owner,
                "token_symbol":   "SPL",
            })

        return transfers

    @staticmethod
    def _extract_programs(msg: dict, resolved_keys: Optional[list] = None) -> list[str]:
        """Extract unique program IDs invoked in a transaction."""
        instructions = msg.get("instructions", []) or []
        keys         = msg.get("accountKeys", [])
        programs: set[str] = set()
        for instr in instructions:
            prog_idx = instr.get("programIdIndex")
            if prog_idx is not None and prog_idx < len(keys):
                programs.add(keys[prog_idx])
        return sorted(programs)

    def _build_flat_solana_docs(self, raw_document: dict) -> list[dict]:
        """
        Build flat transaction documents from a Solana raw slot document.
        Each SOL transfer and SPL token transfer becomes one flat doc.
        """
        slot       = raw_document.get("block_number", 0)
        block_time = raw_document.get("block_time")
        fetched_at = raw_document.get("fetched_at")
        chain_name = "solana"

        documents = []
        seen_ids: set[str] = set()

        for tx in raw_document.get("transactions", []):
            meta = tx.get("meta", {}) or {}
            # Skip failed transactions
            if meta.get("err") is not None:
                continue

            sol_transfers   = self._parse_sol_transfer(tx, slot, block_time)
            token_transfers = self._parse_token_transfers(tx, slot, block_time)

            all_transfers = sol_transfers + token_transfers
            for idx, transfer in enumerate(all_transfers):
                sig       = transfer.get("tx_hash", "")
                from_addr = (transfer.get("from_address") or "").strip()
                to_addr   = (transfer.get("to_address")   or "").strip()

                if not from_addr or not to_addr or from_addr == to_addr:
                    continue

                ttype  = transfer.get("transfer_type", "sol_native")
                # Use the signature as tx_hash (88 chars max for Solana)
                # doc_id is unique per transfer: sig:type:idx
                doc_id = f"{sig[:64]}:{ttype}:{idx}"
                if doc_id in seen_ids:
                    continue
                seen_ids.add(doc_id)

                value_sol = float(transfer.get("value_sol", 0.0))
                # For SPL tokens express value in token units; native field stays 0
                token_amt = float(transfer.get("token_amount", 0.0))
                effective_value = value_sol if ttype == "sol_native" else 0.0

                documents.append({
                    "_id":           doc_id,
                    "tx_hash":       sig[:128],   # Solana signature, max 88 chars
                    "chain_name":    chain_name,
                    "chain_id":      900,
                    "blockchain_type": BLOCKCHAIN_TYPE_ACCOUNT,
                    "native_asset":  "SOL",
                    "network":       chain_name,
                    "block": {
                        "number":    slot,
                        "hash":      raw_document.get("block_hash", ""),
                        "timestamp": block_time,
                    },
                    "address_pair": {
                        "from": from_addr,
                        "to":   to_addr,
                    },
                    "value": {
                        "lamports":         int(transfer.get("value_lamports", 0)),
                        "sol":              value_sol,
                        "native":           effective_value,
                        "eth":              effective_value,   # alias for compat
                        "usd_at_execution": None,
                        "token_amount":     token_amt,
                        "token_mint":       transfer.get("token_mint"),
                    },
                    "solana": {
                        "fee_payer":      transfer.get("fee_payer", ""),
                        "fee_lamports":   int(transfer.get("fee_lamports", 0)),
                        "programs":       transfer.get("programs", []),
                        "transfer_type":  ttype,
                        "token_symbol":   transfer.get("token_symbol", "SOL"),
                        "token_decimals": int(transfer.get("token_decimals", 9)),
                        "token_owner":    transfer.get("token_owner", ""),
                    },
                    "gas": {
                        "gas_limit":       None,
                        "gas_used":        int(transfer.get("fee_lamports", 0)),
                    },
                    "forensics": {
                        "input_data":           "0x",
                        "is_contract":          bool(transfer.get("programs")),
                        "is_contract_creation": False,
                        "method_id":            transfer.get("programs", ["0x"])[0] if transfer.get("programs") else "0x",
                        "receipt_status":       1,
                        "programs":             transfer.get("programs", []),
                    },
                    "metadata": {
                        "fetched_at":   fetched_at,
                        "processed":    False,
                        "processed_at": None,
                        "label_status": "PENDING",
                    },
                })

        return documents

    # ── Block fetch ───────────────────────────────────────────────────────────

    def fetch_block(self, block_number: int) -> dict:
        """
        Fetch a Solana slot (block) with full transaction data.
        block_number is treated as a slot number.
        """
        result = self._rpc(
            "getBlock",
            [
                block_number,
                {
                    "encoding": "jsonParsed",
                    "maxSupportedTransactionVersion": 0,
                    "transactionDetails": "accounts",  # lighter than "full" — no instructions
                    "rewards": False,
                },
            ],
        )
        if result is None:
            raise RuntimeError(f"[solana] Slot {block_number} returned null (skipped slot)")

        # Alchemy returns the block dict directly as result.
        # Guard: if result is not a dict with block fields it's an unexpected shape.
        if not isinstance(result, dict):
            raise RuntimeError(
                f"[solana] Slot {block_number} unexpected response type: {type(result)}"
            )

        txs        = result.get("transactions") or []
        block_hash = result.get("blockhash") or ""
        block_time = result.get("blockTime")   # int (unix) or None
        parent_slot = result.get("parentSlot", block_number - 1)

        # Ensure block_time is an int or None
        if block_time is not None:
            try:
                block_time = int(block_time)
            except (TypeError, ValueError):
                block_time = None

        # Ensure parent_slot is an int
        try:
            parent_slot = int(parent_slot)
        except (TypeError, ValueError):
            parent_slot = block_number - 1

        raw_document = {
            "block_number":      block_number,
            "block_hash":        str(block_hash),
            "block_time":        block_time,
            "parent_slot":       parent_slot,
            "fetched_at":        datetime.now(timezone.utc).isoformat(),
            "chain_name":        "solana",
            "chain_id":          900,
            "blockchain_type":   BLOCKCHAIN_TYPE_ACCOUNT,
            "native_asset":      "SOL",
            "network":           "solana",
            "transaction_count": len(txs),
            "transactions":      txs,
        }
        return raw_document

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_flat_docs(self, slot: int, docs: list[dict]) -> int:
        from pymongo import ReplaceOne
        del_q = {"chain_name": "solana", "block.number": slot}
        self.transaction_collection.delete_many(del_q)

        if docs:
            ops = [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in docs]
            self.transaction_collection.bulk_write(ops, ordered=False)
        return len(docs)

    def save_to_db(self, data: dict) -> int:
        slot = data.get("block_number")
        if slot is None:
            raise ValueError("Solana raw document missing block_number")

        self.raw_collection.replace_one(
            {"chain_name": "solana", "block_number": slot},
            data,
            upsert=True,
        )
        flat_docs = self._build_flat_solana_docs(data)
        return self._save_flat_docs(slot, flat_docs)

    # ── Main fetch loop ───────────────────────────────────────────────────────

    def fetch_and_store_raw(
        self,
        start_block: Optional[int] = None,
        batch: Optional[int] = None,
    ) -> Tuple[int, int]:
        """Fetch a batch of Solana slots near the current chain tip."""
        import os

        # Get chain tip first — needed to determine a good start slot
        try:
            latest_available = self.get_latest_block()
        except Exception as exc:
            logger.warning("[solana] Cannot get chain tip: %s", exc)
            return (start_block or 0), (start_block or 0)

        latest_saved = self.get_latest_saved_block()

        if start_block is None:
            if latest_saved is not None:
                start_block = latest_saved + 1
            else:
                env_start = os.getenv("SOLANA_START_SLOT", "").strip()
                if env_start and env_start.isdigit():
                    configured = int(env_start)
                    if latest_available - configured > 10_000_000:
                        logger.info(
                            "[solana] SOLANA_START_SLOT=%d is too old "
                            "(tip=%d). Using recent slot instead.",
                            configured, latest_available,
                        )
                        start_block = latest_available - 100
                    else:
                        start_block = configured
                else:
                    # Default: 100 slots behind tip (confirmed & finalized)
                    start_block = latest_available - 100

        batch_size = min(
            batch or self.cfg.eth_batch_size,
            _MAX_FETCH_SLOTS_PER_RUN,
        )

        if start_block > latest_available:
            logger.info(
                "[solana] No new slots (start=%d, latest=%d)",
                start_block, latest_available,
            )
            return start_block, latest_available

        from_slot = start_block
        to_slot   = min(from_slot + batch_size - 1, latest_available)

        logger.info("[solana] Fetching slots %d -> %d", from_slot, to_slot)

        total_transfers = 0
        for slot in range(from_slot, to_slot + 1):
            try:
                raw_data = self.fetch_block(slot)
                self.save_to_local_backup(raw_data, slot)
                count = self.save_to_db(raw_data)
                total_transfers += count
                logger.info(
                    "[solana] Slot %d: %d txs -> %d transfers",
                    slot, raw_data.get("transaction_count", 0), count,
                )
            except RuntimeError as exc:
                err_str = str(exc)
                if "null (skipped slot)" in err_str or "slot was skipped" in err_str.lower():
                    logger.debug("[solana] Slot %d skipped (empty/skipped slot)", slot)
                else:
                    logger.warning("[solana] Slot %d error: %s", slot, exc)
            except Exception as exc:
                logger.warning("[solana] Slot %d failed: %s", slot, exc)
                logger.debug("[solana] Slot %d traceback:", slot, exc_info=True)
            time.sleep(0.25)

        msg = (
            f"[solana] Saved slots {from_slot} -> {to_slot} "
            f"({to_slot - from_slot + 1} slots, {total_transfers} transfers)"
        )
        print(msg)
        logger.info(msg)
        return from_slot, to_slot
