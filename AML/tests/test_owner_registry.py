from __future__ import annotations

import unittest

from aml_pipeline.clustering.owner_registry import (
    LABEL_STATUS_CONFLICT,
    LABEL_STATUS_MATCHED,
    _select_cluster_label,
    normalize_owner_addresses,
)


class OwnerRegistryTests(unittest.TestCase):
    def test_normalize_owner_addresses_lowercases_and_deduplicates(self) -> None:
        addresses = normalize_owner_addresses(
            [
                "0xAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                " 0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb ",
            ]
        )

        self.assertEqual(
            addresses,
            [
                "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            ],
        )

    def test_normalize_owner_addresses_rejects_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            normalize_owner_addresses(["not-an-address"])

    def test_select_cluster_label_prefers_highest_match_count(self) -> None:
        match = _select_cluster_label(
            [
                {"owner_list_id": 1, "address": "0x1", "is_primary": 0},
                {"owner_list_id": 1, "address": "0x2", "is_primary": 1},
                {"owner_list_id": 2, "address": "0x3", "is_primary": 1},
            ]
        )

        self.assertEqual(match["owner_id"], 1)
        self.assertEqual(match["label_status"], LABEL_STATUS_MATCHED)
        self.assertEqual(match["matched_owner_address"], "0x2")

    def test_select_cluster_label_marks_equal_top_matches_as_conflict(self) -> None:
        match = _select_cluster_label(
            [
                {"owner_list_id": 1, "address": "0x1", "is_primary": 0},
                {"owner_list_id": 2, "address": "0x2", "is_primary": 0},
            ]
        )

        self.assertIsNone(match["owner_id"])
        self.assertEqual(match["label_status"], LABEL_STATUS_CONFLICT)
        self.assertIsNone(match["matched_owner_address"])


if __name__ == "__main__":
    unittest.main()
