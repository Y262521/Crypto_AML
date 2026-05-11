from __future__ import annotations

import argparse
import json

from blockchain_engine.config import ScannerConfig
from blockchain_engine.scanner import BlockchainScanner


def main() -> None:
    parser = argparse.ArgumentParser(description="Run cross-chain blockchain scan")
    parser.add_argument("--ethereum")
    parser.add_argument("--bsc")
    parser.add_argument("--polygon")
    parser.add_argument("--arbitrum")
    parser.add_argument("--bitcoin")
    parser.add_argument("--limit", type=int, default=15)
    args = parser.parse_args()

    addresses = {
        chain: value
        for chain, value in {
            "ethereum": args.ethereum,
            "bsc": args.bsc,
            "polygon": args.polygon,
            "arbitrum": args.arbitrum,
            "bitcoin": args.bitcoin,
        }.items()
        if value
    }
    if not addresses:
        raise SystemExit("Provide at least one chain address")

    scanner = BlockchainScanner(ScannerConfig())
    results = scanner.scan_cross_chain(addresses=addresses, limit=args.limit)
    print(
        json.dumps(
            {
                chain: {
                    "score": result.score,
                    "label": result.label,
                    "reasons": result.reasons,
                    "transactions": [tx.to_dict() for tx in result.transactions],
                }
                for chain, result in results.items()
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
