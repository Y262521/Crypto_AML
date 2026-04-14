"""
CLI entry point for the clustering module.

Usage:
    # From project directory with venv active:
    python -m aml_pipeline.clustering.run_clustering
    python -m aml_pipeline.clustering.run_clustering --source csv
    python -m aml_pipeline.clustering.run_clustering --persist
    python -m aml_pipeline.clustering.run_clustering --min-size 3 --top 20
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict

from ..config import load_config
from ..logging_config import setup_logging
from .engine import ClusteringEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Run wallet ownership clustering")
    parser.add_argument(
        "--source",
        choices=["auto", "mariadb", "processed", "raw", "csv"],
        default="auto",
        help="Transaction data source (default: auto)",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Save cluster results to MySQL (clusters + owners + evidence)",
    )
    parser.add_argument(
        "--min-size",
        type=int,
        default=None,
        help="Minimum cluster size to include in output (default: configured cluster minimum)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=50,
        help="Print only the top N clusters by size (default: 50)",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args()

    cfg = load_config()
    setup_logging(cfg.log_level)
    logger = logging.getLogger(__name__)

    engine = ClusteringEngine(cfg=cfg)
    results = engine.run(
        source=args.source,
        persist=args.persist,
        min_cluster_size=cfg.clustering_min_cluster_size if args.min_size is None else args.min_size,
    )

    if not results:
        print("No clusters found.")
        sys.exit(0)

    top = results[: args.top]

    if args.output == "json":
        print(json.dumps([asdict(r) for r in top], indent=2, default=str))
        return

    # ── text output ──────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  Wallet Clustering Results  —  {len(results)} clusters found")
    print(f"{'='*70}\n")

    for i, r in enumerate(top, 1):
        print(f"[{i:>3}] Cluster {r.cluster_id}")
        print(f"       Heuristics : {', '.join(r.heuristics_fired) or 'none'}")
        print(f"       Addresses  : {len(r.addresses)}")
        for addr in r.addresses[:5]:
            print(f"                    {addr}")
        if len(r.addresses) > 5:
            print(f"                    ... and {len(r.addresses) - 5} more")
        print(f"       Indicators : vol={r.indicators.get('total_eth_volume')} ETH  "
              f"txns={r.indicators.get('total_tx_count')}  "
              f"internal={r.indicators.get('internal_tx_count')}")
        print()

    print(f"Showing top {len(top)} of {len(results)} clusters.")
    if args.persist:
        print("Results persisted to MySQL.")


if __name__ == "__main__":
    main()
