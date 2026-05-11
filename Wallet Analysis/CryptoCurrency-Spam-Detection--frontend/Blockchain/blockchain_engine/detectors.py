from __future__ import annotations

from collections import Counter
from datetime import datetime

from blockchain_engine.models import Detection, NormalizedTransaction
from blockchain_engine.registry import get_protocol_registry

DAPP_METHODS = {
    "0x095ea7b3": ("approval", "ERC20 approval"),
    "0xa9059cbb": ("token_transfer", "ERC20 transfer"),
    "0x38ed1739": ("dex_swap", "Uniswap-style swap"),
    "0xe8e33700": ("dex_add_liquidity", "Add liquidity"),
    "0xb6b55f25": ("bridge", "Bridge deposit"),
    "0x7ff36ab5": ("dex_swap", "Swap exact ETH for tokens"),
    "0x18cbafe5": ("dex_swap", "Swap exact tokens for ETH"),
    "0x5ae401dc": ("multicall", "Multicall interaction"),
    "0x414bf389": ("bridge", "Cross-chain bridge call"),
}


def detect_activity(transactions: list[NormalizedTransaction]) -> list[Detection]:
    detections: list[Detection] = []
    seen: set[tuple[str, str, str]] = set()
    for tx in transactions:
        for detection in (
            _detect_method(tx)
            + _detect_known_contracts(tx)
            + _detect_value_anomalies(tx)
        ):
            key = (
                detection.detector,
                detection.label,
                str(detection.details.get("tx_hash", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            detections.append(detection)
    return detections


def _lower_addr(value: object) -> str:
    if isinstance(value, str):
        return value.lower()
    return ""


def label_transactions(transactions: list[NormalizedTransaction], address: str) -> None:
    """
    In-place labeling of transactions as: send, swap, buy, receive.
    """
    addr_lower = address.lower()
    for tx in transactions:
        # Default based on direction
        if _lower_addr(tx.from_address) == addr_lower:
            tx.tx_type = "send"
        elif tx.to_address and _lower_addr(tx.to_address) == addr_lower:
            tx.tx_type = "receive"

        # Refine with method_id and known patterns
        if tx.method_id in {"0x38ed1739", "0x7ff36ab5", "0x18cbafe5"}:
            tx.tx_type = "swap"
        elif tx.method_id == "0x095ea7b3":
            tx.tx_type = "approval"
        
        # Heuristic for "buy" (e.g. receiving funds from a known exchange or payment gateway)
        # This is simplified; in production, you'd check if the sender is a known exchange
        if tx.tx_type == "receive" and tx.value > 10 and tx.asset in {"USDT", "USDC", "DAI"}:
             # Placeholder: if it looks like a large stablecoin receipt, it might be a 'buy' from an off-ramp
             pass


def _detect_method(tx: NormalizedTransaction) -> list[Detection]:
    if not tx.method_id or tx.method_id not in DAPP_METHODS:
        return []

    label, description = DAPP_METHODS[tx.method_id]
    severity = "medium" if label in {"approval", "bridge"} else "low"
    return [
        Detection(
            detector="method_signature",
            label=label,
            severity=severity,
            confidence=0.75,
            details={
                "description": description,
                "tx_hash": tx.tx_hash,
                "method_id": tx.method_id,
            },
        )
    ]


def _detect_known_contracts(tx: NormalizedTransaction) -> list[Detection]:
    if not tx.to_address:
        return []

    to_address = tx.to_address.lower()
    registry = get_protocol_registry(tx.chain)
    detections: list[Detection] = []
    for protocol, addresses in registry.items():
        if to_address not in addresses:
            continue
        severity = "high" if protocol == "tornado_cash" else "medium"
        detections.append(
            Detection(
                detector="known_protocol",
                label=protocol,
                severity=severity,
                confidence=0.9,
                details={
                    "tx_hash": tx.tx_hash,
                    "to_address": tx.to_address,
                },
            )
        )
    return detections


def _detect_value_anomalies(tx: NormalizedTransaction) -> list[Detection]:
    if tx.value < 100:
        return []
    return [
        Detection(
            detector="value_heuristic",
            label="large_transfer",
            severity="medium",
            confidence=0.65,
            details={
                "tx_hash": tx.tx_hash,
                "value": tx.value,
                "asset": tx.asset,
            },
        )
    ]


def classify_entity(
    *,
    address: str,
    transactions: list[NormalizedTransaction],
    detections: list[Detection],
    bytecode: str = "0x",
) -> str:
    """
    Classifies the address into: exchange, smart contract, bot, mixer, user wallet.
    """
    # 1. Mixer detection
    if any(d.label == "tornado_cash" for d in detections):
        return "mixer"

    # 2. Smart Contract detection
    if bytecode and bytecode not in ("0x", "0x0", "None", ""):
        return "smart contract"

    # 3. Exchange detection (Heuristic: high volume, many counterparties, specific labels)
    unique_counterparties = {
        (tx.to_address or "").lower() for tx in transactions
    } | {(tx.from_address or "").lower() for tx in transactions}
    if len(unique_counterparties) > 100 or any("exchange" in d.label.lower() for d in detections):
        return "exchange"

    # 4. Bot detection (Heuristic: high frequency, consistent intervals)
    if _is_bot_behavior(transactions):
        return "bot"

    return "user wallet"


def _is_bot_behavior(transactions: list[NormalizedTransaction]) -> bool:
    if len(transactions) < 10:
        return False

    # Sort by timestamp
    sorted_txs = sorted(transactions, key=lambda x: x.timestamp)
    intervals = []
    for i in range(1, len(sorted_txs)):
        delta = (sorted_txs[i].timestamp - sorted_txs[i-1].timestamp).total_seconds()
        intervals.append(delta)

    # Check for high frequency (e.g., more than 5 tx per minute average)
    total_duration = (sorted_txs[-1].timestamp - sorted_txs[0].timestamp).total_seconds()
    if total_duration > 0 and (len(transactions) / (total_duration / 60)) > 5:
        return True

    # Check for repeated interaction with same contracts
    to_addresses = [tx.to_address for tx in transactions if tx.to_address]
    if to_addresses:
        most_common_to = Counter(to_addresses).most_common(1)[0]
        if most_common_to[1] / len(transactions) > 0.8:
            return True

    return False
