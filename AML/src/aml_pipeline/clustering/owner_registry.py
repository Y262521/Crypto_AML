"""Owner registry and cluster labeling helpers."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
import hashlib
import logging
import string
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from ..config import Config, load_config
from ..utils.connections import get_maria_engine

logger = logging.getLogger(__name__)

LABEL_STATUS_MATCHED = "matched"
LABEL_STATUS_UNLABELED = "unlabeled"
LABEL_STATUS_CONFLICT = "conflict"
DEFAULT_NETWORK = "ethereum"

_HEX_CHARS = set(string.hexdigits)

_OWNER_LIST_SEED_PROFILES: list[dict[str, str]] = [
    {
        "full_name": "Dawit Alemu",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "Apartment 4B",
        "street_address": "Bole Road",
        "locality": "Bole",
        "city": "Addis Ababa",
        "administrative_area": "Addis Ababa",
        "postal_code": "1000",
        "country": "Ethiopia",
        "source_reference": "Owner Registry Intake",
        "notes": "Initial owner-list seed profile linked to an observed cluster address.",
    },
    {
        "full_name": "Hana Bekele",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "House 12",
        "street_address": "Cape Verde Street",
        "locality": "Kirkos",
        "city": "Addis Ababa",
        "administrative_area": "Addis Ababa",
        "postal_code": "1010",
        "country": "Ethiopia",
        "source_reference": "Owner Registry Intake",
        "notes": "Initial owner-list seed profile linked to an observed cluster address.",
    },
    {
        "full_name": "Samuel Tadesse",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "Suite 8",
        "street_address": "Menelik II Avenue",
        "locality": "Arada",
        "city": "Addis Ababa",
        "administrative_area": "Addis Ababa",
        "postal_code": "1005",
        "country": "Ethiopia",
        "source_reference": "Owner Registry Intake",
        "notes": "Initial owner-list seed profile linked to an observed cluster address.",
    },
    {
        "full_name": "Meron Tesfaye",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "Compound 17",
        "street_address": "Ayer Tena Road",
        "locality": "Kolfe Keranio",
        "city": "Addis Ababa",
        "administrative_area": "Addis Ababa",
        "postal_code": "1020",
        "country": "Ethiopia",
        "source_reference": "Owner Registry Intake",
        "notes": "Initial owner-list seed profile linked to an observed cluster address.",
    },
    {
        "full_name": "Abel Getachew",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "Block C",
        "street_address": "Gofa Camp Road",
        "locality": "Nifas Silk-Lafto",
        "city": "Addis Ababa",
        "administrative_area": "Addis Ababa",
        "postal_code": "1050",
        "country": "Ethiopia",
        "source_reference": "Owner Registry Intake",
        "notes": "Initial owner-list seed profile linked to an observed cluster address.",
    },
    {
        "full_name": "Bethlehem Assefa",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "Unit 6",
        "street_address": "Haile Gebre Selassie Avenue",
        "locality": "Belay Zeleke",
        "city": "Bahir Dar",
        "administrative_area": "Amhara",
        "postal_code": "6000",
        "country": "Ethiopia",
        "source_reference": "Owner Registry Intake",
        "notes": "Initial owner-list seed profile linked to an observed cluster address.",
    },
    {
        "full_name": "Natnael Girma",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "House 9",
        "street_address": "Ras Abebe Aregay Street",
        "locality": "Tabor",
        "city": "Hawassa",
        "administrative_area": "Sidama",
        "postal_code": "8000",
        "country": "Ethiopia",
        "source_reference": "Owner Registry Intake",
        "notes": "Initial owner-list seed profile linked to an observed cluster address.",
    },
    {
        "full_name": "Ruth Kebede",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "Plot 14",
        "street_address": "Adama Ring Road",
        "locality": "Bole",
        "city": "Adama",
        "administrative_area": "Oromia",
        "postal_code": "1888",
        "country": "Ethiopia",
        "source_reference": "Owner Registry Intake",
        "notes": "Initial owner-list seed profile linked to an observed cluster address.",
    },
    {
        "full_name": "Yonas Fikru",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "Office 2",
        "street_address": "Sabian Road",
        "locality": "Kezira",
        "city": "Dire Dawa",
        "administrative_area": "Dire Dawa",
        "postal_code": "3000",
        "country": "Ethiopia",
        "source_reference": "Owner Registry Intake",
        "notes": "Initial owner-list seed profile linked to an observed cluster address.",
    },
    {
        "full_name": "Tigist Lemma",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "Residence 5",
        "street_address": "Kebele 04",
        "locality": "Ayder",
        "city": "Mekelle",
        "administrative_area": "Tigray",
        "postal_code": "7000",
        "country": "Ethiopia",
        "source_reference": "Owner Registry Intake",
        "notes": "Initial owner-list seed profile linked to an observed cluster address.",
    },
    {
        "full_name": "Kalkidan Demissie",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "Flat 10",
        "street_address": "Kebele 03",
        "locality": "Hermata",
        "city": "Jimma",
        "administrative_area": "Oromia",
        "postal_code": "3788",
        "country": "Ethiopia",
        "source_reference": "Owner Registry Intake",
        "notes": "Initial owner-list seed profile linked to an observed cluster address.",
    },
    {
        "full_name": "Biruk Hailu",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "Warehouse 1",
        "street_address": "Bure Road",
        "locality": "Shimbit",
        "city": "Bahir Dar",
        "administrative_area": "Amhara",
        "postal_code": "6000",
        "country": "Ethiopia",
        "source_reference": "Owner Registry Intake",
        "notes": "Initial owner-list seed profile linked to an observed cluster address.",
    },
    {
        "full_name": "Eden Sisay",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "Apartment 18",
        "street_address": "Megenagna Ring Road",
        "locality": "Yeka",
        "city": "Addis Ababa",
        "administrative_area": "Addis Ababa",
        "postal_code": "1000",
        "country": "Ethiopia",
        "source_reference": "Owner Registry Intake",
        "notes": "Initial owner-list seed profile linked to an observed cluster address.",
    },
    {
        "full_name": "Henok Desta",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "Compound 22",
        "street_address": "Lideta Debre Zeit Road",
        "locality": "Lideta",
        "city": "Addis Ababa",
        "administrative_area": "Addis Ababa",
        "postal_code": "1030",
        "country": "Ethiopia",
        "source_reference": "Owner Registry Intake",
        "notes": "Initial owner-list seed profile linked to an observed cluster address.",
    },
    {
        "full_name": "Liya Abebe",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "Office 11",
        "street_address": "Stadium Road",
        "locality": "Arada",
        "city": "Addis Ababa",
        "administrative_area": "Addis Ababa",
        "postal_code": "1004",
        "country": "Ethiopia",
        "source_reference": "Owner Registry Intake",
        "notes": "Initial owner-list seed profile linked to an observed cluster address.",
    },
    {
        "full_name": "Mekdes Wondimu",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "Suite 3",
        "street_address": "Kilo Avenue",
        "locality": "Kirkos",
        "city": "Addis Ababa",
        "administrative_area": "Addis Ababa",
        "postal_code": "1012",
        "country": "Ethiopia",
        "source_reference": "Owner Registry Intake",
        "notes": "Initial owner-list seed profile linked to an observed cluster address.",
    },
    {
        "full_name": "Surafel Mengistu",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "House 7",
        "street_address": "Gende Kore Road",
        "locality": "Legetafo",
        "city": "Bishoftu",
        "administrative_area": "Oromia",
        "postal_code": "2001",
        "country": "Ethiopia",
        "source_reference": "Owner Registry Intake",
        "notes": "Initial owner-list seed profile linked to an observed cluster address.",
    },
    {
        "full_name": "Blue Nile Trading PLC",
        "entity_type": "organization",
        "list_category": "watchlist",
        "specifics": "Floor 5",
        "street_address": "Africa Avenue",
        "locality": "Bole",
        "city": "Addis Ababa",
        "administrative_area": "Addis Ababa",
        "postal_code": "1000",
        "country": "Ethiopia",
        "source_reference": "Commercial Registry Review",
        "notes": "Entity record seeded for initial registry coverage.",
    },
    {
        "full_name": "Abay Logistics Share Company",
        "entity_type": "organization",
        "list_category": "watchlist",
        "specifics": "Logistics Yard 2",
        "street_address": "Industrial Park Road",
        "locality": "Kality",
        "city": "Addis Ababa",
        "administrative_area": "Addis Ababa",
        "postal_code": "1040",
        "country": "Ethiopia",
        "source_reference": "Commercial Registry Review",
        "notes": "Entity record seeded for initial registry coverage.",
    },
    {
        "full_name": "Victor Mwangi",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "Suite 14",
        "street_address": "Ngong Road",
        "locality": "Kilimani",
        "city": "Nairobi",
        "administrative_area": "Nairobi County",
        "postal_code": "00100",
        "country": "Kenya",
        "source_reference": "Cross-Border Registry Review",
        "notes": "Foreign owner profile included in the seed set.",
    },
    {
        "full_name": "Oliver Grant",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "Flat 7",
        "street_address": "Canary Wharf Road",
        "locality": "Tower Hamlets",
        "city": "London",
        "administrative_area": "England",
        "postal_code": "E14 5AB",
        "country": "United Kingdom",
        "source_reference": "Cross-Border Registry Review",
        "notes": "Foreign owner profile included in the seed set.",
    },
    {
        "full_name": "Fatima Al Mansoori",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "Office 22",
        "street_address": "Sheikh Zayed Road",
        "locality": "Trade Centre",
        "city": "Dubai",
        "administrative_area": "Dubai",
        "postal_code": "00000",
        "country": "United Arab Emirates",
        "source_reference": "Cross-Border Registry Review",
        "notes": "Foreign owner profile included in the seed set.",
    },
    {
        "full_name": "Nora Schneider",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "Haus 5",
        "street_address": "Friedrichstrasse",
        "locality": "Mitte",
        "city": "Berlin",
        "administrative_area": "Berlin",
        "postal_code": "10117",
        "country": "Germany",
        "source_reference": "Cross-Border Registry Review",
        "notes": "Foreign owner profile included in the seed set.",
    },
    {
        "full_name": "Linh Tran",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "Unit 18",
        "street_address": "Raffles Place",
        "locality": "Downtown Core",
        "city": "Singapore",
        "administrative_area": "Central Singapore",
        "postal_code": "048616",
        "country": "Singapore",
        "source_reference": "Cross-Border Registry Review",
        "notes": "Foreign owner profile included in the seed set.",
    },
    {
        "full_name": "Daniel Costa",
        "entity_type": "individual",
        "list_category": "watchlist",
        "specifics": "Apt 3D",
        "street_address": "Avenida da Liberdade",
        "locality": "Santo Antonio",
        "city": "Lisbon",
        "administrative_area": "Lisbon",
        "postal_code": "1250-144",
        "country": "Portugal",
        "source_reference": "Cross-Border Registry Review",
        "notes": "Foreign owner profile included in the seed set.",
    },
]


def normalize_owner_addresses(addresses: Iterable[str]) -> list[str]:
    """Normalize and deduplicate EVM-style addresses."""
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in addresses:
        address = (raw or "").strip().lower()
        if not address:
            continue
        if len(address) != 42 or not address.startswith("0x"):
            raise ValueError(f"Invalid address format: {raw}")
        if any(char not in _HEX_CHARS for char in address[2:]):
            raise ValueError(f"Invalid address format: {raw}")
        if address in seen:
            continue
        seen.add(address)
        normalized.append(address)
    return normalized


def _select_cluster_label(match_rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not match_rows:
        return {
            "owner_id": None,
            "label_status": LABEL_STATUS_UNLABELED,
            "matched_owner_address": None,
            "match_count": 0,
        }

    candidates: dict[int, dict[str, Any]] = {}
    for row in match_rows:
        owner_id = int(row["owner_list_id"])
        candidate = candidates.setdefault(
            owner_id,
            {
                "owner_id": owner_id,
                "match_count": 0,
                "has_primary": False,
                "primary_address": None,
                "addresses": [],
            },
        )
        candidate["match_count"] += 1
        address = row.get("address")
        if address:
            candidate["addresses"].append(address)
        if bool(row.get("is_primary")):
            candidate["has_primary"] = True
            if not candidate["primary_address"]:
                candidate["primary_address"] = address

    ranked = sorted(
        candidates.values(),
        key=lambda item: (-item["match_count"], -int(item["has_primary"]), item["owner_id"]),
    )
    top = ranked[0]
    if len(ranked) > 1:
        second = ranked[1]
        if (
            top["match_count"] == second["match_count"]
            and top["has_primary"] == second["has_primary"]
        ):
            return {
                "owner_id": None,
                "label_status": LABEL_STATUS_CONFLICT,
                "matched_owner_address": None,
                "match_count": top["match_count"],
            }

    matched_address = top["primary_address"] or min(top["addresses"])
    return {
        "owner_id": top["owner_id"],
        "label_status": LABEL_STATUS_MATCHED,
        "matched_owner_address": matched_address,
        "match_count": top["match_count"],
    }


def _representative_address(cluster_id: str, addresses: Sequence[str]) -> str:
    digest = hashlib.sha1(cluster_id.encode("utf-8")).hexdigest()
    index = int(digest[:8], 16) % len(addresses)
    return addresses[index]


def _chunked(items: Sequence[str], size: int = 1000):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _cluster_ids_for_addresses(
    conn: Connection,
    addresses: Sequence[str],
) -> list[str]:
    if not addresses:
        return []

    cluster_ids: list[str] = []
    for batch in _chunked(addresses):
        placeholders = ", ".join(f":addr{i}" for i in range(len(batch)))
        params = {f"addr{i}": address for i, address in enumerate(batch)}
        rows = conn.execute(
            text(
                f"""
                SELECT DISTINCT cluster_id
                FROM addresses
                WHERE cluster_id IS NOT NULL
                  AND LOWER(address) IN ({placeholders})
                ORDER BY cluster_id
                """
            ),
            params,
        ).scalars().all()
        cluster_ids.extend(rows)

    return sorted(set(cluster_ids))


def resolve_cluster_labels(
    conn: Connection,
    cluster_ids: Sequence[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Return owner matches for wallet clusters based on registry addresses."""
    if cluster_ids is None:
        target_cluster_ids = conn.execute(
            text("SELECT id FROM wallet_clusters ORDER BY id")
        ).scalars().all()
    else:
        target_cluster_ids = sorted(set(cluster_ids))

    if not target_cluster_ids:
        return {}

    rows_by_cluster: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for batch in _chunked(target_cluster_ids):
        placeholders = ", ".join(f":cid{i}" for i in range(len(batch)))
        params = {f"cid{i}": cluster_id for i, cluster_id in enumerate(batch)}
        rows = conn.execute(
            text(
                f"""
                SELECT a.cluster_id,
                       ola.owner_list_id,
                       ola.address,
                       ola.is_primary
                FROM addresses a
                JOIN owner_list_addresses ola
                  ON LOWER(ola.address) = LOWER(a.address)
                WHERE a.cluster_id IN ({placeholders})
                """
            ),
            params,
        ).mappings().all()
        for row in rows:
            rows_by_cluster[row["cluster_id"]].append(dict(row))

    return {
        cluster_id: _select_cluster_label(rows_by_cluster.get(cluster_id, []))
        for cluster_id in target_cluster_ids
    }


def relabel_clusters_in_connection(
    conn: Connection,
    cluster_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Apply owner labels to wallet_clusters from the owner registry."""
    labels = resolve_cluster_labels(conn, cluster_ids=cluster_ids)
    if not labels:
        return {
            "clusters_relabelled": 0,
            "matched_clusters": 0,
            "unlabeled_clusters": 0,
            "conflict_clusters": 0,
            "cluster_ids": [],
        }

    update_rows = [
        {
            "cluster_id": cluster_id,
            "owner_id": label["owner_id"],
            "label_status": label["label_status"],
            "matched_owner_address": label["matched_owner_address"],
        }
        for cluster_id, label in labels.items()
    ]
    conn.execute(
        text(
            """
            UPDATE wallet_clusters
            SET owner_id = :owner_id,
                label_status = :label_status,
                matched_owner_address = :matched_owner_address,
                last_labeled_at = UTC_TIMESTAMP()
            WHERE id = :cluster_id
            """
        ),
        update_rows,
    )

    status_counts = defaultdict(int)
    for label in labels.values():
        status_counts[label["label_status"]] += 1

    return {
        "clusters_relabelled": len(update_rows),
        "matched_clusters": int(status_counts[LABEL_STATUS_MATCHED]),
        "unlabeled_clusters": int(status_counts[LABEL_STATUS_UNLABELED]),
        "conflict_clusters": int(status_counts[LABEL_STATUS_CONFLICT]),
        "cluster_ids": sorted(labels),
    }


def relabel_clusters(
    cfg: Config | None = None,
    cluster_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    cfg = cfg or load_config()
    from ..etl.load.mariadb_loader import create_tables_if_not_exist

    create_tables_if_not_exist(cfg)
    engine = get_maria_engine(cfg)
    try:
        with engine.begin() as conn:
            return relabel_clusters_in_connection(conn, cluster_ids=cluster_ids)
    finally:
        engine.dispose()


def create_owner_list_entry(
    owner_data: dict[str, Any],
    *,
    cfg: Config | None = None,
) -> dict[str, Any]:
    """Insert an owner-list row and relabel any matching clusters."""
    cfg = cfg or load_config()
    from ..etl.load.mariadb_loader import create_tables_if_not_exist

    create_tables_if_not_exist(cfg)
    engine = get_maria_engine(cfg)
    try:
        with engine.begin() as conn:
            addresses = normalize_owner_addresses(owner_data.pop("known_addresses"))
            network = owner_data.pop("blockchain_network", DEFAULT_NETWORK)
            existing_rows = []
            if addresses:
                placeholders = ", ".join(f":addr{i}" for i in range(len(addresses)))
                params = {f"addr{i}": address for i, address in enumerate(addresses)}
                existing_rows = conn.execute(
                    text(
                        f"""
                        SELECT address
                        FROM owner_list_addresses
                        WHERE address IN ({placeholders})
                        """
                    ),
                    params,
                ).scalars().all()
            if existing_rows:
                existing = ", ".join(sorted(existing_rows))
                raise ValueError(f"Address already exists in owner list: {existing}")

            result = conn.execute(
                text(
                    """
                    INSERT INTO owner_list (
                        full_name,
                        entity_type,
                        list_category,
                        specifics,
                        street_address,
                        locality,
                        city,
                        administrative_area,
                        postal_code,
                        country,
                        source_reference,
                        notes
                    )
                    VALUES (
                        :full_name,
                        :entity_type,
                        :list_category,
                        :specifics,
                        :street_address,
                        :locality,
                        :city,
                        :administrative_area,
                        :postal_code,
                        :country,
                        :source_reference,
                        :notes
                    )
                    """
                ),
                owner_data,
            )
            owner_id = int(result.lastrowid)
            conn.execute(
                text(
                    """
                    INSERT INTO owner_list_addresses (
                        owner_list_id,
                        blockchain_network,
                        address,
                        is_primary
                    )
                    VALUES (
                        :owner_list_id,
                        :blockchain_network,
                        :address,
                        :is_primary
                    )
                    """
                ),
                [
                    {
                        "owner_list_id": owner_id,
                        "blockchain_network": network,
                        "address": address,
                        "is_primary": 1 if index == 0 else 0,
                    }
                    for index, address in enumerate(addresses)
                ],
            )

            cluster_ids = _cluster_ids_for_addresses(conn, addresses)
            relabel_summary = relabel_clusters_in_connection(conn, cluster_ids=cluster_ids)

            return {
                "owner_id": owner_id,
                "addresses_added": len(addresses),
                "cluster_ids": cluster_ids,
                "relabel_summary": relabel_summary,
            }
    finally:
        engine.dispose()


def seed_owner_registry(
    cfg: Config | None = None,
    *,
    replace_existing: bool = False,
) -> dict[str, Any]:
    """Seed the owner list with realistic profiles for current clusters."""
    cfg = cfg or load_config()
    from ..etl.load.mariadb_loader import create_tables_if_not_exist

    create_tables_if_not_exist(cfg)
    engine = get_maria_engine(cfg)
    try:
        with engine.begin() as conn:
            existing_count = int(
                conn.execute(text("SELECT COUNT(*) FROM owner_list")).scalar_one()
            )
            if existing_count and not replace_existing:
                return {
                    "seeded": 0,
                    "skipped": True,
                    "owner_list_count": existing_count,
                    "reason": "owner_list already contains data",
                }

            if replace_existing:
                conn.execute(
                    text(
                        """
                        UPDATE wallet_clusters
                        SET owner_id = NULL,
                            label_status = :label_status,
                            matched_owner_address = NULL,
                            last_labeled_at = NULL
                        """
                    ),
                    {"label_status": LABEL_STATUS_UNLABELED},
                )
                conn.execute(text("DELETE FROM owner_list_addresses"))
                conn.execute(text("DELETE FROM owner_list"))

            rows = conn.execute(
                text(
                    """
                    SELECT c.id AS cluster_id,
                           a.address
                    FROM wallet_clusters c
                    JOIN addresses a ON a.cluster_id = c.id
                    ORDER BY c.cluster_size DESC, c.id ASC, a.address ASC
                    """
                )
            ).mappings().all()

            clusters: dict[str, list[str]] = defaultdict(list)
            for row in rows:
                clusters[row["cluster_id"]].append(row["address"])

            if not clusters:
                return {
                    "seeded": 0,
                    "skipped": True,
                    "owner_list_count": 0,
                    "reason": "no clusters available",
                }

            for index, (cluster_id, addresses) in enumerate(clusters.items()):
                profile = dict(_OWNER_LIST_SEED_PROFILES[index % len(_OWNER_LIST_SEED_PROFILES)])
                result = conn.execute(
                    text(
                        """
                        INSERT INTO owner_list (
                            full_name,
                            entity_type,
                            list_category,
                            specifics,
                            street_address,
                            locality,
                            city,
                            administrative_area,
                            postal_code,
                            country,
                            source_reference,
                            notes
                        )
                        VALUES (
                            :full_name,
                            :entity_type,
                            :list_category,
                            :specifics,
                            :street_address,
                            :locality,
                            :city,
                            :administrative_area,
                            :postal_code,
                            :country,
                            :source_reference,
                            :notes
                        )
                        """
                    ),
                    profile,
                )
                owner_id = int(result.lastrowid)
                conn.execute(
                    text(
                        """
                        INSERT INTO owner_list_addresses (
                            owner_list_id,
                            blockchain_network,
                            address,
                            is_primary
                        )
                        VALUES (
                            :owner_list_id,
                            :blockchain_network,
                            :address,
                            1
                        )
                        """
                    ),
                    {
                        "owner_list_id": owner_id,
                        "blockchain_network": DEFAULT_NETWORK,
                        "address": _representative_address(cluster_id, addresses),
                    },
                )

            relabel_summary = relabel_clusters_in_connection(
                conn,
                cluster_ids=sorted(clusters),
            )
            logger.info(
                "Seeded %d owner-list profiles and relabelled %d clusters",
                len(clusters),
                relabel_summary["clusters_relabelled"],
            )
            return {
                "seeded": len(clusters),
                "skipped": False,
                "owner_list_count": len(clusters),
                "relabel_summary": relabel_summary,
            }
    finally:
        engine.dispose()

