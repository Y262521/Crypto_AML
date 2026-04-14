from __future__ import annotations

import unittest

from aml_pipeline.clustering.engine import _normalize_text_for_storage
from aml_pipeline.etl.load.neo4j_loader import _build_transactions_query


class StorageCompatibilityTests(unittest.TestCase):
    def test_neo4j_sync_query_uses_tx_hash_not_id(self) -> None:
        query, params = _build_transactions_query(min_block=123)

        self.assertIn("ORDER BY block_number ASC, tx_hash ASC", query)
        self.assertNotIn("id ASC", query)
        self.assertEqual(params, {"min_block": 123})

    def test_storage_text_normalization_removes_unicode_only_symbols(self) -> None:
        value = "Deposit→Contract→Withdraw cycles are linked — shared fan-out…"

        self.assertEqual(
            _normalize_text_for_storage(value),
            "Deposit->Contract->Withdraw cycles are linked - shared fan-out...",
        )


if __name__ == "__main__":
    unittest.main()
