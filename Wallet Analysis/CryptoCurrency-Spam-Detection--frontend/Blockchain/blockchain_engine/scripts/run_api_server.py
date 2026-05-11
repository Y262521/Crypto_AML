from __future__ import annotations

import argparse
import os
from pathlib import Path


def _load_env() -> None:
    """Load .env from the Blockchain directory if python-dotenv is available."""
    try:
        from dotenv import load_dotenv  # type: ignore
        env_path = Path(__file__).resolve().parents[3] / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=False)
            print(f"   Loaded env from {env_path}")
    except ImportError:
        # python-dotenv not installed — fall back to manual parse
        env_path = Path(__file__).resolve().parents[3] / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value


def main() -> None:
    _load_env()

    from blockchain_engine.api import run_api_server

    parser = argparse.ArgumentParser(description="Run blockchain intelligence API server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8055)
    args = parser.parse_args()
    run_api_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
