"""Abstract base extractor interface."""

from abc import ABC, abstractmethod

from ...config import Config, load_config
from .utils import to_jsonable


class BaseExtractor(ABC):
    """Abstract base class for chain-specific extractors."""
    def __init__(self, cfg: Config | None = None):
        """Initialize the extractor with a Config instance."""
        self.cfg = cfg or load_config()

    @abstractmethod
    def fetch_block(self, block_number: int) -> dict:
        """Fetch a single block and return a raw document."""
        raise NotImplementedError

    @abstractmethod
    def get_latest_block(self) -> int:
        """Return the latest chain head block number."""
        raise NotImplementedError

    @abstractmethod
    def save_to_db(self, data: dict):
        """Persist extracted data to storage."""
        raise NotImplementedError

    def save_to_local_backup(self, data: dict, block_number: int) -> str:
        """Write a raw block JSON backup to disk."""
        self.cfg.raw_dir.mkdir(parents=True, exist_ok=True)
        path = self.cfg.raw_dir / f"block_{block_number}.json"
        with path.open("w", encoding="utf-8") as handle:
            import json

            json.dump(to_jsonable(data), handle, ensure_ascii=True, indent=2)
        return str(path)
