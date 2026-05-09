"""CLI entrypoint for the end-to-end extract -> transform -> load pipeline."""

import argparse
from .daily_pipeline import run_daily_pipeline


def main():
    """CLI entrypoint for the ETL pipeline."""
    parser = argparse.ArgumentParser(description="Run the ETL pipeline")
    parser.add_argument("--start-block", type=int, help="Ethereum block number to start extraction from")
    parser.add_argument("--batch", type=int, help="Number of blocks to extract in this run")
    parser.add_argument(
        "--skip-mongo-backup",
        action="store_true",
        help="Deprecated: processed transactions are no longer stored in MongoDB",
    )
    parser.add_argument("--skip-neo4j", action="store_true", help="Skip loading to Neo4j")
    parser.add_argument(
        "--strict-neo4j",
        action="store_true",
        help="Fail the pipeline if Neo4j loading fails instead of warning and continuing",
    )
    parser.add_argument(
        "--skip-clustering",
        action="store_true",
        help="Skip the address clustering stage",
    )
    parser.add_argument(
        "--skip-integration",
        action="store_true",
        help="Skip the integration-stage analytics",
    )
    parser.add_argument(
        "--skip-placement",
        action="store_true",
        help="Skip the placement analytics stage",
    )
    parser.add_argument(
        "--skip-layering",
        action="store_true",
        help="Skip the layering analytics stage",
    )

    args = parser.parse_args()
    run_daily_pipeline(
        start_block=args.start_block,
        batch=args.batch,
        skip_mongo_backup=args.skip_mongo_backup,
        skip_neo4j=args.skip_neo4j,
        strict_neo4j=args.strict_neo4j,
        run_clustering=not args.skip_clustering,
        run_placement=not args.skip_placement,
        run_layering=not args.skip_layering,
        run_integration=not args.skip_integration,
    )


if __name__ == "__main__":
    main()
