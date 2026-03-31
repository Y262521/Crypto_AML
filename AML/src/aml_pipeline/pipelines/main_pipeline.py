"""Main pipeline entrypoint for the default ETL flow."""

from .daily_pipeline import run_daily_pipeline


def main():
    """Run the default extract -> transform -> load pipeline."""
    run_daily_pipeline()


if __name__ == "__main__":
    main()
