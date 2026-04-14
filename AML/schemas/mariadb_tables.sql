CREATE TABLE IF NOT EXISTS owners (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    specifics VARCHAR(255) NULL,
    street_address VARCHAR(255) NULL,
    locality VARCHAR(128) NULL,
    city VARCHAR(128) NOT NULL,
    administrative_area VARCHAR(128) NULL,
    postal_code VARCHAR(32) NULL,
    country VARCHAR(128) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_owners_country_city (country, city)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS wallet_clusters (
    id VARCHAR(64) PRIMARY KEY,
    owner_id BIGINT NULL,
    cluster_size INT NOT NULL DEFAULT 1,
    total_balance DECIMAL(38,18) NOT NULL DEFAULT 0,
    risk_level VARCHAR(32) NOT NULL DEFAULT 'normal',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_wallet_clusters_owner_id (owner_id),
    KEY idx_wallet_clusters_size (cluster_size),
    KEY idx_wallet_clusters_balance (total_balance),
    CONSTRAINT fk_wallet_clusters_owner
        FOREIGN KEY (owner_id) REFERENCES owners(id)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS transactions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    tx_hash VARCHAR(66) NOT NULL,
    from_address VARCHAR(64) NULL,
    to_address VARCHAR(64) NULL,
    value_eth DECIMAL(38,18) NOT NULL DEFAULT 0,
    timestamp DATETIME NULL,
    block_number BIGINT NOT NULL,
    is_contract_call TINYINT(1) NOT NULL DEFAULT 0,
    gas_used BIGINT NULL,
    status TINYINT NULL,
    UNIQUE KEY uq_transactions_tx_hash (tx_hash),
    KEY idx_transactions_block_number (block_number),
    KEY idx_transactions_timestamp (timestamp),
    KEY idx_transactions_from_address (from_address),
    KEY idx_transactions_to_address (to_address),
    KEY idx_transactions_value_eth (value_eth)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS addresses (
    address VARCHAR(64) PRIMARY KEY,
    is_contract TINYINT(1) NOT NULL DEFAULT 0,
    first_seen DATETIME NULL,
    last_seen DATETIME NULL,
    total_in DECIMAL(38,18) NOT NULL DEFAULT 0,
    total_out DECIMAL(38,18) NOT NULL DEFAULT 0,
    tx_count BIGINT NOT NULL DEFAULT 0,
    cluster_id VARCHAR(64) NULL,
    KEY idx_addresses_last_seen (last_seen),
    KEY idx_addresses_cluster_id (cluster_id),
    CONSTRAINT fk_addresses_cluster
        FOREIGN KEY (cluster_id) REFERENCES wallet_clusters(id)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS cluster_evidence (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    cluster_id VARCHAR(64) NOT NULL,
    heuristic_name VARCHAR(128) NOT NULL,
    evidence_text TEXT NOT NULL,
    confidence DECIMAL(6,4) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_cluster_evidence_cluster_id (cluster_id),
    KEY idx_cluster_evidence_heuristic_name (heuristic_name),
    CONSTRAINT fk_cluster_evidence_cluster
        FOREIGN KEY (cluster_id) REFERENCES wallet_clusters(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
