CREATE TABLE IF NOT EXISTS transactions (
    tx_hash VARCHAR(66) PRIMARY KEY,
    block_number BIGINT NOT NULL,
    timestamp DATETIME NULL,
    from_address VARCHAR(64) NULL,
    to_address VARCHAR(64) NULL,
    value_eth DECIMAL(38,18) NOT NULL,
    gas_used BIGINT NULL,
    status TINYINT NULL,
    is_contract_call TINYINT(1) NOT NULL DEFAULT 0,
    input_data TEXT NULL,
    risk_flag_high_value TINYINT(1) NOT NULL DEFAULT 0,
    risk_flag_contract TINYINT(1) NOT NULL DEFAULT 0,
    is_suspicious_basic TINYINT(1) NOT NULL DEFAULT 0,
    tx_type VARCHAR(32) NOT NULL DEFAULT 'ETH Transfer',
    fetched_at DATETIME NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_transactions_block_number (block_number),
    KEY idx_transactions_timestamp (timestamp),
    KEY idx_transactions_from_address (from_address),
    KEY idx_transactions_to_address (to_address),
    KEY idx_transactions_value_eth (value_eth)
);

CREATE TABLE IF NOT EXISTS graph_edges (
    tx_hash VARCHAR(66) PRIMARY KEY,
    from_address VARCHAR(64) NULL,
    to_address VARCHAR(64) NULL,
    value_eth DECIMAL(38,18) NOT NULL,
    block_number BIGINT NOT NULL,
    timestamp DATETIME NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_graph_edges_from_address (from_address),
    KEY idx_graph_edges_to_address (to_address),
    KEY idx_graph_edges_block_number (block_number)
);

CREATE TABLE IF NOT EXISTS addresses (
    address VARCHAR(64) PRIMARY KEY,
    first_seen_block BIGINT NULL,
    last_seen_block BIGINT NULL,
    first_seen_at DATETIME NULL,
    last_seen_at DATETIME NULL,
    total_in_tx_count BIGINT NOT NULL DEFAULT 0,
    total_out_tx_count BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_addresses_last_seen_block (last_seen_block),
    KEY idx_addresses_last_seen_at (last_seen_at)
);
