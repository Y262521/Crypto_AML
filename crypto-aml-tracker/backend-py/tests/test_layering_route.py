from __future__ import annotations

import unittest

from routes.layering import _decode_json, _layering_payload


class LayeringRouteHelpersTests(unittest.TestCase):
    def test_decode_json_returns_default_on_invalid_payload(self) -> None:
        self.assertEqual(_decode_json("not-json", {}), {})

    def test_layering_payload_shapes_alert_fields(self) -> None:
        payload = _layering_payload(
            {
                "entity_id": "SEED",
                "entity_type": "cluster",
                "confidence_score": 0.82,
                "layering_score": 0.77,
                "placement_score": 0.71,
                "placement_confidence": 0.69,
                "method_scores_json": '{"peeling_chain": 0.82, "bridge_hopping": 0.73}',
                "methods_json": '["bridge_hopping", "peeling_chain", "peeling_chain"]',
                "reasons_json": '["Peeling pattern observed across 3 hops."]',
                "supporting_tx_hashes_json": '["0xabc", "0xdef"]',
                "evidence_ids_json": '["LEV-123"]',
                "metrics_json": '{"detector_count": 2, "bridge_pair_count": 1}',
                "validation_status": "existing",
                "validation_confidence": 0.9,
                "source_kind": "existing",
                "placement_behaviors_json": '["structuring"]',
                "first_seen_at": "2026-01-01T00:00:00",
                "last_seen_at": "2026-01-01T00:10:00",
            },
            ["0xaaa", "0xbbb"],
        )

        self.assertEqual(payload["address_count"], 2)
        self.assertEqual(payload["primary_method"], "peeling_chain")
        self.assertEqual(payload["methods"], ["peeling_chain", "bridge_hopping"])
        self.assertEqual(payload["risk_score"], 77.0)
        self.assertEqual(payload["evidence_count"], 1)
        self.assertEqual(payload["placement_behaviors"], ["structuring"])
        self.assertIn("Peeling chains dominate this entity", payload["reason"])
        self.assertIn("Cross-chain & bridge hopping also scores strongly enough", payload["reason"])
        self.assertIn("Placement seeding for this entity was already linked to structuring.", payload["reason"])
        self.assertIn("1 bridge-linked transfer pair supports the trace.", payload["reason"])

    def test_layering_payload_uses_raw_reason_when_no_method_exists(self) -> None:
        payload = _layering_payload(
            {
                "entity_id": "SEED",
                "entity_type": "address",
                "confidence_score": 0.51,
                "layering_score": 0.49,
                "placement_score": 0.41,
                "placement_confidence": 0.4,
                "method_scores_json": "{}",
                "methods_json": "[]",
                "reasons_json": '["Observed suspicious layering path."]',
                "supporting_tx_hashes_json": "[]",
                "evidence_ids_json": "[]",
                "metrics_json": "{}",
                "validation_status": "existing",
                "validation_confidence": 0.7,
                "source_kind": "existing",
                "placement_behaviors_json": "[]",
                "first_seen_at": None,
                "last_seen_at": None,
            },
            ["0xaaa"],
        )

        self.assertEqual(payload["reason"], "Observed suspicious layering path.")


if __name__ == "__main__":
    unittest.main()
