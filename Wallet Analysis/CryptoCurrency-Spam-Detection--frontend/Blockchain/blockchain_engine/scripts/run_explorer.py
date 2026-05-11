from __future__ import annotations

import argparse
import json

from blockchain_engine.config import ScannerConfig
from blockchain_engine.scanner import BlockchainScanner


def main() -> None:
    parser = argparse.ArgumentParser(description="Run address or transaction explorer")
    parser.add_argument("--chain", choices=["ethereum", "bsc", "polygon", "arbitrum", "bitcoin"])
    parser.add_argument("--address")
    parser.add_argument("--tx-hash")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    scanner = BlockchainScanner(ScannerConfig())
    if args.tx_hash:
        payload = scanner.explore_transaction(args.tx_hash)
    elif args.chain and args.address:
        payload = scanner.explore_address(args.chain, args.address, limit=args.limit)
    else:
        raise SystemExit("Provide either --tx-hash or both --chain and --address")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
