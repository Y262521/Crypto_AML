from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from blockchain_engine.connectors.base import BaseConnector
from blockchain_engine.models import NormalizedTransaction
from blockchain_engine.network import RetryConfig, request_with_retry


class BitcoinConnector(BaseConnector):
    chain = "bitcoin"

    def __init__(
        self,
        api_url: str,
        request_timeout: int = 20,
        retry_config: RetryConfig | None = None,
    ) -> None:
        self.api_url = api_url.rstrip("/")
        self.request_timeout = request_timeout
        self.session = requests.Session()
        self.retry_config = retry_config or RetryConfig()

    def _get(self, path: str) -> Any:
        response = request_with_retry(
            self.session,
            "GET",
            f"{self.api_url}{path}",
            timeout=self.request_timeout,
            retry_config=self.retry_config,
        )
        response.raise_for_status()
        return response.json()

    def get_balance(self, address: str) -> dict[str, Any]:
        data = self._get(f"/address/{address}")
        funded = data["chain_stats"]["funded_txo_sum"]
        spent = data["chain_stats"]["spent_txo_sum"]
        balance_btc = (funded - spent) / 10**8
        return {
            "chain": self.chain,
            "address": address,
            "balance": balance_btc,
            "asset": "BTC",
        }

    def get_transactions(self, address: str, limit: int = 50) -> list[NormalizedTransaction]:
        transactions = self._get(f"/address/{address}/txs")
        results: list[NormalizedTransaction] = []
        lower_address = address.lower()

        for tx in transactions[:limit]:
            vin_addresses = [
                vin.get("prevout", {}).get("scriptpubkey_address", "").lower()
                for vin in tx.get("vin", [])
            ]
            vout_addresses = [
                vout.get("scriptpubkey_address", "").lower()
                for vout in tx.get("vout", [])
            ]
            if lower_address not in vin_addresses and lower_address not in vout_addresses:
                continue

            value_sats = sum(
                vout.get("value", 0)
                for vout in tx.get("vout", [])
                if vout.get("scriptpubkey_address", "").lower() == lower_address
            )
            timestamp = datetime.fromtimestamp(
                tx.get("status", {}).get("block_time", 0) or 0,
                tz=timezone.utc,
            )
            results.append(
                NormalizedTransaction(
                    chain=self.chain,
                    tx_hash=tx["txid"],
                    block_number=tx.get("status", {}).get("block_height"),
                    timestamp=timestamp,
                    from_address=vin_addresses[0] if vin_addresses else "",
                    to_address=address if lower_address in vout_addresses else None,
                    value=value_sats / 10**8,
                    asset="BTC",
                    direction="in" if lower_address in vout_addresses else "out",
                    raw=tx,
                )
            )

        return results
