from __future__ import annotations

import argparse
import json

from blockchain_engine.config import ScannerConfig
from blockchain_engine.scanner import BlockchainScanner


def main() -> None:
    parser = argparse.ArgumentParser(description="Build graph and clusters for an address")
    parser.add_argument("--chain", required=True, choices=["ethereum", "bsc", "polygon", "arbitrum", "bitcoin"])
    parser.add_argument("--address", required=True)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    scanner = BlockchainScanner(ScannerConfig())
    payload = {
        "graph": scanner.build_graph(args.chain, args.address, limit=args.limit),
        "clusters": scanner.cluster_address(args.chain, args.address, limit=args.limit),
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
