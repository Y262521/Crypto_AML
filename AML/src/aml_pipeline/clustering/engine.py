"""
Clustering Engine
==================
Orchestrates the full clustering pipeline:

  1. Load transactions via a BlockchainAdapter
  2. Build a NetworkX directed graph
  3. Run all enabled heuristics to find address links
  4. Merge links with Union-Find into clusters
  5. Score and label each cluster
  6. (Optional) persist results to MongoDB + Neo4j

Designed for incremental updates: pass `incremental=True` and only
new transactions are processed; existing clusters are updated in-place.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import networkx as nx

from ..config import Config, load_config
from .base import BlockchainAdapter
from .eth_adapter import EthereumAdapter
from .graph_builder import build_graph
from .heuristics import (
    BehavioralSimilarityHeuristic,
    ContractInteractionHeuristic,
    FanPatternHeuristic,
    LoopDetectionHeuristic,
    TemporalHeuristic,
    TokenFlowHeuristic,
    PeelChainHeuristic,
    DustingAttackHeuristic,
    AddressPoisoningHeuristic,
    LayeringHeuristic,
    CommunityDetectionHeuristic,
)
from .heuristics.base_heuristic import BaseHeuristic
from .risk_scorer import ClusterResult, score_cluster
from .union_find import UnionFind

logger = logging.getLogger(__name__)

_DEFAULT_HEURISTICS = [
    # Intermediate
    BehavioralSimilarityHeuristic,
    ContractInteractionHeuristic,
    TokenFlowHeuristic,
    TemporalHeuristic,
    FanPatternHeuristic,
    LoopDetectionHeuristic,
    # Advanced
    PeelChainHeuristic,
    DustingAttackHeuristic,
    AddressPoisoningHeuristic,
    LayeringHeuristic,
    CommunityDetectionHeuristic,
]


def _cluster_id(addresses: List[str]) -> str:
    """Deterministic cluster ID from sorted member addresses."""
    key = "|".join(sorted(addresses))
    return "C-" + hashlib.sha1(key.encode()).hexdigest()[:12].upper()


def _compute_indicators(
    addresses: List[str],
    G: nx.MultiDiGraph,
    cfg: Config,
) -> Dict[str, object]:
    """Compute raw behavioural stats for a cluster."""
    addr_set = set(addresses)
    total_eth = 0.0
    tx_count = 0
    internal_tx = 0
    contract_calls = 0
    timestamps = []

    for u, v, data in G.edges(data=True):
        if u in addr_set or v in addr_set:
            tx_count += 1
            total_eth += data.get("value_eth", 0.0) or 0.0
            if data.get("is_contract_call"):
                contract_calls += 1
            ts = data.get("timestamp")
            if ts:
                timestamps.append(float(ts))
        if u in addr_set and v in addr_set:
            internal_tx += 1

    time_span_seconds = (max(timestamps) - min(timestamps)) if len(timestamps) >= 2 else 0

    return {
        "size": len(addresses),
        "total_eth_volume": round(total_eth, 6),
        "total_tx_count": tx_count,
        "internal_tx_count": internal_tx,
        "contract_call_count": contract_calls,
        "time_span_seconds": int(time_span_seconds),
        "min_shared_counterparties": cfg.clustering_min_shared_counterparties,
    }


class ClusteringEngine:
    """
    Main entry point for address clustering.

    Usage:
        engine = ClusteringEngine()
        results = engine.run()
        for cluster in results:
            print(cluster.cluster_id, cluster.risk_score, cluster.labels)
    """

    def __init__(
        self,
        cfg: Optional[Config] = None,
        adapter: Optional[BlockchainAdapter] = None,
        heuristics: Optional[List[type]] = None,
    ):
        self.cfg = cfg or load_config()
        self.adapter = adapter or EthereumAdapter(self.cfg)
        heuristic_classes = heuristics or _DEFAULT_HEURISTICS
        self.heuristics: List[BaseHeuristic] = [H(self.cfg) for H in heuristic_classes]

    # ── public API ───────────────────────────────────────────────────────────

    def run(
        self,
        source: str = "auto",
        persist: bool = False,
        min_cluster_size: int = 2,
    ) -> List[ClusterResult]:
        """
        Run the full clustering pipeline and return a list of ClusterResult.

        Args:
            source:           data source hint passed to the adapter
            persist:          if True, save results to MongoDB and Neo4j
            min_cluster_size: skip singleton clusters (size < this value)
        """
        logger.info("ClusteringEngine: loading transactions (source=%s)", source)
        transactions = list(self.adapter.iter_transactions(source=source))
        if not transactions:
            logger.warning("No transactions found — clustering aborted.")
            return []

        logger.info("Building graph from %d transactions", len(transactions))
        G = build_graph(transactions)

        logger.info("Running %d heuristics", len(self.heuristics))
        uf = UnionFind(list(G.nodes()))

        # Track which heuristics fired for each pair
        pair_heuristics: Dict[tuple, List[str]] = {}

        for heuristic in self.heuristics:
            logger.info("  → %s", heuristic.name)
            try:
                links = heuristic.find_links(G)
            except Exception as exc:
                logger.warning("Heuristic %s failed: %s", heuristic.name, exc)
                continue

            for a, b in links:
                if not G.has_node(a) or not G.has_node(b):
                    continue
                uf.union(a, b)
                pair = tuple(sorted([a, b]))
                pair_heuristics.setdefault(pair, [])
                if heuristic.name not in pair_heuristics[pair]:
                    pair_heuristics[pair].append(heuristic.name)

        # Build cluster → heuristics mapping
        cluster_heuristics: Dict[str, List[str]] = {}
        for (a, b), hnames in pair_heuristics.items():
            root = uf.find(a)
            for h in hnames:
                if h not in cluster_heuristics.get(root, []):
                    cluster_heuristics.setdefault(root, []).append(h)

        # Assemble results
        results: List[ClusterResult] = []
        for root, members in uf.clusters().items():
            if len(members) < min_cluster_size:
                continue
            addr_list = sorted(members)
            cid = _cluster_id(addr_list)
            fired = cluster_heuristics.get(root, [])
            indicators = _compute_indicators(addr_list, G, self.cfg)
            result = score_cluster(cid, members, fired, indicators)
            results.append(result)

        results.sort(key=lambda r: r.risk_score, reverse=True)
        logger.info("Clustering complete: %d clusters found", len(results))

        if persist:
            self._persist(results, G)

        return results

    def run_incremental(
        self,
        new_transactions,
        existing_graph: Optional[nx.MultiDiGraph] = None,
        persist: bool = False,
    ) -> List[ClusterResult]:
        """
        Incremental update: add new transactions to an existing graph
        and re-run heuristics only on affected subgraph.
        """
        new_G = build_graph(new_transactions)
        if existing_graph is not None:
            # Merge new edges into existing graph
            for u, v, key, data in new_G.edges(keys=True, data=True):
                existing_graph.add_edge(u, v, key=key, **data)
            G = existing_graph
        else:
            G = new_G

        # Re-run on full merged graph (subgraph optimisation is future work)
        uf = UnionFind(list(G.nodes()))
        pair_heuristics: Dict[tuple, List[str]] = {}

        for heuristic in self.heuristics:
            try:
                links = heuristic.find_links(G)
            except Exception as exc:
                logger.warning("Heuristic %s failed: %s", heuristic.name, exc)
                continue
            for a, b in links:
                if not G.has_node(a) or not G.has_node(b):
                    continue
                uf.union(a, b)
                pair = tuple(sorted([a, b]))
                pair_heuristics.setdefault(pair, [])
                if heuristic.name not in pair_heuristics[pair]:
                    pair_heuristics[pair].append(heuristic.name)

        cluster_heuristics: Dict[str, List[str]] = {}
        for (a, b), hnames in pair_heuristics.items():
            root = uf.find(a)
            for h in hnames:
                cluster_heuristics.setdefault(root, []).append(h)

        results: List[ClusterResult] = []
        for root, members in uf.clusters().items():
            if len(members) < 2:
                continue
            addr_list = sorted(members)
            cid = _cluster_id(addr_list)
            fired = list(set(cluster_heuristics.get(root, [])))
            indicators = _compute_indicators(addr_list, G, self.cfg)
            result = score_cluster(cid, members, fired, indicators)
            results.append(result)

        results.sort(key=lambda r: r.risk_score, reverse=True)
        if persist:
            self._persist(results, G)
        return results

    # ── persistence ──────────────────────────────────────────────────────────

    def _persist(self, results: List[ClusterResult], G: nx.MultiDiGraph) -> None:
        """Save cluster results to MongoDB and update Neo4j cluster labels."""
        self._save_to_mongo(results)
        self._save_to_neo4j(results)

    def _save_to_mongo(self, results: List[ClusterResult]) -> None:
        try:
            from pymongo import MongoClient, UpdateOne
            client = MongoClient(self.cfg.mongo_uri)
            col = client[self.cfg.mongo_processed_db]["address_clusters"]
            now = datetime.now(timezone.utc)
            ops = []
            for r in results:
                doc = {
                    "cluster_id": r.cluster_id,
                    "addresses": r.addresses,
                    "risk_score": r.risk_score,
                    "labels": r.labels,
                    "heuristics_fired": r.heuristics_fired,
                    "indicators": r.indicators,
                    "explanation": r.explanation,
                    "updated_at": now,
                }
                ops.append(UpdateOne(
                    {"cluster_id": r.cluster_id},
                    {"$set": doc},
                    upsert=True,
                ))
            if ops:
                col.bulk_write(ops, ordered=False)
                logger.info("Persisted %d clusters to MongoDB", len(ops))
            client.close()
        except Exception as exc:
            logger.warning("MongoDB persist failed: %s", exc)

    def _save_to_neo4j(self, results: List[ClusterResult]) -> None:
        try:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(
                self.cfg.neo4j_uri,
                auth=(self.cfg.neo4j_user, self.cfg.neo4j_password),
            )
            query = """
            UNWIND $rows AS row
            MATCH (a:Address {address: row.address})
            SET a.cluster_id   = row.cluster_id,
                a.risk_score   = row.risk_score,
                a.cluster_labels = row.labels
            """
            rows = []
            for r in results:
                for addr in r.addresses:
                    rows.append({
                        "address": addr,
                        "cluster_id": r.cluster_id,
                        "risk_score": r.risk_score,
                        "labels": r.labels,
                    })
            batch_size = self.cfg.neo4j_batch_size
            with driver.session(database=self.cfg.neo4j_database) as session:
                for i in range(0, len(rows), batch_size):
                    session.run(query, rows=rows[i:i + batch_size]).consume()
            driver.close()
            logger.info("Updated %d address nodes in Neo4j with cluster labels", len(rows))
        except Exception as exc:
            logger.warning("Neo4j persist failed: %s", exc)
