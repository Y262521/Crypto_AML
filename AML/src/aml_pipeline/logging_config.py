"""Logging setup for the pipeline."""

import logging


def setup_logging(level: str) -> None:
    """Configure root logging with a consistent format."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
