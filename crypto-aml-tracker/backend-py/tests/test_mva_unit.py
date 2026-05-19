"""
Unit tests for MVA helpers and balance RPC URL selection (no MySQL required).
"""

import os
import asyncio
import unittest
from datetime import datetime, timezone, timedelta


class TestMvaFlags(unittest.TestCase):
    def test_flags_naive_iso_string_no_crash(self):
        from routes.mva import generate_intelligence_flags

        summary = {
            "total_value_usd": 1000.0,
            "stablecoin_value_usd": 100.0,
            "eth_value_usd": 900.0,
            "updated_at": "2025-01-15T12:00:00",
        }
        flags = generate_intelligence_flags(summary, [])
        self.assertIsInstance(flags, list)

    def test_flags_datetime_naive_no_crash(self):
        from routes.mva import generate_intelligence_flags

        summary = {
            "total_value_usd": 1000.0,
            "stablecoin_value_usd": 100.0,
            "eth_value_usd": 900.0,
            "updated_at": datetime(2025, 1, 1, 0, 0, 0),
        }
        flags = generate_intelligence_flags(summary, [])
        self.assertIsInstance(flags, list)

    def test_flags_recent_update_no_dormant(self):
        from routes.mva import generate_intelligence_flags

        recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        summary = {
            "total_value_usd": 5000.0,
            "stablecoin_value_usd": 100.0,
            "eth_value_usd": 4900.0,
            "updated_at": recent,
        }
        flags = generate_intelligence_flags(summary, [])
        types = {f["type"] for f in flags}
        self.assertNotIn("dormant", types)


class TestFormatTs(unittest.TestCase):
    def test_format_naive_datetime(self):
        from routes.mva import _format_ts_utc

        s = _format_ts_utc(datetime(2026, 5, 1, 12, 0, 0))
        self.assertIn("2026-05-01", s)
        self.assertIn("+00:00", s)


class TestRpcUrlSelection(unittest.TestCase):
    def setUp(self):
        self._saved = os.environ.copy()

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved)

    def test_demo_url_skipped(self):
        from services.balance_aggregator import _collect_rpc_urls

        os.environ["ALCHEMY_RPC"] = "https://eth-mainnet.g.alchemy.com/v2/demo"
        os.environ["RPC_URL"] = "https://example-custom-rpc.invalid/v1"
        urls = _collect_rpc_urls()
        self.assertTrue(any("example-custom-rpc" in u for u in urls))
        self.assertFalse(any("demo" in u for u in urls))


class TestJsonRpcSmoke(unittest.TestCase):
    """Live JSON-RPC call (skipped if network blocked)."""

    def test_eth_block_number(self):
        async def _run():
            from services.balance_aggregator import BalanceAggregator

            agg = BalanceAggregator()
            data, err = await agg._jsonrpc(
                {"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1}
            )
            self.assertIsNone(err, msg=err)
            self.assertIsNotNone(data)
            self.assertIn("result", data)
            self.assertTrue(data["result"].startswith("0x"))

        try:
            asyncio.run(_run())
        except OSError:
            self.skipTest("network unavailable")


if __name__ == "__main__":
    unittest.main()
