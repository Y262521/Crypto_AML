"""Bitcoin extractor placeholder (future implementation)."""

from .base import BaseExtractor


class BitcoinExtractor(BaseExtractor):
    """Stub class reserved for a future Bitcoin extractor."""
    def fetch_block(self, block_number: int) -> dict:
        """Fetch a Bitcoin block (not implemented yet)."""
        raise NotImplementedError("Bitcoin extractor not implemented yet")

    def get_latest_block(self) -> int:
        """Return the Bitcoin chain tip (not implemented yet)."""
        raise NotImplementedError("Bitcoin extractor not implemented yet")

    def save_to_db(self, data: dict) -> None:
        """Persist a raw Bitcoin block (not implemented yet)."""
        raise NotImplementedError("Bitcoin extractor not implemented yet")
