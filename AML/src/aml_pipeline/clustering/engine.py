"""
Clustering Engine
==================
Orchestrates the full clustering pipeline:

  1. Load transactions via a BlockchainAdapter
  2. Build a NetworkX directed graph
  3. Run all enabled heuristics to find address links
  4. Merge links with Union-Find into clusters
  5. Compile cluster evidence and indicators
  6. Persist results to MySQL (clusters + owner list labels + evidence)

Designed for incremental updates: pass `incremental=True` and only
new transactions are processed; existing clusters are updated in-place.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import logging
from typing import Dict, List, Optional
import unicodedata

import networkx as nx

from ..config import Config, load_config
from .base import BlockchainAdapter
from .eth_adapter import EthereumAdapter
from .graph_builder import build_graph
from .heuristics import (
    BehavioralSimilarityHeuristic,
    CommonFunderHeuristic,
    CoordinatedCashoutHeuristic,
    ContractInteractionHeuristic,
    DepositAddressReuseHeuristic,
    FanPatternHeuristic,
    LoopDetectionHeuristic,
    TemporalHeuristic,
    TokenFlowHeuristic,
)
from .policy import should_merge_pair
from .heuristics.base_heuristic import BaseHeuristic
from .cluster_result import ClusterResult, build_cluster_result
from .union_find import UnionFind

logger = logging.getLogger(__name__)

_DEFAULT_HEURISTICS = [
    DepositAddressReuseHeuristic,
    CoordinatedCashoutHeuristic,
    CommonFunderHeuristic,
    BehavioralSimilarityHeuristic,
    ContractInteractionHeuristic,
    TokenFlowHeuristic,
    TemporalHeuristic,
    FanPatternHeuristic,
    LoopDetectionHeuristic,
]

_STORAGE_CHAR_REPLACEMENTS = str.maketrans(
    {
        "→": "->",
        "←": "<-",
        "↔": "<->",
        "–": "-",
        "—": "-",
        "…": "...",
    }
)


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
    total_in = 0.0
    total_out = 0.0
    internal_eth = 0.0
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
            internal_eth += data.get("value_eth", 0.0) or 0.0
        if v in addr_set:
            total_in += data.get("value_eth", 0.0) or 0.0
        if u in addr_set:
            total_out += data.get("value_eth", 0.0) or 0.0

    time_span_seconds = (max(timestamps) - min(timestamps)) if len(timestamps) >= 2 else 0

    return {
        "size": len(addresses),
        "total_eth_volume": round(total_eth, 6),
        "internal_eth_volume": round(internal_eth, 6),
        "total_in": round(total_in, 6),
        "total_out": round(total_out, 6),
        "net_balance": round(total_in - total_out, 6),
        "total_tx_count": tx_count,
        "internal_tx_count": internal_tx,
        "contract_call_count": contract_calls,
        "time_span_seconds": int(time_span_seconds),
        "min_shared_counterparties": cfg.clustering_min_shared_counterparties,
    }


def _normalize_text_for_storage(value: str) -> str:
    normalized = value.translate(_STORAGE_CHAR_REPLACEMENTS)
    ascii_safe = (
        unicodedata.normalize("NFKD", normalized)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    return " ".join(ascii_safe.split())


def _chunked(items: List[str], size: int = 1000):
    for start in range(0, len(items), size):
        yield items[start:start + size]


class ClusteringEngine:
    """
    Main entry point for address clustering.

    Usage:
        engine = ClusteringEngine()
        results = engine.run()
        for cluster in results:
            print(cluster.cluster_id, len(cluster.addresses))
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

    def _find_pair_heuristics(self, G: nx.MultiDiGraph) -> Dict[tuple[str, str], List[str]]:
        logger.info("Running %d heuristics", len(self.heuristics))
        pair_heuristics: Dict[tuple[str, str], List[str]] = {}

        for heuristic in self.heuristics:
            logger.info("  -> %s", heuristic.name)
            try:
                links = heuristic.find_links(G)
            except Exception as exc:
                logger.warning("Heuristic %s failed: %s", heuristic.name, exc)
                continue

            unique_links = 0
            for a, b in links:
                if a == b or not G.has_node(a) or not G.has_node(b):
                    continue
                pair = tuple(sorted([a, b]))
                pair_heuristics.setdefault(pair, [])
                if heuristic.name in pair_heuristics[pair]:
                    continue
                pair_heuristics[pair].append(heuristic.name)
                unique_links += 1

            logger.info("    %s retained %d unique address pairs", heuristic.name, unique_links)

        return pair_heuristics

    def _build_results(
        self,
        G: nx.MultiDiGraph,
        pair_heuristics: Dict[tuple[str, str], List[str]],
        min_cluster_size: int,
    ) -> List[ClusterResult]:
        uf = UnionFind(list(G.nodes()))
        accepted_pairs = {
            pair: heuristics
            for pair, heuristics in pair_heuristics.items()
            if should_merge_pair(
                heuristics,
                min_support=self.cfg.clustering_min_heuristic_support,
            )
        }
        logger.info(
            "Accepted %d/%d heuristic pairs after evidence gating",
            len(accepted_pairs),
            len(pair_heuristics),
        )
        for a, b in accepted_pairs:
            uf.union(a, b)

        cluster_heuristic_counts: Dict[str, Counter[str]] = defaultdict(Counter)
        for (a, b), heuristics in pair_heuristics.items():
            root_a = uf.find(a)
            if root_a != uf.find(b):
                continue
            cluster_heuristic_counts[root_a].update(heuristics)

        results: List[ClusterResult] = []
        for root, members in uf.clusters().items():
            if len(members) < min_cluster_size:
                continue
            heuristic_counts = cluster_heuristic_counts.get(root, Counter())
            addr_list = sorted(members)
            cid = _cluster_id(addr_list)
            indicators = _compute_indicators(addr_list, G, self.cfg)
            result = build_cluster_result(
                cid,
                addr_list,
                list(heuristic_counts.keys()),
                indicators,
                heuristic_counts=dict(heuristic_counts),
            )
            results.append(result)

        results.sort(
            key=lambda r: (
                len(r.addresses),
                int(r.indicators.get("total_tx_count", 0) or 0),
                float(r.indicators.get("total_eth_volume", 0.0) or 0.0),
            ),
            reverse=True,
        )
        return results

    # ── public API ───────────────────────────────────────────────────────────

    def run(
        self,
        source: str = "auto",
        persist: bool = False,
        min_cluster_size: int = 1,
    ) -> List[ClusterResult]:
        """
        Run the full clustering pipeline and return a list of ClusterResult.

        Args:
            source:           data source hint passed to the adapter
            persist:          if True, save results to MySQL (clusters + owner labels + evidence)
            min_cluster_size: skip clusters smaller than this value
        """
        logger.info("ClusteringEngine: loading transactions (source=%s)", source)
        transactions = list(self.adapter.iter_transactions(source=source))
        if not transactions:
            logger.warning("No transactions found — clustering aborted.")
            return []

        logger.info("Building graph from %d transactions", len(transactions))
        G = build_graph(transactions)
        pair_heuristics = self._find_pair_heuristics(G)
        results = self._build_results(G, pair_heuristics, min_cluster_size=min_cluster_size)
        logger.info("Clustering complete: %d clusters found", len(results))

        if persist:
            self._persist(results)

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

        pair_heuristics = self._find_pair_heuristics(G)
        results = self._build_results(G, pair_heuristics, min_cluster_size=1)
        if persist:
            self._persist(results)
        return results

    # ── persistence ──────────────────────────────────────────────────────────

    def _persist(self, results: List[ClusterResult]) -> None:
        """Save cluster results to MySQL (clusters + owner labels + evidence)."""
        persist_min_size = max(2, int(self.cfg.clustering_min_cluster_size or 2))
        persisted = [result for result in results if len(result.addresses) >= persist_min_size]
        self._save_to_mysql(persisted)

    def _save_to_mysql(self, results: List[ClusterResult]) -> None:
        from sqlalchemy import text

        from ..utils.connections import get_maria_engine
        from ..etl.load.mariadb_loader import create_tables_if_not_exist
        from .owner_registry import LABEL_STATUS_UNLABELED, relabel_clusters_in_connection

        persist_min_size = max(2, int(self.cfg.clustering_min_cluster_size or 2))
        heuristic_descriptions = {h.name: h.description for h in self.heuristics}

        create_tables_if_not_exist(self.cfg)
        engine = get_maria_engine(self.cfg)
        try:
            with engine.begin() as conn:
                cluster_ids = [r.cluster_id for r in results]
                existing_cluster_ids = set(
                    conn.execute(text("SELECT id FROM wallet_clusters")).scalars().all()
                )
                current_cluster_ids = set(cluster_ids)
                stale_cluster_ids = sorted(existing_cluster_ids - current_cluster_ids)

                if cluster_ids:
                    cluster_rows = []
                    for r in results:
                        total_balance = float(
                            r.indicators.get("internal_eth_volume", 0.0) or 0.0
                        )
                        cluster_rows.append({
                            "id": r.cluster_id,
                            "owner_id": None,
                            "cluster_size": len(r.addresses),
                            "total_balance": total_balance,
                            "risk_level": "normal",
                            "label_status": LABEL_STATUS_UNLABELED,
                            "matched_owner_address": None,
                        })

                    conn.execute(
                        text(
                            """
                            INSERT INTO wallet_clusters (
                                id,
                                owner_id,
                                cluster_size,
                                total_balance,
                                risk_level,
                                label_status,
                                matched_owner_address
                            )
                            VALUES (
                                :id,
                                :owner_id,
                                :cluster_size,
                                :total_balance,
                                :risk_level,
                                :label_status,
                                :matched_owner_address
                            )
                            ON DUPLICATE KEY UPDATE
                                owner_id = VALUES(owner_id),
                                cluster_size = VALUES(cluster_size),
                                total_balance = VALUES(total_balance),
                                risk_level = VALUES(risk_level),
                                label_status = VALUES(label_status),
                                matched_owner_address = VALUES(matched_owner_address)
                            """
                        ),
                        cluster_rows,
                    )

                if stale_cluster_ids:
                    for stale_batch in _chunked(stale_cluster_ids):
                        placeholders = ", ".join(
                            [f":sid{i}" for i in range(len(stale_batch))]
                        )
                        params = {
                            f"sid{i}": cluster_id
                            for i, cluster_id in enumerate(stale_batch)
                        }
                        conn.execute(
                            text(f"DELETE FROM wallet_clusters WHERE id IN ({placeholders})"),
                            params,
                        )

                # Reset address cluster mapping then re-assign
                conn.execute(text("UPDATE addresses SET cluster_id = NULL"))
                address_rows = [
                    {
                        "address": address,
                        "cluster_id": r.cluster_id,
                    }
                    for r in results
                    for address in r.addresses
                ]
                if address_rows:
                    conn.execute(
                        text(
                            """
                            UPDATE addresses
                            SET cluster_id = :cluster_id
                            WHERE address = :address
                            """
                        ),
                        address_rows,
                    )

                retained_cluster_ids = set(cluster_ids)
                if cluster_ids:
                    count_rows = conn.execute(
                        text(
                            """
                            SELECT cluster_id, COUNT(*) AS members
                            FROM addresses
                            WHERE cluster_id IS NOT NULL
                            GROUP BY cluster_id
                            """
                        )
                    ).mappings().all()
                    counts_by_cluster = {
                        row["cluster_id"]: int(row["members"] or 0)
                        for row in count_rows
                    }
                    retained_cluster_ids = {
                        cluster_id
                        for cluster_id in cluster_ids
                        if counts_by_cluster.get(cluster_id, 0) >= persist_min_size
                    }

                    if counts_by_cluster:
                        conn.execute(
                            text(
                                """
                                UPDATE wallet_clusters
                                SET cluster_size = :cluster_size
                                WHERE id = :cluster_id
                                """
                            ),
                            [
                                {
                                    "cluster_id": cluster_id,
                                    "cluster_size": counts_by_cluster.get(cluster_id, 0),
                                }
                                for cluster_id in cluster_ids
                            ],
                        )

                    undersized_ids = sorted(set(cluster_ids) - retained_cluster_ids)
                    if undersized_ids:
                        for undersized_batch in _chunked(undersized_ids):
                            placeholders = ", ".join(
                                [f":uid{i}" for i in range(len(undersized_batch))]
                            )
                            params = {
                                f"uid{i}": cluster_id
                                for i, cluster_id in enumerate(undersized_batch)
                            }
                            conn.execute(
                                text(f"DELETE FROM wallet_clusters WHERE id IN ({placeholders})"),
                                params,
                            )
                            conn.execute(
                                text(f"UPDATE addresses SET cluster_id = NULL WHERE cluster_id IN ({placeholders})"),
                                params,
                            )

                relabel_clusters_in_connection(
                    conn,
                    cluster_ids=sorted(retained_cluster_ids),
                )

                # Replace evidence
                retained_cluster_list = sorted(retained_cluster_ids)
                if retained_cluster_list:
                    for cluster_batch in _chunked(retained_cluster_list):
                        placeholders = ", ".join(
                            [f":cid{i}" for i in range(len(cluster_batch))]
                        )
                        params = {
                            f"cid{i}": cid
                            for i, cid in enumerate(cluster_batch)
                        }
                        conn.execute(
                            text(
                                f"DELETE FROM cluster_evidence "
                                f"WHERE cluster_id IN ({placeholders})"
                            ),
                            params,
                        )

                evidence_rows = []
                for r in results:
                    if r.cluster_id not in retained_cluster_ids:
                        continue
                    cluster_size = max(1, len(r.addresses))
                    for h_name, count in (r.heuristic_counts or {}).items():
                        description = heuristic_descriptions.get(h_name, h_name.replace("_", " "))
                        confidence = min(1.0, float(count) / float(cluster_size))
                        evidence_rows.append({
                            "cluster_id": r.cluster_id,
                            "heuristic_name": h_name,
                            "evidence_text": _normalize_text_for_storage(
                                f"{description} (signals: {count})"
                            ),
                            "confidence": confidence,
                        })

                if evidence_rows:
                    conn.execute(
                        text(
                            """
                            INSERT INTO cluster_evidence
                                (cluster_id, heuristic_name, evidence_text, confidence)
                            VALUES
                                (:cluster_id, :heuristic_name, :evidence_text, :confidence)
                            """
                        ),
                        evidence_rows,
                    )

            logger.info("Persisted %d clusters to MySQL", len(retained_cluster_ids))
        finally:
            engine.dispose()
