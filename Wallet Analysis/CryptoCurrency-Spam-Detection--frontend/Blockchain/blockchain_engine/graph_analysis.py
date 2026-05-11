from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import datetime
from typing import Any

from blockchain_engine.models import GraphEdge, GraphNode


class GraphAnalyzer:
    def build_graph(
        self,
        *,
        root_address: str,
        risk_score: int,
        label: str,
        entity_label: str = "user wallet",
        transactions: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        nodes: dict[str, GraphNode] = {
            root_address.lower(): GraphNode(
                id=root_address,
                risk=label,
                score=risk_score,
                entity_label=entity_label,
            )
        }
        edges: list[GraphEdge] = []

        for tx in transactions:
            source = tx["from_address"]
            target = tx["to_address"] or "unknown"
            nodes.setdefault(source.lower(), GraphNode(id=source, risk="unknown", score=0))
            nodes.setdefault(target.lower(), GraphNode(id=target, risk="unknown", score=0))
            edges.append(
                GraphEdge(
                    source=source,
                    target=target,
                    tx_hash=tx["tx_hash"],
                    value=tx["value"],
                    asset=tx["asset"],
                    timestamp=tx["timestamp"],
                )
            )

        return {
            "nodes": [asdict(node) for node in nodes.values()],
            "edges": [asdict(edge) for edge in edges],
        }

    def cluster_addresses(self, transactions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        outbound_counter: Counter[str] = Counter()
        pair_counter: Counter[tuple[str, str]] = Counter()
        reverse_pairs: defaultdict[frozenset[str], int] = defaultdict(int)
        funding_times: defaultdict[str, list[datetime]] = defaultdict(list)

        for tx in transactions:
            source = tx["from_address"].lower()
            target = (tx["to_address"] or "").lower()
            if not source or not target:
                continue
            outbound_counter[source] += 1
            pair_counter[(source, target)] += 1
            reverse_pairs[frozenset({source, target})] += 1
            
            ts = datetime.fromisoformat(tx["timestamp"].replace("Z", "+00:00"))
            funding_times[source].append(ts)

        clusters: list[dict[str, Any]] = []
        for source, count in outbound_counter.items():
            # 1. Hub funding cluster (Existing)
            related = [target for (src, target), total in pair_counter.items() if src == source and total >= 2]
            if len(related) >= 2:
                clusters.append(
                    {
                        "type": "hub_funding_cluster",
                        "seed": source,
                        "members": [source, *related],
                        "reason": "One address repeatedly funds many related addresses",
                    }
                )
            
            # 2. Fresh wallet funding cluster (Requirement 5)
            # Check if one address funded many different addresses in a short window
            targets = [target for (src, target) in pair_counter.keys() if src == source]
            if len(targets) >= 5:
                times = sorted(funding_times[source])
                # If first and last funding are within 24 hours
                if (times[-1] - times[0]).total_seconds() < 86400:
                    clusters.append(
                        {
                            "type": "rapid_funding_cluster",
                            "seed": source,
                            "members": [source, *targets],
                            "reason": "One address funded many fresh wallets in a short window",
                        }
                    )

        # 3. Bidirectional cluster (Existing)
        for pair, count in reverse_pairs.items():
            if count < 2 or len(pair) != 2:
                continue
            members = sorted(pair)
            clusters.append(
                {
                    "type": "bidirectional_cluster",
                    "seed": members[0],
                    "members": members,
                    "reason": "Bidirectional repeated fund flows detected",
                }
            )

        return clusters
