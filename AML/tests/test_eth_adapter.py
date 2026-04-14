from __future__ import annotations

import unittest

from aml_pipeline.clustering.eth_adapter import EthereumAdapter


class EthereumAdapterSelectionTests(unittest.TestCase):
    def test_auto_prefers_mariadb_without_querying_mongo(self) -> None:
        class Adapter(EthereumAdapter):
            def __init__(self):
                pass

            def _count_mariadb_transactions(self) -> int:
                return 3

            def _iter_from_mariadb(self):
                yield "mariadb"

            def _count_raw_mongo_transactions(self) -> int:
                raise AssertionError("MongoDB should not be queried when MariaDB has data")

        self.assertEqual(list(Adapter().iter_transactions()), ["mariadb"])

    def test_auto_falls_back_to_csv_when_databases_are_empty(self) -> None:
        class Adapter(EthereumAdapter):
            def __init__(self):
                pass

            def _count_mariadb_transactions(self) -> int:
                return 0

            def _count_raw_mongo_transactions(self) -> int:
                return 0

            def _iter_from_csv(self):
                yield "csv"

        self.assertEqual(list(Adapter().iter_transactions()), ["csv"])


if __name__ == "__main__":
    unittest.main()
