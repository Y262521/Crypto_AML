CREATE TABLE IF NOT EXISTS owner_list (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    entity_type VARCHAR(64) NOT NULL DEFAULT 'individual',
    list_category VARCHAR(64) NOT NULL DEFAULT 'watchlist',
    specifics VARCHAR(255) NULL,
    street_address VARCHAR(255) NULL,
    locality VARCHAR(128) NULL,
    city VARCHAR(128) NOT NULL,
    administrative_area VARCHAR(128) NULL,
    postal_code VARCHAR(32) NULL,
    country VARCHAR(128) NOT NULL,
    source_reference VARCHAR(255) NULL,
    notes TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_owner_list_country_city (country, city),
    KEY idx_owner_list_name (full_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS owner_list_addresses (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    owner_list_id BIGINT NOT NULL,
    blockchain_network VARCHAR(64) NOT NULL DEFAULT 'ethereum',
    address VARCHAR(64) NOT NULL,
    is_primary TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_owner_list_addresses_address (address),
    KEY idx_owner_list_addresses_owner_id (owner_list_id),
    KEY idx_owner_list_addresses_network (blockchain_network),
    CONSTRAINT fk_owner_list_addresses_owner
        FOREIGN KEY (owner_list_id) REFERENCES owner_list(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS wallet_clusters (
    id VARCHAR(64) PRIMARY KEY,
    owner_id BIGINT NULL,
    cluster_size INT NOT NULL DEFAULT 1,
    total_balance DECIMAL(38,18) NOT NULL DEFAULT 0,
    risk_level VARCHAR(32) NOT NULL DEFAULT 'normal',
    label_status VARCHAR(32) NOT NULL DEFAULT 'unlabeled',
    matched_owner_address VARCHAR(64) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_labeled_at DATETIME NULL,
    KEY idx_wallet_clusters_owner_id (owner_id),
    KEY idx_wallet_clusters_size (cluster_size),
    KEY idx_wallet_clusters_balance (total_balance),
    KEY idx_wallet_clusters_label_status (label_status),
    CONSTRAINT fk_wallet_clusters_owner
        FOREIGN KEY (owner_id) REFERENCES owner_list(id)
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

CREATE TABLE IF NOT EXISTS placement_runs (
    id VARCHAR(64) PRIMARY KEY,
    source VARCHAR(32) NOT NULL DEFAULT 'auto',
    status VARCHAR(32) NOT NULL DEFAULT 'completed',
    started_at DATETIME NULL,
    completed_at DATETIME NULL,
    summary_json LONGTEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_placement_runs_completed_at (completed_at),
    KEY idx_placement_runs_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS placement_entities (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    entity_id VARCHAR(64) NOT NULL,
    entity_type VARCHAR(16) NOT NULL,
    validation_status VARCHAR(32) NOT NULL,
    validation_confidence DECIMAL(6,4) NOT NULL DEFAULT 0,
    source_kind VARCHAR(32) NOT NULL,
    source_cluster_ids_json LONGTEXT NULL,
    address_count INT NOT NULL DEFAULT 0,
    first_seen_at DATETIME NULL,
    last_seen_at DATETIME NULL,
    metrics_json LONGTEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_placement_entities_run_entity (run_id, entity_id),
    KEY idx_placement_entities_run_id (run_id),
    KEY idx_placement_entities_entity_type (entity_type),
    KEY idx_placement_entities_validation_status (validation_status),
    CONSTRAINT fk_placement_entities_run
        FOREIGN KEY (run_id) REFERENCES placement_runs(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS placement_entity_addresses (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    entity_id VARCHAR(64) NOT NULL,
    address VARCHAR(64) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_placement_entity_addresses (run_id, entity_id, address),
    KEY idx_placement_entity_addresses_run_entity (run_id, entity_id),
    KEY idx_placement_entity_addresses_address (address),
    CONSTRAINT fk_placement_entity_addresses_run
        FOREIGN KEY (run_id) REFERENCES placement_runs(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS placement_behaviors (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    entity_id VARCHAR(64) NOT NULL,
    entity_type VARCHAR(16) NOT NULL,
    behavior_type VARCHAR(64) NOT NULL,
    confidence_score DECIMAL(6,4) NOT NULL DEFAULT 0,
    metrics_json LONGTEXT NULL,
    supporting_tx_hashes_json LONGTEXT NULL,
    first_observed_at DATETIME NULL,
    last_observed_at DATETIME NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_placement_behaviors_run_id (run_id),
    KEY idx_placement_behaviors_entity_id (entity_id),
    KEY idx_placement_behaviors_behavior_type (behavior_type),
    CONSTRAINT fk_placement_behaviors_run
        FOREIGN KEY (run_id) REFERENCES placement_runs(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS placement_traces (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    root_entity_id VARCHAR(64) NOT NULL,
    origin_entity_id VARCHAR(64) NOT NULL,
    path_index INT NOT NULL,
    depth INT NOT NULL DEFAULT 0,
    upstream_entity_id VARCHAR(64) NOT NULL,
    downstream_entity_id VARCHAR(64) NULL,
    path_score DECIMAL(6,4) NOT NULL DEFAULT 0,
    is_terminal TINYINT(1) NOT NULL DEFAULT 0,
    terminal_reason VARCHAR(64) NULL,
    edge_value_eth DECIMAL(38,18) NOT NULL DEFAULT 0,
    supporting_tx_hashes_json LONGTEXT NULL,
    first_seen_at DATETIME NULL,
    last_seen_at DATETIME NULL,
    details_json LONGTEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_placement_traces_run_origin (run_id, origin_entity_id),
    KEY idx_placement_traces_run_root (run_id, root_entity_id),
    KEY idx_placement_traces_path (run_id, path_index),
    CONSTRAINT fk_placement_traces_run
        FOREIGN KEY (run_id) REFERENCES placement_runs(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS placement_detections (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    entity_id VARCHAR(64) NOT NULL,
    entity_type VARCHAR(16) NOT NULL,
    placement_type VARCHAR(32) NOT NULL DEFAULT 'placement_origin',
    confidence_score DECIMAL(6,4) NOT NULL DEFAULT 0,
    placement_score DECIMAL(6,4) NOT NULL DEFAULT 0,
    behavior_score DECIMAL(6,4) NOT NULL DEFAULT 0,
    graph_position_score DECIMAL(6,4) NOT NULL DEFAULT 0,
    temporal_score DECIMAL(6,4) NOT NULL DEFAULT 0,
    reasons_json LONGTEXT NULL,
    behaviors_json LONGTEXT NULL,
    linked_root_entities_json LONGTEXT NULL,
    supporting_tx_hashes_json LONGTEXT NULL,
    metrics_json LONGTEXT NULL,
    first_seen_at DATETIME NULL,
    last_seen_at DATETIME NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_placement_detections_run_entity (run_id, entity_id),
    KEY idx_placement_detections_run_id (run_id),
    KEY idx_placement_detections_score (placement_score),
    CONSTRAINT fk_placement_detections_run
        FOREIGN KEY (run_id) REFERENCES placement_runs(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS placement_labels (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    entity_id VARCHAR(64) NOT NULL,
    entity_type VARCHAR(16) NOT NULL,
    label VARCHAR(64) NOT NULL,
    label_source VARCHAR(64) NOT NULL,
    confidence_score DECIMAL(6,4) NOT NULL DEFAULT 0,
    explanation TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_placement_labels_run_id (run_id),
    KEY idx_placement_labels_entity_id (entity_id),
    KEY idx_placement_labels_label (label),
    CONSTRAINT fk_placement_labels_run
        FOREIGN KEY (run_id) REFERENCES placement_runs(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
