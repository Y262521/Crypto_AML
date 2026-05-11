from __future__ import annotations

import argparse
import json

from blockchain_engine.config import ScannerConfig
from blockchain_engine.scanner import BlockchainScanner


def main() -> None:
    parser = argparse.ArgumentParser(description="Run alert evaluation")
    parser.add_argument("--chain", required=True, choices=["ethereum", "bsc", "polygon", "arbitrum", "bitcoin"])
    parser.add_argument("--address", required=True)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    scanner = BlockchainScanner(ScannerConfig())
    payload = scanner.evaluate_alerts(args.chain, args.address, limit=args.limit)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
