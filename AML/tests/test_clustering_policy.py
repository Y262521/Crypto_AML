from __future__ import annotations

import unittest

from aml_pipeline.clustering.cluster_result import build_cluster_result
from aml_pipeline.clustering.policy import should_merge_pair


class ClusteringPolicyTests(unittest.TestCase):
    def test_merge_requires_primary_and_min_support(self) -> None:
        self.assertFalse(should_merge_pair({"fan_pattern"}, min_support=2))
        self.assertTrue(should_merge_pair({"fan_pattern", "loop_detection"}, min_support=2))
        self.assertTrue(should_merge_pair({"repeated_flow"}, min_support=1))

    def test_heuristics_are_ranked_by_support(self) -> None:
        result = build_cluster_result(
            "cluster-1",
            ["a", "b", "c"],
            ["loop_detection", "fan_pattern", "behavioral_similarity"],
            {"min_shared_counterparties": 3},
            heuristic_counts={
                "behavioral_similarity": 1,
                "fan_pattern": 4,
                "loop_detection": 2,
            },
        )
        self.assertEqual(result.heuristics_fired[0], "fan_pattern")


if __name__ == "__main__":
    unittest.main()
