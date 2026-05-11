from __future__ import annotations

import json
import sys
import traceback
from dataclasses import asdict, is_dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from blockchain_engine.config import ScannerConfig
from blockchain_engine.scanner import BlockchainScanner

# Errors raised when the client closes the connection before we finish writing
_BROKEN_PIPE = (BrokenPipeError, ConnectionAbortedError, ConnectionResetError)


def run_api_server(host: str = "127.0.0.1", port: int = 8055) -> None:
    scanner = BlockchainScanner(ScannerConfig())

    class ApiHandler(BaseHTTPRequestHandler):
        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(200)
            self._add_cors_headers()
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)

            try:
                if parsed.path == "/health":
                    self._send_json({"status": "ok", "version": "1.0.0"})
                    return

                if parsed.path == "/health/chains":
                    payload = scanner.get_chain_health()
                    self._send_json({"chains": payload})
                    return

                if parsed.path == "/screen":
                    payload = scanner.screen_address(
                        chain=_single(query, "chain"),
                        address=_single(query, "address"),
                    )
                    self._send_json(payload, dataclass_like=True)
                    return

                if parsed.path == "/explore/address":
                    payload = scanner.explore_address(
                        chain=_single(query, "chain"),
                        address=_single(query, "address"),
                        limit=int(query.get("limit", ["50"])[0]),
                    )
                    self._send_json(payload)
                    return

                if parsed.path == "/explore/tx":
                    payload = scanner.explore_transaction(_single(query, "tx_hash"))
                    self._send_json(
                        payload or {"message": "not found"},
                        status=200 if payload else 404,
                    )
                    return

                if parsed.path == "/graph":
                    payload = scanner.build_graph(
                        chain=_single(query, "chain"),
                        address=_single(query, "address"),
                        limit=int(query.get("limit", ["50"])[0]),
                    )
                    self._send_json(payload)
                    return

                if parsed.path == "/cluster":
                    payload = scanner.cluster_address(
                        chain=_single(query, "chain"),
                        address=_single(query, "address"),
                        limit=int(query.get("limit", ["50"])[0]),
                    )
                    self._send_json(payload)
                    return

                if parsed.path == "/risk":
                    payload = scanner.scan_address(
                        chain=_single(query, "chain"),
                        address=_single(query, "address"),
                        limit=int(query.get("limit", ["50"])[0]),
                    )
                    self._send_json(payload, dataclass_like=True)
                    return

                if parsed.path == "/alerts":
                    payload = scanner.evaluate_alerts(
                        chain=_single(query, "chain"),
                        address=_single(query, "address"),
                        limit=int(query.get("limit", ["50"])[0]),
                    )
                    self._send_json(payload)
                    return

                if parsed.path == "/watchlist":
                    payload = scanner.watchlist.list_entries()
                    self._send_json(payload)
                    return

                if parsed.path == "/feeds/sync":
                    result = scanner.sync_public_feeds()
                    self._send_json({"synced": result})
                    return

                self._send_json({"error": "not found"}, status=404)

            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
            except _BROKEN_PIPE:
                # Client disconnected — nothing to do
                pass
            except Exception as exc:  # pragma: no cover
                traceback.print_exc(file=sys.stderr)
                try:
                    self._send_json({"error": str(exc)}, status=500)
                except _BROKEN_PIPE:
                    pass

        def log_message(self, format: str, *args: object) -> None:
            return

        def _add_cors_headers(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

        def _send_json(
            self,
            payload: object,
            *,
            status: int = 200,
            dataclass_like: bool = False,
        ) -> None:
            if dataclass_like:
                body = json.dumps(
                    payload,
                    default=lambda obj: asdict(obj) if is_dataclass(obj) else str(obj),
                    indent=2,
                )
            else:
                body = json.dumps(payload, indent=2)
            encoded = body.encode("utf-8")
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self._add_cors_headers()
                self.end_headers()
                self.wfile.write(encoded)
            except _BROKEN_PIPE:
                pass

    server = ThreadingHTTPServer((host, port), ApiHandler)
    print(f"🔗 Blockchain Engine API running on http://{host}:{port}")
    print(f"   Endpoints: /health /screen /risk /explore/address /graph /cluster /alerts /watchlist /feeds/sync")
    server.serve_forever()


def _single(query: dict[str, list[str]], key: str) -> str:
    value = query.get(key, [""])[0]
    if not value:
        raise ValueError(f"Missing query parameter: {key}")
    return value
