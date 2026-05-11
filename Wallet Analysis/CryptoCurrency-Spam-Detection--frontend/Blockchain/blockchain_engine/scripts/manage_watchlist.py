from __future__ import annotations

import argparse
import json

from blockchain_engine.config import ScannerConfig
from blockchain_engine.scanner import BlockchainScanner


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage watchlist entries")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("--chain", required=True)
    add_parser.add_argument("--address", required=True)
    add_parser.add_argument("--category", required=True)
    add_parser.add_argument("--source", required=True)
    add_parser.add_argument("--confidence", type=float, default=0.8)
    add_parser.add_argument("--notes", default="")
    add_parser.add_argument("--label", default="")

    list_parser = subparsers.add_parser("list")

    args = parser.parse_args()
    scanner = BlockchainScanner(ScannerConfig())

    if args.command == "add":
        payload = scanner.watchlist.add_entry(
            address=args.address,
            chain=args.chain,
            category=args.category,
            source=args.source,
            confidence=args.confidence,
            reviewer_notes=args.notes,
            label=args.label,
        )
    else:
        payload = scanner.watchlist.list_entries()

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
