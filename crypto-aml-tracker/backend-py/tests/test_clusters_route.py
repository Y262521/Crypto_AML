from __future__ import annotations

import unittest

from routes.clusters import OwnerListCreateRequest, _cluster_payload, _owner_payload


class ClustersRouteTests(unittest.TestCase):
    def test_owner_request_normalizes_known_addresses(self) -> None:
        payload = OwnerListCreateRequest(
            full_name=" Dawit Alemu ",
            known_addresses="0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa,\n0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            city=" Addis Ababa ",
            country=" Ethiopia ",
        )

        self.assertEqual(payload.full_name, "Dawit Alemu")
        self.assertEqual(payload.city, "Addis Ababa")
        self.assertEqual(payload.country, "Ethiopia")
        self.assertEqual(
            payload.known_addresses,
            [
                "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            ],
        )

    def test_owner_payload_returns_none_when_cluster_is_unlabeled(self) -> None:
        self.assertIsNone(_owner_payload({}))

    def test_cluster_payload_includes_label_status_and_owner_details(self) -> None:
        payload = _cluster_payload(
            {
                "id": "C-123",
                "cluster_size": 2,
                "total_balance": 4.25,
                "risk_level": "normal",
                "label_status": "matched",
                "matched_owner_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "owner_registry_id": 9,
                "full_name": "Hana Bekele",
                "entity_type": "individual",
                "list_category": "watchlist",
                "country": "Ethiopia",
                "city": "Addis Ababa",
                "specifics": "Apartment 5",
                "street_address": "Bole Road",
                "locality": "Bole",
                "administrative_area": "Addis Ababa",
                "postal_code": "1000",
                "source_reference": "Registry",
                "notes": "Known counterparty",
            },
            addresses_map={
                "C-123": [
                    {
                        "address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                        "total_in": 2.0,
                        "total_out": 1.0,
                    }
                ]
            },
            activity_map={"C-123": {"address_count": 1, "total_in": 2.0, "total_out": 1.0, "total_tx_count": 3}},
            evidence_map={},
        )

        self.assertEqual(payload["label_status"], "matched")
        self.assertEqual(payload["matched_owner_address"], "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        self.assertEqual(payload["owner"]["full_name"], "Hana Bekele")
        self.assertEqual(payload["activity"]["total_tx_count"], 3)


if __name__ == "__main__":
    unittest.main()
