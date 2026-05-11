from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from blockchain_engine.connectors.base import BaseConnector
from blockchain_engine.models import NormalizedTransaction
from blockchain_engine.network import RetryConfig, request_with_retry

TRANSFER_EVENT_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)


class EVMConnector(BaseConnector):
    def __init__(
        self,
        chain: str,
        rpc_url: str,
        request_timeout: int = 20,
        explorer_api_url: str | None = None,
        explorer_api_key: str = "",
        blockscout_api_url: str | None = None,
        max_rpc_scan_blocks: int = 250,
        retry_config: RetryConfig | None = None,
    ) -> None:
        self.chain = chain
        self.rpc_url = rpc_url
        self.request_timeout = request_timeout
        self.explorer_api_url = explorer_api_url
        self.explorer_api_key = explorer_api_key
        self.blockscout_api_url = blockscout_api_url.rstrip("/") if blockscout_api_url else None
        self.max_rpc_scan_blocks = max_rpc_scan_blocks
        self.session = requests.Session()
        self.retry_config = retry_config or RetryConfig()

    def _rpc(self, method: str, params: list[Any]) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        response = request_with_retry(
            self.session,
            "POST",
            self.rpc_url,
            json=payload,
            timeout=self.request_timeout,
            retry_config=self.retry_config,
        )
        response.raise_for_status()
        body = response.json()
        if body.get("error"):
            raise RuntimeError(f"{self.chain} RPC error: {body['error']}")
        return body["result"]

    def _explorer_get(self, params: dict[str, Any]) -> Any:
        if not self.explorer_api_url:
            raise RuntimeError(f"{self.chain} explorer API is not configured")

        request_params = dict(params)
        if self.explorer_api_key:
            request_params["apikey"] = self.explorer_api_key
        chain_id = self._chain_id()
        if chain_id is not None:
            request_params["chainid"] = chain_id

        response = request_with_retry(
            self.session,
            "GET",
            self.explorer_api_url,
            params=request_params,
            timeout=self.request_timeout,
            retry_config=self.retry_config,
        )
        response.raise_for_status()
        body = response.json()
        status = str(body.get("status", "1"))
        result = body.get("result", [])
        if status == "0" and result not in ("", [], "No transactions found", "0"):
            raise RuntimeError(f"{self.chain} explorer error: {body.get('message')}")
        return result

    def get_balance(self, address: str) -> dict[str, Any]:
        balance_wei: int
        if self.explorer_api_url and self.explorer_api_key:
            try:
                balance_wei = self._get_balance_from_explorer(address)
            except Exception:
                raw_balance = self._rpc("eth_getBalance", [address, "latest"])
                balance_wei = int(raw_balance, 16)
        else:
            raw_balance = self._rpc("eth_getBalance", [address, "latest"])
            balance_wei = int(raw_balance, 16)
        return {
            "chain": self.chain,
            "address": address,
            "balance": balance_wei / 10**18,
            "asset": self._native_asset(),
        }

    def get_code(self, address: str) -> str:
        try:
            code = self._rpc("eth_getCode", [address, "latest"])
            return code
        except Exception as e:
            return "0x"

    def _get_balance_from_explorer(self, address: str) -> int:
        result = self._explorer_get(
            {
                "module": "account",
                "action": "balance",
                "address": address,
                "tag": "latest",
            }
        )
        return int(result or "0")

    def get_transactions(self, address: str, limit: int = 50) -> list[NormalizedTransaction]:
        if self.explorer_api_url and self.explorer_api_key:
            try:
                return self._get_transactions_from_explorer(address, limit)
            except Exception:
                pass

        if self.blockscout_api_url:
            try:
                return self._get_transactions_from_blockscout(address, limit)
            except Exception:
                pass

        # RPC block scan — bounded and wrapped so a timeout returns empty list
        try:
            latest_block = int(self._rpc("eth_blockNumber", []), 16)
        except Exception:
            return []

        results: list[NormalizedTransaction] = []
        cursor = latest_block
        min_block = max(0, latest_block - self.max_rpc_scan_blocks)
        lower_address = address.lower()

        while cursor >= min_block and len(results) < limit:
            try:
                block = self._rpc("eth_getBlockByNumber", [hex(cursor), True])
            except Exception:
                break  # stop on any RPC error (timeout, rate-limit, etc.)
            if not block:
                cursor -= 1
                continue

            block_timestamp = datetime.fromtimestamp(
                int(block["timestamp"], 16),
                tz=timezone.utc,
            )
            for tx in block.get("transactions", []):
                from_address = (tx.get("from") or "").lower()
                to_address = (tx.get("to") or "").lower() or None
                if lower_address not in {from_address, to_address}:
                    continue
                value = int(tx.get("value", "0x0"), 16) / 10**18
                results.append(
                    NormalizedTransaction(
                        chain=self.chain,
                        tx_hash=tx["hash"],
                        block_number=int(tx["blockNumber"], 16)
                        if tx.get("blockNumber")
                        else None,
                        timestamp=block_timestamp,
                        from_address=tx.get("from", ""),
                        to_address=tx.get("to"),
                        value=value,
                        asset=self._native_asset(),
                        direction="out"
                        if from_address == lower_address
                        else "in",
                        method_id=(tx.get("input") or "")[:10] or None,
                        raw=tx,
                    )
                )
                if len(results) >= limit:
                    break
            cursor -= 1

        return results

    def _get_transactions_from_blockscout(
        self,
        address: str,
        limit: int,
    ) -> list[NormalizedTransaction]:
        response = request_with_retry(
            self.session,
            "GET",
            f"{self.blockscout_api_url}/addresses/{address}/transactions",
            params={"items_count": limit},
            timeout=self.request_timeout,
            retry_config=self.retry_config,
        )
        response.raise_for_status()
        body = response.json()
        transactions = body.get("items", [])
        lower_address = address.lower()
        results: list[NormalizedTransaction] = []
        for tx in transactions[:limit]:
            block_number = tx.get("block")
            timestamp_value = tx.get("timestamp")
            if isinstance(timestamp_value, str) and timestamp_value.endswith("Z"):
                timestamp = datetime.fromisoformat(timestamp_value.replace("Z", "+00:00"))
            else:
                timestamp = datetime.now(tz=timezone.utc)
            from_address = (
                tx.get("from", {}).get("hash", "")
                if isinstance(tx.get("from"), dict)
                else tx.get("from", "")
            ).lower()
            to_address_raw = (
                tx.get("to", {}).get("hash")
                if isinstance(tx.get("to"), dict)
                else tx.get("to")
            )
            value_raw = tx.get("value") or "0"
            results.append(
                NormalizedTransaction(
                    chain=self.chain,
                    tx_hash=tx["hash"],
                    block_number=int(block_number) if block_number else None,
                    timestamp=timestamp,
                    from_address=tx.get("from", {}).get("hash", "")
                    if isinstance(tx.get("from"), dict)
                    else (tx.get("from") or ""),
                    to_address=to_address_raw,
                    value=int(value_raw) / 10**18,
                    asset=self._native_asset(),
                    direction="out" if from_address == lower_address else "in",
                    method_id=(tx.get("raw_input") or tx.get("method") or "")[:10] or None,
                    raw=tx,
                )
            )
        return results

    def _get_transactions_from_explorer(
        self,
        address: str,
        limit: int,
    ) -> list[NormalizedTransaction]:
        transactions = self._explorer_get(
            {
                "module": "account",
                "action": "txlist",
                "address": address,
                "startblock": 0,
                "endblock": 99999999,
                "page": 1,
                "offset": limit,
                "sort": "desc",
            }
        )
        if not isinstance(transactions, list):
            return []
        lower_address = address.lower()
        results: list[NormalizedTransaction] = []
        for tx in transactions[:limit]:
            timestamp = datetime.fromtimestamp(int(tx["timeStamp"]), tz=timezone.utc)
            from_address = (tx.get("from") or "").lower()
            to_address = tx.get("to")
            results.append(
                NormalizedTransaction(
                    chain=self.chain,
                    tx_hash=tx["hash"],
                    block_number=int(tx["blockNumber"]) if tx.get("blockNumber") else None,
                    timestamp=timestamp,
                    from_address=tx.get("from", ""),
                    to_address=to_address,
                    value=int(tx.get("value", "0")) / 10**18,
                    asset=self._native_asset(),
                    direction="out" if from_address == lower_address else "in",
                    method_id=(tx.get("input") or "")[:10] or None,
                    raw=tx,
                )
            )
        return results

    def get_token_transfers(
        self,
        address: str,
        from_block: str = "0x0",
        to_block: str = "latest",
    ) -> list[dict[str, Any]]:
        if self.explorer_api_url and self.explorer_api_key:
            try:
                return self._explorer_get(
                    {
                        "module": "account",
                        "action": "tokentx",
                        "address": address,
                        "startblock": int(from_block, 16) if from_block.startswith("0x") else 0,
                        "endblock": (
                            99999999
                            if to_block == "latest"
                            else int(to_block, 16)
                            if to_block.startswith("0x")
                            else int(to_block)
                        ),
                        "page": 1,
                        "offset": 100,
                        "sort": "desc",
                    }
                )
            except Exception:
                pass

        padded_address = "0x" + address.lower().replace("0x", "").rjust(64, "0")
        logs = self._rpc(
            "eth_getLogs",
            [
                {
                    "fromBlock": from_block,
                    "toBlock": to_block,
                    "topics": [TRANSFER_EVENT_TOPIC, None, padded_address],
                }
            ],
        )
        return logs

    def _native_asset(self) -> str:
        return {
            "ethereum": "ETH",
            "bsc": "BNB",
            "polygon": "MATIC",
            "arbitrum": "ETH",
        }.get(self.chain, "NATIVE")

    def _chain_id(self) -> int | None:
        return {
            "ethereum": 1,
            "bsc": 56,
            "polygon": 137,
            "arbitrum": 42161,
        }.get(self.chain)
