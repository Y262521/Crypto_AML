// Run once before the first load.
CREATE CONSTRAINT address_unique IF NOT EXISTS
FOR (a:Address)
REQUIRE a.address IS UNIQUE;

CREATE INDEX transfer_tx_hash IF NOT EXISTS
FOR ()-[r:TRANSFER]-()
ON (r.tx_hash);

CREATE INDEX transfer_block_number IF NOT EXISTS
FOR ()-[r:TRANSFER]-()
ON (r.block_number);

// Top hubs by degree.
MATCH (a:Address)
WITH a, size((a)-[:TRANSFER]-()) AS degree
RETURN a.address AS address, degree
ORDER BY degree DESC
LIMIT 25;

// High-value transfers.
MATCH (s:Address)-[r:TRANSFER]->(t:Address)
WHERE r.value_eth >= 10
RETURN s.address AS from_address,
       t.address AS to_address,
       r.value_eth AS value_eth,
       r.tx_hash AS tx_hash,
       r.block_number AS block_number
ORDER BY r.value_eth DESC
LIMIT 50;

// Money-path exploration starting from a wallet.
MATCH path = (start:Address {address: $address})-[:TRANSFER*1..4]->(target:Address)
RETURN path
LIMIT 20;

// ── Phase 1: Multi-chain indexes ─────────────────────────────────────────────

// Chain name index on Address nodes (created at startup via create_constraints)
CREATE INDEX address_chain_name IF NOT EXISTS
FOR (a:Address)
ON (a.chain_name);

// Chain name index on TRANSFER edges
CREATE INDEX transfer_chain_name IF NOT EXISTS
FOR ()-[r:TRANSFER]-()
ON (r.chain_name);

// ── Multi-chain queries ───────────────────────────────────────────────────────

// All addresses on a specific chain
MATCH (a:Address {chain_name: $chain_name})
RETURN a.address AS address, a.chain_name AS chain
ORDER BY a.address
LIMIT 100;

// High-value transfers on a specific chain
MATCH (s:Address)-[r:TRANSFER]->(t:Address)
WHERE r.chain_name = $chain_name
  AND r.value_eth >= $min_value
RETURN s.address AS from_address,
       t.address AS to_address,
       r.value_eth AS value_eth,
       r.chain_name AS chain,
       r.tx_hash AS tx_hash
ORDER BY r.value_eth DESC
LIMIT 50;

// Cross-chain address activity (same address on multiple chains)
MATCH (a:Address)
WITH a.address AS address, collect(DISTINCT a.chain_name) AS chains
WHERE size(chains) > 1
RETURN address, chains
LIMIT 25;

// Chain summary statistics
MATCH (a:Address)
RETURN a.chain_name AS chain_name,
       count(a) AS address_count
ORDER BY address_count DESC;
