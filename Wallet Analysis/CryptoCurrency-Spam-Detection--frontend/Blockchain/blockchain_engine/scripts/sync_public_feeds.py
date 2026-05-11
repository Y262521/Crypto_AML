from __future__ import annotations

import json

from blockchain_engine.config import ScannerConfig
from blockchain_engine.scanner import BlockchainScanner


def main() -> None:
    scanner = BlockchainScanner(ScannerConfig())
    summary = scanner.sync_public_feeds()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
