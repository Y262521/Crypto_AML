"""CLI entrypoint for the end-to-end extract -> transform -> load pipeline."""

import argparse
from .daily_pipeline import run_daily_pipeline


def main():
    """CLI entrypoint for the ETL pipeline."""
    parser = argparse.ArgumentParser(description="Run the AML ETL pipeline")
    parser.add_argument("--start-block", type=int, help="Ethereum block number to start extraction from")
    parser.add_argument("--batch", type=int, help="Number of blocks to extract in this run")
    parser.add_argument(
        "--skip-mongo-backup",
        action="store_true",
        help="Skip backing up processed transactions into MongoDB",
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

    args = parser.parse_args()
    run_daily_pipeline(
        start_block=args.start_block,
        batch=args.batch,
        skip_mongo_backup=args.skip_mongo_backup,
        skip_neo4j=args.skip_neo4j,
        strict_neo4j=args.strict_neo4j,
        run_clustering=not args.skip_clustering,
    )


if __name__ == "__main__":
    main()
