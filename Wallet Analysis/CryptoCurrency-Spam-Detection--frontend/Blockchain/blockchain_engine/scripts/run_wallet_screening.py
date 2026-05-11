from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from blockchain_engine.config import ScannerConfig
from blockchain_engine.scanner import BlockchainScanner


def main() -> None:
    parser = argparse.ArgumentParser(description="Run wallet screening")
    parser.add_argument("--chain", required=True, choices=["ethereum", "bsc", "polygon", "arbitrum", "bitcoin"])
    parser.add_argument("--address", required=True)
    args = parser.parse_args()

    scanner = BlockchainScanner(ScannerConfig())
    result = scanner.screen_address(args.chain, args.address)
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
