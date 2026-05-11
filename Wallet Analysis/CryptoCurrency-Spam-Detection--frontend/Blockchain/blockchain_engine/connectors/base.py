from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from blockchain_engine.models import NormalizedTransaction


class BaseConnector(ABC):
    chain: str

    @abstractmethod
    def get_balance(self, address: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_transactions(self, address: str, limit: int = 50) -> list[NormalizedTransaction]:
        raise NotImplementedError

    def get_code(self, address: str) -> str:
        return ""
