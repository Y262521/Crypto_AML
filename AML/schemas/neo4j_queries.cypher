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
