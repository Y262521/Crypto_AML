"""Binance Smart Chain extractor placeholder (future implementation)."""

from .base import BaseExtractor


class BscExtractor(BaseExtractor):
    """Stub class reserved for a future BSC extractor."""
    def fetch_block(self, block_number: int) -> dict:
        """Fetch a BSC block (not implemented yet)."""
        raise NotImplementedError("BSC extractor not implemented yet")

    def get_latest_block(self) -> int:
        """Return the BSC chain tip (not implemented yet)."""
        raise NotImplementedError("BSC extractor not implemented yet")

    def save_to_db(self, data: dict) -> None:
        """Persist a raw BSC block (not implemented yet)."""
        raise NotImplementedError("BSC extractor not implemented yet")
