from __future__ import annotations

import json

from blockchain_engine.config import ScannerConfig
from blockchain_engine.scanner import BlockchainScanner


def main() -> None:
    scanner = BlockchainScanner(ScannerConfig())
    print(json.dumps(scanner.get_chain_health(), indent=2))


if __name__ == "__main__":
    main()
