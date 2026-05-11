from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from blockchain_engine.config import ScannerConfig
from blockchain_engine.scanner import BlockchainScanner


def main() -> None:
    parser = argparse.ArgumentParser(description="Run blockchain risk scan")
    parser.add_argument("--chain", required=True, choices=["ethereum", "bsc", "polygon", "arbitrum", "bitcoin"])
    parser.add_argument("--address", required=True)
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()

    scanner = BlockchainScanner(ScannerConfig())
    result = scanner.scan_address(args.chain, args.address, limit=args.limit)
    print(
        json.dumps(
            {
                "address": result.address,
                "chain": result.chain,
                "score": result.score,
                "label": result.label,
                "entity_label": result.entity_label,
                "reasons": result.reasons,
                "detections": [asdict(item) for item in result.detections],
                "transactions": [tx.to_dict() for tx in result.transactions],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
