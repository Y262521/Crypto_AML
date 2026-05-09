"""Service label loading for layering analytics."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
import logging
from pathlib import Path

from sqlalchemy import text

from ...config import Config
from ...utils.connections import get_maria_engine

logger = logging.getLogger(__name__)

_DEFAULT_KEYWORDS = {
    "mixer": {
        "mixer",
        "mixing",
        "tornado",
        "privacy",
        "anonymity",
        "shielded",
        "stealth",
    },
    "bridge": {
        "bridge",
        "bridging",
        "portal",
        "router",
        "wormhole",
        "stargate",
        "across",
        "hop",
    },
    "exchange": {
        "exchange",
        "binance",
        "coinbase",
        "kraken",
        "okx",
        "bybit",
        "kucoin",
        "gate",
        "bitfinex",
        "huobi",
    },
}


@dataclass(frozen=True)
class ServiceRegistry:
    address_categories: dict[str, set[str]]
    method_categories: dict[str, set[str]]
    keywords: dict[str, set[str]]

    def categories_for_address(self, address: str | None) -> set[str]:
        if not address:
            return set()
        return set(self.address_categories.get(address.lower().strip(), set()))

    def categories_for_method(self, method_id: str | None) -> set[str]:
        if not method_id:
            return set()
        return set(self.method_categories.get(method_id.lower().strip(), set()))


def _merge_category_values(target: dict[str, set[str]], values: dict[str, list[str]] | None) -> None:
    if not isinstance(values, dict):
        return
    for category, raw_items in values.items():
        if not isinstance(raw_items, list):
            continue
        for item in raw_items:
            normalized = str(item or "").lower().strip()
            if normalized:
                target[normalized].add(category)


def _load_profile_file(path: Path) -> tuple[dict[str, set[str]], dict[str, set[str]], dict[str, set[str]]]:
    address_categories: dict[str, set[str]] = defaultdict(set)
    method_categories: dict[str, set[str]] = defaultdict(set)
    keywords = {name: set(values) for name, values in _DEFAULT_KEYWORDS.items()}

    if not path.exists():
        return address_categories, method_categories, keywords

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to parse layering service profile file %s: %s", path, exc)
        return address_categories, method_categories, keywords

    _merge_category_values(address_categories, payload.get("addresses"))
    _merge_category_values(method_categories, payload.get("methods"))

    raw_keywords = payload.get("keywords")
    if isinstance(raw_keywords, dict):
        for category, values in raw_keywords.items():
            if isinstance(values, list):
                keywords.setdefault(category, set()).update(
                    str(value or "").lower().strip()
                    for value in values
                    if str(value or "").strip()
                )

    return address_categories, method_categories, keywords


def _classify_text_labels(text_blob: str, keywords: dict[str, set[str]]) -> set[str]:
    normalized = text_blob.lower().strip()
    categories: set[str] = set()
    for category, category_keywords in keywords.items():
        if any(keyword in normalized for keyword in category_keywords):
            categories.add(category)
    return categories


def load_service_registry(cfg: Config) -> ServiceRegistry:
    address_categories: dict[str, set[str]] = defaultdict(set)
    method_categories: dict[str, set[str]] = defaultdict(set)
    keywords = {name: set(values) for name, values in _DEFAULT_KEYWORDS.items()}

    profile_path = str(cfg.layering_service_profile_path or "").strip()
    if profile_path:
        path = Path(profile_path)
        if not path.is_absolute():
            path = cfg.base_dir / path
        file_addresses, file_methods, file_keywords = _load_profile_file(path)
        for address, categories in file_addresses.items():
            address_categories[address].update(categories)
        for method_id, categories in file_methods.items():
            method_categories[method_id].update(categories)
        for category, values in file_keywords.items():
            keywords.setdefault(category, set()).update(values)

    engine = None
    try:
        engine = get_maria_engine(cfg)
        query = text(
            """
            SELECT
                ola.address,
                ol.full_name,
                ol.entity_type,
                ol.list_category,
                ol.specifics,
                ol.source_reference,
                ol.notes
            FROM owner_list_addresses ola
            JOIN owner_list ol
              ON ol.id = ola.owner_list_id
            """
        )
        with engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        for row in rows:
            address = str(row.get("address") or "").lower().strip()
            if not address:
                continue
            blob = " ".join(
                str(row.get(field) or "")
                for field in (
                    "full_name",
                    "entity_type",
                    "list_category",
                    "specifics",
                    "source_reference",
                    "notes",
                )
            )
            categories = _classify_text_labels(blob, keywords)
            for category in categories:
                address_categories[address].add(category)
    except Exception as exc:
        logger.info("Layering service registry could not load owner labels: %s", exc)
    finally:
        if engine is not None:
            engine.dispose()

    return ServiceRegistry(
        address_categories={key: set(value) for key, value in address_categories.items()},
        method_categories={key: set(value) for key, value in method_categories.items()},
        keywords=keywords,
    )
