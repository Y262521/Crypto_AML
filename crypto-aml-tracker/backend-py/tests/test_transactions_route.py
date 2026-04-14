from __future__ import annotations

import unittest

from routes.transactions import _latest_transactions_sql, _risk_label, _risk_score


class TransactionsRouteSqlTests(unittest.TestCase):
    def test_latest_transactions_query_defaults_to_amount_sorting(self) -> None:
        sql = _latest_transactions_sql()

        self.assertIn("ORDER BY value_eth DESC, block_number DESC, tx_hash DESC", sql)
        self.assertNotIn("id DESC", sql)

    def test_risk_label_uses_score_thresholds(self) -> None:
        self.assertEqual(_risk_score(10.0, 10.0), 75.0)
        self.assertEqual(_risk_label(10.0, 10.0), "Medium")
        self.assertEqual(_risk_score(20.0, 10.0), 100.0)
        self.assertEqual(_risk_label(20.0, 10.0), "High")
        self.assertEqual(_risk_score(6.0, 10.0), 45.0)
        self.assertEqual(_risk_label(6.0, 10.0), "Medium")
        self.assertEqual(_risk_score(3.0, 10.0), 22.5)
        self.assertEqual(_risk_label(3.0, 10.0), "Low")


if __name__ == "__main__":
    unittest.main()
