from __future__ import annotations

import unittest

from routes.placement import _build_trace_paths, _decode_json, _placement_payload


class PlacementRouteHelpersTests(unittest.TestCase):
    def test_decode_json_returns_default_on_invalid_payload(self) -> None:
        self.assertEqual(_decode_json("not-json", []), [])

    def test_placement_payload_shapes_scores_and_reason(self) -> None:
        payload = _placement_payload(
            {
                "entity_id": "C-PLACEMENT",
                "entity_type": "cluster",
                "confidence_score": 0.82,
                "placement_score": 0.79,
                "behavior_score": 0.8,
                "graph_position_score": 0.78,
                "temporal_score": 0.74,
                "reasons_json": '["earliest traced entity", "no upstream suspicious history"]',
                "behaviors_json": '["smurfing", "structuring"]',
                "linked_root_entities_json": '["C-COLLECTOR"]',
                "supporting_tx_hashes_json": '["0xabc"]',
                "metrics_json": '{"avg_trace_score": 0.9, "behavior_profile": {"primary_behavior": "smurfing", "display_behaviors": ["smurfing"], "display_mode": "dominant", "ranked_behaviors": [{"behavior_type": "smurfing", "confidence_score": 0.88, "source": "origin"}]}}',
                "validation_status": "validated",
                "validation_confidence": 0.88,
                "source_kind": "existing",
                "first_seen_at": "2026-01-01T00:00:00",
                "last_seen_at": "2026-01-01T00:10:00",
            },
            ["0xaaa", "0xbbb"],
        )

        self.assertEqual(payload["reason"], "earliest traced entity")
        self.assertEqual(payload["risk_score"], 79.0)
        self.assertEqual(payload["address_count"], 2)
        self.assertEqual(payload["primary_behavior"], "smurfing")
        self.assertEqual(payload["behaviors"], ["smurfing"])
        self.assertEqual(payload["all_behaviors"], ["smurfing", "structuring"])

    def test_build_trace_paths_reconstructs_node_order(self) -> None:
        trace_paths = _build_trace_paths(
            [
                {
                    "root_entity_id": "C-COLLECTOR",
                    "origin_entity_id": "C-PLACEMENT",
                    "path_index": 3,
                    "depth": 0,
                    "upstream_entity_id": "C-PLACEMENT",
                    "downstream_entity_id": "C-COLLECTOR",
                    "path_score": 0.81,
                    "terminal_reason": "no_incoming",
                    "edge_value_eth": 2.4,
                    "supporting_tx_hashes_json": '["0x1", "0x2"]',
                    "first_seen_at": None,
                    "last_seen_at": None,
                }
            ],
            {
                "C-PLACEMENT": {"entity_id": "C-PLACEMENT", "entity_type": "cluster", "address_count": 4},
                "C-COLLECTOR": {"entity_id": "C-COLLECTOR", "entity_type": "cluster", "address_count": 1},
            },
            {
                "C-PLACEMENT": ["0xaaa", "0xbbb"],
                "C-COLLECTOR": ["0xccc"],
            },
        )

        self.assertEqual(len(trace_paths), 1)
        self.assertEqual(
            [node["entity_id"] for node in trace_paths[0]["nodes"]],
            ["C-PLACEMENT", "C-COLLECTOR"],
        )
        self.assertEqual(trace_paths[0]["edges"][0]["supporting_tx_hashes"], ["0x1", "0x2"])


if __name__ == "__main__":
    unittest.main()
