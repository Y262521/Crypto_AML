"""MariaDB (MySQL) access helpers for clean data and alerts."""

import logging
import math
from typing import Iterable, List

import mysql.connector
from mysql.connector import errorcode

from ..config import Config

logger = logging.getLogger(__name__)


TRANSACTIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS transactions_clean (
    tx_id VARCHAR(64) PRIMARY KEY,
    event_time DATETIME NOT NULL,
    sender_id VARCHAR(64) NOT NULL,
    receiver_id VARCHAR(64) NOT NULL,
    amount DECIMAL(18,8) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    amount_usd DECIMAL(18,2) NOT NULL,
    btc_amount DECIMAL(18,8) NOT NULL,
    is_crypto TINYINT(1) NOT NULL,
    raw_source VARCHAR(32),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
"""

ALERTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS alerts (
    alert_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    tx_id VARCHAR(64) NOT NULL,
    alert_time DATETIME NOT NULL,
    risk_score DECIMAL(5,2) NOT NULL,
    reasons TEXT NOT NULL,
    cluster_label INT NOT NULL,
    amount_usd DECIMAL(18,2) NOT NULL,
    btc_amount DECIMAL(18,8) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX (tx_id),
    INDEX (alert_time)
);
"""

STATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pipeline_state (
    state_key VARCHAR(64) PRIMARY KEY,
    state_value VARCHAR(255)
);
"""

ETH_TRANSACTIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS eth_transactions (
    tx_hash VARCHAR(66) PRIMARY KEY,
    block_number BIGINT NOT NULL,
    timestamp DATETIME NULL,
    from_address VARCHAR(64) NULL,
    to_address VARCHAR(64) NULL,
    value_eth DECIMAL(38,18) NOT NULL,
    gas_used BIGINT NULL,
    status TINYINT NULL,
    is_contract_call TINYINT(1) NOT NULL,
    input_data TEXT,
    risk_flag_high_value TINYINT(1) NOT NULL,
    risk_flag_contract TINYINT(1) NOT NULL,
    is_suspicious_basic TINYINT(1) NOT NULL,
    tx_type VARCHAR(32) NOT NULL,
    fetched_at DATETIME NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
"""

GRAPH_EDGES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS graph_edges (
    tx_hash VARCHAR(66) PRIMARY KEY,
    from_address VARCHAR(64) NULL,
    to_address VARCHAR(64) NULL,
    value_eth DECIMAL(38,18) NOT NULL,
    block_number BIGINT NOT NULL,
    timestamp DATETIME NULL
);
"""


INSERT_TRANSACTION_SQL = """
INSERT INTO transactions_clean (
    tx_id, event_time, sender_id, receiver_id, amount, currency,
    amount_usd, btc_amount, is_crypto, raw_source
) VALUES (
    %(tx_id)s, %(event_time)s, %(sender_id)s, %(receiver_id)s, %(amount)s, %(currency)s,
    %(amount_usd)s, %(btc_amount)s, %(is_crypto)s, %(raw_source)s
)
ON DUPLICATE KEY UPDATE
    event_time=VALUES(event_time),
    sender_id=VALUES(sender_id),
    receiver_id=VALUES(receiver_id),
    amount=VALUES(amount),
    currency=VALUES(currency),
    amount_usd=VALUES(amount_usd),
    btc_amount=VALUES(btc_amount),
    is_crypto=VALUES(is_crypto),
    raw_source=VALUES(raw_source),
    updated_at=CURRENT_TIMESTAMP;
"""

INSERT_ALERT_SQL = """
INSERT INTO alerts (
    tx_id, alert_time, risk_score, reasons, cluster_label, amount_usd, btc_amount
) VALUES (
    %(tx_id)s, %(alert_time)s, %(risk_score)s, %(reasons)s, %(cluster_label)s,
    %(amount_usd)s, %(btc_amount)s
);
"""


INSERT_STATE_SQL = """
INSERT INTO pipeline_state (state_key, state_value)
VALUES (%(state_key)s, %(state_value)s)
ON DUPLICATE KEY UPDATE state_value=VALUES(state_value);
"""

INSERT_ETH_TX_SQL = """
INSERT INTO eth_transactions (
    tx_hash, block_number, timestamp, from_address, to_address, value_eth,
    gas_used, status, is_contract_call, input_data, risk_flag_high_value,
    risk_flag_contract, is_suspicious_basic, tx_type, fetched_at
) VALUES (
    %(tx_hash)s, %(block_number)s, %(timestamp)s, %(from_address)s, %(to_address)s, %(value_eth)s,
    %(gas_used)s, %(status)s, %(is_contract_call)s, %(input_data)s, %(risk_flag_high_value)s,
    %(risk_flag_contract)s, %(is_suspicious_basic)s, %(tx_type)s, %(fetched_at)s
)
ON DUPLICATE KEY UPDATE
    block_number=VALUES(block_number),
    timestamp=VALUES(timestamp),
    from_address=VALUES(from_address),
    to_address=VALUES(to_address),
    value_eth=VALUES(value_eth),
    gas_used=VALUES(gas_used),
    status=VALUES(status),
    is_contract_call=VALUES(is_contract_call),
    input_data=VALUES(input_data),
    risk_flag_high_value=VALUES(risk_flag_high_value),
    risk_flag_contract=VALUES(risk_flag_contract),
    is_suspicious_basic=VALUES(is_suspicious_basic),
    tx_type=VALUES(tx_type),
    fetched_at=VALUES(fetched_at),
    updated_at=CURRENT_TIMESTAMP;
"""

INSERT_GRAPH_EDGE_SQL = """
INSERT INTO graph_edges (
    tx_hash, from_address, to_address, value_eth, block_number, timestamp
) VALUES (
    %(tx_hash)s, %(from_address)s, %(to_address)s, %(value_eth)s, %(block_number)s, %(timestamp)s
)
ON DUPLICATE KEY UPDATE
    from_address=VALUES(from_address),
    to_address=VALUES(to_address),
    value_eth=VALUES(value_eth),
    block_number=VALUES(block_number),
    timestamp=VALUES(timestamp);
"""


def _connect(cfg: Config, database: str = None):
    """Create a MariaDB connection with optional database."""
    return mysql.connector.connect(
        host=cfg.mysql_host,
        port=cfg.mysql_port,
        user=cfg.mysql_user,
        password=cfg.mysql_password,
        database=database,
        autocommit=True,
    )


def _is_nan(value) -> bool:
    """Return True when a value is NaN-like (float or numpy float)."""
    try:
        if isinstance(value, float) and math.isnan(value):
            return True
    except TypeError:
        pass
    try:
        return value != value
    except Exception:  # noqa: BLE001
        return False


def _sanitize_rows(rows: Iterable[dict]) -> List[dict]:
    """Convert NaN-like values to None so MySQL treats them as NULL."""
    cleaned: List[dict] = []
    for row in rows:
        cleaned_row = {}
        for key, value in row.items():
            cleaned_row[key] = None if _is_nan(value) else value
        cleaned.append(cleaned_row)
    return cleaned


def get_connection(cfg: Config):
    """Return a connection, creating the database if needed."""
    try:
        return _connect(cfg, database=cfg.mysql_db)
    except mysql.connector.Error as err:
        if err.errno != errorcode.ER_BAD_DB_ERROR:
            raise
        logger.info("Database %s not found, creating it", cfg.mysql_db)
        conn = _connect(cfg)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {cfg.mysql_db}")
        cursor.close()
        conn.close()
        return _connect(cfg, database=cfg.mysql_db)


def ensure_tables(cfg: Config) -> None:
    """Create required tables if they do not exist."""
    conn = get_connection(cfg)
    cursor = conn.cursor()
    cursor.execute(TRANSACTIONS_TABLE_SQL)
    cursor.execute(ALERTS_TABLE_SQL)
    cursor.execute(STATE_TABLE_SQL)
    cursor.execute(ETH_TRANSACTIONS_TABLE_SQL)
    cursor.execute(GRAPH_EDGES_TABLE_SQL)
    cursor.close()
    conn.close()


def upsert_transactions(cfg: Config, rows: Iterable[dict]) -> int:
    """Upsert clean transactions into MariaDB."""
    conn = get_connection(cfg)
    cursor = conn.cursor()
    data = _sanitize_rows(rows)
    if not data:
        return 0
    cursor.executemany(INSERT_TRANSACTION_SQL, data)
    count = cursor.rowcount
    cursor.close()
    conn.close()
    return count


def insert_alerts(cfg: Config, rows: Iterable[dict]) -> int:
    """Insert alert rows into MariaDB."""
    conn = get_connection(cfg)
    cursor = conn.cursor()
    data = _sanitize_rows(rows)
    if not data:
        return 0
    cursor.executemany(INSERT_ALERT_SQL, data)
    count = cursor.rowcount
    cursor.close()
    conn.close()
    return count


def write_state(cfg: Config, state_items: List[dict]) -> None:
    """Write pipeline state key/value pairs to MariaDB."""
    conn = get_connection(cfg)
    cursor = conn.cursor()
    cursor.executemany(INSERT_STATE_SQL, _sanitize_rows(state_items))
    cursor.close()
    conn.close()


def upsert_eth_transactions(cfg: Config, rows: Iterable[dict]) -> int:
    """Upsert Ethereum transaction rows into MariaDB."""
    conn = get_connection(cfg)
    cursor = conn.cursor()
    data = _sanitize_rows(rows)
    if not data:
        return 0
    cursor.executemany(INSERT_ETH_TX_SQL, data)
    count = cursor.rowcount
    cursor.close()
    conn.close()
    return count


def upsert_graph_edges(cfg: Config, rows: Iterable[dict]) -> int:
    """Upsert graph edge rows into MariaDB."""
    conn = get_connection(cfg)
    cursor = conn.cursor()
    data = _sanitize_rows(rows)
    if not data:
        return 0
    cursor.executemany(INSERT_GRAPH_EDGE_SQL, data)
    count = cursor.rowcount
    cursor.close()
    conn.close()
    return count
