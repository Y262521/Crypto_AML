"""Tron extractor placeholder (future implementation)."""

from .base import BaseExtractor


class TronExtractor(BaseExtractor):
    """Stub class reserved for a future Tron extractor."""
    def fetch_block(self, block_number: int) -> dict:
        """Fetch a Tron block (not implemented yet)."""
        raise NotImplementedError("Tron extractor not implemented yet")

    def get_latest_block(self) -> int:
        """Return the Tron chain tip (not implemented yet)."""
        raise NotImplementedError("Tron extractor not implemented yet")

    def save_to_db(self, data: dict) -> None:
        """Persist a raw Tron block (not implemented yet)."""
        raise NotImplementedError("Tron extractor not implemented yet")
