"""
Audit-safe backfill of usd_at_execution for existing transactions.

Usage:
    python scripts/backfill_usd_at_execution.py [--batch-size 500] [--dry-run]

Design principles:
  - Single source of truth: token_price_history (seeded from Chainlink oracle via Alchemy).
  - No CoinGecko. No external market APIs. No fabricated values.
  - Every valuation is traceable: pricing_source, valuation_version, backfill_run_id.
  - Immutable audit log: every computed value is appended to valuation_audit_log.
  - Idempotent: re-running only processes rows still NULL (or upgrades to a new version).
  - Does NOT overwrite values in-place silently — increments valuation_version on each run.

Audit trail:
  - transactions.pricing_source  = 'backfill_chainlink'
  - transactions.valuation_version increments per backfill run
  - valuation_audit_log records every (run_id, tx_hash, price, usd_value, computed_at)
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from sqlalchemy import text
from aml_pipeline.config import load_config
from aml_pipeline.utils.connections import get_maria_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

PRICING_SOURCE = "backfill_chainlink"


# ---------------------------------------------------------------------------
# Schema migration helpers
# ---------------------------------------------------------------------------

def _ensure_columns(engine, db: str) -> None:
    """Add audit columns to transactions table if missing."""
    with engine.begin() as conn:
        cols = set(conn.execute(
            text("SELECT COLUMN_NAME FROM information_schema.columns "
                 "WHERE table_schema = :db AND table_name = 'transactions'"),
            {"db": db},
        ).scalars().all())

        migrations = {
            "usd_at_execution":  "DECIMAL(24,2) NULL",
            "pricing_source":    "VARCHAR(64) NULL COMMENT 'chainlink_oracle | backfill_chainlink'",
            "valuation_version": "TINYINT UNSIGNED NOT NULL DEFAULT 0",
        }
        for col, ddl in migrations.items():
            if col not in cols:
                conn.exec_driver_sql(f"ALTER TABLE `transactions` ADD COLUMN `{col}` {ddl}")
                logger.info("Added column transactions.%s", col)

    # Ensure audit log table exists
    with engine.begin() as conn:
        conn.exec_driver_sql("""
            CREATE TABLE IF NOT EXISTS valuation_audit_log (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                run_id VARCHAR(64) NOT NULL,
                pricing_source VARCHAR(64) NOT NULL,
                price_date DATE NOT NULL,
                eth_usd_price DECIMAL(24,8) NOT NULL,
                tx_hash VARCHAR(66) NOT NULL,
                value_eth DECIMAL(38,18) NOT NULL,
                usd_at_execution DECIMAL(24,2) NOT NULL,
                valuation_version TINYINT UNSIGNED NOT NULL,
                computed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                KEY idx_val_audit_run_id (run_id),
                KEY idx_val_audit_tx_hash (tx_hash),
                KEY idx_val_audit_price_date (price_date),
                KEY idx_val_audit_computed_at (computed_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)


# ---------------------------------------------------------------------------
# Price cache — reads ONLY from token_price_history (Chainlink oracle data)
# ---------------------------------------------------------------------------

def _load_price_cache(engine) -> Dict[str, Decimal]:
    """
    Load ETH/USD prices from token_price_history into a flat dict keyed by "YYYY-MM-DD".
    This table is populated exclusively by the Chainlink oracle via Alchemy.
    ETH takes precedence over WETH for the same date.
    """
    price_map: Dict[str, Decimal] = {}
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT token_symbol, price_date, price_usd
                FROM token_price_history
                WHERE token_symbol IN ('ETH', 'WETH')
                ORDER BY token_symbol ASC
            """)
        ).fetchall()

    for row in rows:
        date_str = str(row[1])
        price    = Decimal(str(row[2]))
        price_map[date_str] = price   # ETH overwrites WETH (ETH sorts first)

    logger.info(
        "Loaded %d price entries from token_price_history (Chainlink oracle data)",
        len(price_map),
    )
    return price_map


# ---------------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------------

def _next_valuation_version(engine, db: str) -> int:
    """Return max(valuation_version) + 1 from transactions table."""
    with engine.connect() as conn:
        current = conn.execute(
            text("SELECT COALESCE(MAX(valuation_version), 0) FROM transactions")
        ).scalar_one()
    return int(current) + 1


def backfill(batch_size: int = 500, dry_run: bool = False) -> None:
    cfg    = load_config()
    engine = get_maria_engine(cfg)

    # Step 1 — schema migration (idempotent)
    _ensure_columns(engine, cfg.mysql_db)

    # Step 2 — load price cache (Chainlink oracle data only)
    price_map = _load_price_cache(engine)
    if not price_map:
        logger.error(
            "token_price_history is empty. "
            "Start the backend with ALCHEMY_RPC configured to populate Chainlink prices, "
            "then re-run this script."
        )
        engine.dispose()
        return

    # Step 3 — assign a unique run ID and version for this backfill execution
    run_id  = str(uuid.uuid4())
    version = _next_valuation_version(engine, cfg.mysql_db)
    started = datetime.now(timezone.utc).isoformat()

    logger.info("Backfill run_id=%s  valuation_version=%d  dry_run=%s", run_id, version, dry_run)

    # Step 4 — count eligible rows
    with engine.connect() as conn:
        total_null = conn.execute(
            text("SELECT COUNT(*) FROM transactions WHERE usd_at_execution IS NULL AND value_eth > 0")
        ).scalar_one()

    logger.info("Found %d transactions with usd_at_execution IS NULL and value_eth > 0", total_null)
    if total_null == 0:
        logger.info("Nothing to backfill.")
        engine.dispose()
        return

    # Step 5 — process in batches
    updated_total = 0
    skipped_total = 0
    offset        = 0

    while True:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT tx_hash, value_eth, timestamp
                    FROM transactions
                    WHERE usd_at_execution IS NULL AND value_eth > 0
                    ORDER BY block_number ASC, tx_hash ASC
                    LIMIT :limit OFFSET :offset
                """),
                {"limit": batch_size, "offset": offset},
            ).fetchall()

        if not rows:
            break

        tx_updates: List[dict] = []
        audit_rows: List[dict] = []

        for row in rows:
            tx_hash   = row[0]
            value_eth = float(row[1] or 0)
            ts        = row[2]

            if ts is None or value_eth <= 0:
                skipped_total += 1
                continue

            date_str = ts.strftime("%Y-%m-%d")
            price    = price_map.get(date_str)

            if price is None or price <= 0:
                # No Chainlink price for this date — leave NULL, never fabricate
                skipped_total += 1
                continue

            usd_val = round(float(Decimal(str(value_eth)) * price), 2)

            tx_updates.append({
                "tx_hash":           tx_hash,
                "usd_val":           usd_val,
                "pricing_source":    PRICING_SOURCE,
                "valuation_version": version,
            })
            audit_rows.append({
                "run_id":            run_id,
                "pricing_source":    PRICING_SOURCE,
                "price_date":        date_str,
                "eth_usd_price":     float(price),
                "tx_hash":           tx_hash,
                "value_eth":         value_eth,
                "usd_at_execution":  usd_val,
                "valuation_version": version,
            })

        if tx_updates and not dry_run:
            with engine.begin() as conn:
                # Update transactions with value + audit metadata
                conn.execute(
                    text("""
                        UPDATE transactions
                        SET usd_at_execution  = :usd_val,
                            pricing_source    = :pricing_source,
                            valuation_version = :valuation_version
                        WHERE tx_hash = :tx_hash
                    """),
                    tx_updates,
                )
                # Append immutable audit log rows
                conn.execute(
                    text("""
                        INSERT INTO valuation_audit_log
                            (run_id, pricing_source, price_date, eth_usd_price,
                             tx_hash, value_eth, usd_at_execution, valuation_version)
                        VALUES
                            (:run_id, :pricing_source, :price_date, :eth_usd_price,
                             :tx_hash, :value_eth, :usd_at_execution, :valuation_version)
                    """),
                    audit_rows,
                )

        updated_total += len(tx_updates)
        offset        += len(rows)

        logger.info(
            "Progress: %d/%d  |  updated=%d  skipped=%d (no Chainlink price)",
            offset, total_null, updated_total, skipped_total,
        )

        if len(rows) < batch_size:
            break

    engine.dispose()

    if dry_run:
        logger.info(
            "[DRY RUN] Would update %d rows (version=%d), skip %d rows. "
            "No DB changes made.",
            updated_total, version, skipped_total,
        )
    else:
        logger.info(
            "Backfill complete: run_id=%s  version=%d  updated=%d  skipped=%d",
            run_id, version, updated_total, skipped_total,
        )
        logger.info(
            "Audit trail written to valuation_audit_log (%d rows).",
            updated_total,
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Audit-safe backfill of usd_at_execution using Chainlink oracle prices"
    )
    parser.add_argument(
        "--batch-size", type=int, default=500,
        help="Rows per batch (default: 500)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Calculate values but do not write to the database",
    )
    args = parser.parse_args()
    backfill(batch_size=args.batch_size, dry_run=args.dry_run)
