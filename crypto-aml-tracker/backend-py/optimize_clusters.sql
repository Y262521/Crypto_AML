-- Performance optimization indexes for cluster queries
-- These indexes dramatically speed up cluster listing and summary queries

USE aml_clean;

-- Index on addresses.cluster_id for fast filtering and grouping
-- This is critical for the cluster size computation
CREATE INDEX IF NOT EXISTS idx_addresses_cluster_id 
ON addresses(cluster_id);

-- Composite index for wallet_clusters sorting
-- Helps ORDER BY queries on the main cluster listing
CREATE INDEX IF NOT EXISTS idx_wallet_clusters_balance_risk 
ON wallet_clusters(total_balance DESC, risk_level);

-- Index on label_status for filtering and grouping
CREATE INDEX IF NOT EXISTS idx_wallet_clusters_label_status 
ON wallet_clusters(label_status);

-- Index on owner_id for faster joins with owner_list
CREATE INDEX IF NOT EXISTS idx_wallet_clusters_owner_id 
ON wallet_clusters(owner_id);

-- Show current indexes
SHOW INDEX FROM addresses;
SHOW INDEX FROM wallet_clusters;
