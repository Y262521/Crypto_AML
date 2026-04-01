"""Shared helper utilities for extractors."""

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal

from bson import ObjectId
from bson.decimal128 import Decimal128
from hexbytes import HexBytes
from web3.datastructures import AttributeDict

logger = logging.getLogger(__name__)

MAX_INT64 = 2**63 - 1
MIN_INT64 = -(2**63)
WEI_PER_ETH = Decimal("1000000000000000000")


def to_jsonable(value):
    """Convert Web3/Mongo objects into JSON-serializable types."""
    if isinstance(value, AttributeDict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value > MAX_INT64 or value < MIN_INT64:
            return str(value)
        return value
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, (HexBytes, bytes)):
        return value.hex()
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def to_int(value, default: int = 0):
    """Convert numeric inputs, including hex strings, into Python ints."""
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        if value.startswith("0x"):
            try:
                return int(value, 16)
            except ValueError:
                return default
        try:
            return int(value)
        except ValueError:
            return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_optional_int(value):
    """Convert a numeric input into an int, or None when not present."""
    if value in (None, ""):
        return None
    return to_int(value, default=0)


def to_utc_datetime(value):
    """Convert raw timestamps into timezone-aware UTC datetimes when possible."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    if isinstance(value, str):
        if value.startswith("0x"):
            return datetime.fromtimestamp(int(value, 16), tz=timezone.utc)
        if value.isdigit():
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def normalize_address(value):
    """Normalize blockchain addresses to lowercase strings."""
    if not value:
        return None
    return str(value).lower()


def normalize_hex_data(value, default: str = "0x") -> str:
    """Normalize hex-encoded payloads so they consistently keep the 0x prefix."""
    if not value:
        return default
    value = str(value).lower()
    if value == "0x":
        return value
    if value.startswith("0x"):
        return value
    return f"0x{value}"


def normalize_hex_id(value) -> str | None:
    """Normalize hex identifiers (hashes) to lowercase with 0x prefix."""
    if value in (None, ""):
        return None
    if isinstance(value, (HexBytes, bytes)):
        text = value.hex()
    else:
        text = str(value).strip()
    if not text:
        return None
    text = text.lower()
    if text.startswith("0x"):
        return text
    # Only prefix when the value looks like hex to avoid mangling non-hex strings.
    if all(char in "0123456789abcdef" for char in text):
        return f"0x{text}"
    return text


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def to_decimal128(value):
    """Convert a numeric input into BSON Decimal128, or None when empty."""
    if value in (None, ""):
        return None
    if isinstance(value, Decimal128):
        return value
    if isinstance(value, Decimal):
        return Decimal128(_decimal_text(value))
    return Decimal128(str(to_int(value)))


def to_eth_decimal128(value_wei) -> Decimal128:
    """Convert a wei-denominated value into exact ETH Decimal128."""
    wei_decimal = Decimal(str(to_int(value_wei)))
    return Decimal128(_decimal_text(wei_decimal / WEI_PER_ETH))


def build_flat_transaction_documents(raw_document: dict, network: str) -> list[dict]:
    """Explode a raw block document into indexed transaction documents."""
    block = raw_document.get("block", {})
    block_number = raw_document.get("block_number")
    block_hash = normalize_hex_id(block.get("hash"))
    block_timestamp = to_utc_datetime(block.get("timestamp"))
    fetched_at = to_utc_datetime(raw_document.get("fetched_at"))

    receipts_map = {}
    for receipt in raw_document.get("receipts", []):
        tx_hash = normalize_hex_id(receipt.get("transactionHash"))
        if tx_hash:
            receipts_map[tx_hash] = receipt

    documents = []
    seen_hashes = set()
    for raw_tx in raw_document.get("transactions", []):
        tx_hash = normalize_hex_id(raw_tx.get("hash"))
        if not tx_hash or tx_hash in seen_hashes:
            continue
        seen_hashes.add(tx_hash)

        receipt = receipts_map.get(tx_hash, {})
        input_data = normalize_hex_data(raw_tx.get("input"))
        to_address = normalize_address(raw_tx.get("to"))
        is_contract = bool(input_data and input_data != "0x") or to_address is None
        value_wei = to_int(raw_tx.get("value"))

        documents.append(
            {
                "_id": tx_hash,
                "tx_hash": tx_hash,
                "network": network,
                "block": {
                    "number": block_number,
                    "hash": block_hash,
                    "timestamp": block_timestamp,
                },
                "address_pair": {
                    "from": normalize_address(raw_tx.get("from")),
                    "to": to_address,
                },
                "value": {
                    "wei": Decimal128(str(value_wei)),
                    "eth": to_eth_decimal128(value_wei),
                    "usd_at_execution": None,
                },
                "gas": {
                    "gas_limit": to_optional_int(raw_tx.get("gas")),
                    "gas_price_wei": to_decimal128(raw_tx.get("gasPrice")),
                    "max_fee_per_gas_wei": to_decimal128(raw_tx.get("maxFeePerGas")),
                    "max_priority_fee_per_gas_wei": to_decimal128(raw_tx.get("maxPriorityFeePerGas")),
                    "gas_used": to_optional_int(receipt.get("gasUsed")),
                    "effective_gas_price_wei": to_decimal128(receipt.get("effectiveGasPrice")),
                },
                "forensics": {
                    "input_data": input_data,
                    "input_size": max(0, len(input_data) - 2) if input_data.startswith("0x") else len(input_data),
                    "is_contract": is_contract,
                    "is_contract_creation": to_address is None,
                    "method_id": input_data[:10] if len(input_data) >= 10 else input_data,
                    "nonce": to_optional_int(raw_tx.get("nonce")),
                    "transaction_index": to_optional_int(raw_tx.get("transactionIndex")),
                    "receipt_status": to_optional_int(receipt.get("status")),
                    "receipt_logs_count": len(receipt.get("logs", [])),
                },
                "metadata": {
                    "fetched_at": fetched_at,
                    "processed": False,
                    "processed_at": None,
                    "risk_level": "PENDING",
                },
            }
        )

    return documents


def rpc_call_with_retry(fn, retries: int = 3, delay: float = 0.5):
    """Execute an RPC call with retries and a fixed delay."""
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("RPC error on attempt %s: %s", attempt, exc)
            time.sleep(delay)
    logger.error("RPC failed after %s attempts", retries)
    raise last_exc
