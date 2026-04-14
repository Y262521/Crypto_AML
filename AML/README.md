# Wallet Clustering ETL Pipeline (MongoDB -> MySQL -> Neo4j -> MySQL)

This project extracts raw Ethereum blocks into MongoDB, stores a flattened raw-transaction collection for fast lookups, transforms the data into clean CSVs, loads the transformed outputs into MySQL, syncs relationships into Neo4j, and persists wallet-clustering results (clusters + owners + evidence) back into MySQL.

## Architecture

1. **Extract**: fetch raw blocks, store them in MongoDB and `data/raw/`, and explode each block into a MongoDB `raw_transactions` collection.
2. **Transform**: read only the newly fetched or otherwise untransformed blocks, prefer the flattened `raw_transactions` documents, and fall back to raw blocks only when needed.
3. **Load**: upsert the current transform run's processed rows into MySQL, sync relationships into Neo4j, and run clustering to populate wallet ownership groups.

Raw Ethereum blocks are stored idempotently by `block_number`. The extractor also maintains a query-friendly `raw_transactions` collection keyed by `tx_hash`, so MongoDB address and transaction lookups do not need to scan nested block arrays. The live extractor now caps each fetch run at 3 blocks.

## Folder Structure

```text
aml_pipeline/
  README.md
  requirements.txt
  .env.example
  data/
    raw/
    processed/
    staging/
    state/
  schemas/
    mariadb_tables.sql
    neo4j_queries.cypher
  src/
    aml_pipeline/
      config.py
      logging_config.py
      db/
        mongo.py
      etl/
        extract/
        transform/
        load/
          __init__.py
          mongodb_loader.py
          mariadb_loader.py
          neo4j_loader.py
      pipelines/
        daily_pipeline.py
        main_pipeline.py
        run_etl.py
      utils/
        connections.py
        state.py
```

## Environment Setup

1. Create a virtual environment and install dependencies.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

2. Create your environment file.

```bash
cp .env.example .env
```

3. Configure these database settings in `.env`.

- `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB`
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`
- `MONGO_URI`, `MONGO_RAW_DB`, `MONGO_RAW_COLLECTION`
- `MONGO_FLAT_TX_DB`, `MONGO_FLAT_TX_COLLECTION`
- `MONGO_PROCESSED_DB`, `MONGO_PROCESSED_COLLECTION`
- `ETH_NETWORK`

For the local system Neo4j service on this machine, `NEO4J_DATABASE=neo4j` is the correct default.

## Database Prep

### MariaDB

Create the database user you want to use, then point `.env` to it. The loader will automatically create the configured database and the tables from `schemas/mariadb_tables.sql` if they do not exist.

Main tables:

- `transactions`
- `graph_edges`
- `addresses`

### Neo4j

Create a Neo4j instance and set the credentials in `.env`. The load stage creates these graph structures automatically:

- unique constraint on `:Address(address)`
- index on `:TRANSFER(tx_hash)`
- index on `:TRANSFER(block_number)`

The same setup and demo queries are also stored in `schemas/neo4j_queries.cypher`.
If Neo4j authentication fails, `run_load.py` and the pipeline will still finish MongoDB and MariaDB loading by default and report the Neo4j error in the summary. Use `--strict-neo4j` if you want the command to fail hard instead.

## Running Each Stage

### Extract Only

From the repo root:

```bash
python run_extraction.py
```

### Transform Only

This processes only pending / newly fetched raw blocks into `data/processed/transactions.csv` and `data/processed/graph_edges.csv` for the current run. Old processed and staging CSVs are cleared at the start of the transform so each run produces a clean delta for the load stage.

```bash
python run_transform.py
```

### Load Only

This runs all load targets in order:

1. processed transaction backup into MongoDB
2. MariaDB upsert
3. Neo4j graph merge

```bash
python run_load.py
```

### Full Pipeline

Run the complete Extract -> Transform -> Load flow:

```bash
cd /home/hakim/AML_CODE/aml_pipeline
python -m aml_pipeline.pipelines.run_etl
```

Optional flags:

- `--start-block 21000000`
- `--batch 3` (the extractor now caps any request to 3 blocks per run)
- `--skip-mongo-backup`
- `--skip-neo4j`
- `--strict-neo4j`

## Load Stage Details

### MongoDB Backup Loader

File: `src/aml_pipeline/etl/load/mongodb_loader.py`

- reads `data/processed/transactions.csv`
- upserts into MongoDB collection `processed_transactions`
- creates a unique index on `tx_hash`
- exposes `verify_raw_count()` to check the raw block collection

## Raw MongoDB Collections

- `raw_blocks`: immutable-style block snapshots keyed by `block_number`
- `raw_transactions`: one document per transaction keyed by `tx_hash`
- `processed_transactions`: backup of the transformed CSV output

Example `raw_transactions` fields:

- `_id` / `tx_hash`
- `network`
- `block.number`, `block.hash`, `block.timestamp`
- `address_pair.from`, `address_pair.to`
- `value.wei`, `value.eth`
- `gas.gas_limit`, `gas.gas_used`, `gas.gas_price_wei`
- `forensics.input_data`, `forensics.method_id`, `forensics.receipt_status`
- `metadata.processed`, `metadata.processed_at`, `metadata.risk_level`

### MariaDB Loader

File: `src/aml_pipeline/etl/load/mariadb_loader.py`

- reads `data/processed/transactions.csv`
- reads `data/processed/graph_edges.csv`
- creates database and tables from `schemas/mariadb_tables.sql`
- upserts into `transactions` and `graph_edges`
- rebuilds `addresses` from the loaded transactions so counts stay idempotent
- exposes `test_small_load()` to load only the first 50 rows

### Neo4j Loader

File: `src/aml_pipeline/etl/load/neo4j_loader.py`

- reads `data/processed/graph_edges.csv`
- batches rows into Neo4j using `UNWIND`
- merges `:Address` nodes and `:TRANSFER` relationships
- exposes `create_constraints()`, `clear_graph()`, and `test_small_graph_load()`

## Processed Data Contract

### `transactions.csv`

- `block_number`
- `timestamp`
- `tx_hash`
- `from_address`
- `to_address`
- `value_eth`
- `gas_used`
- `status`
- `is_contract_call`
- `input_data`
- `risk_flag_high_value`
- `risk_flag_contract`
- `is_suspicious_basic`
- `tx_type`
- `fetched_at`

### `graph_edges.csv`

- `from_address`
- `to_address`
- `value_eth`
- `block_number`
- `tx_hash`
- `timestamp`

## Outputs

- raw block JSON backups in `data/raw/`
- MongoDB raw block collection `raw_blocks`
- MongoDB flattened raw transaction collection `raw_transactions`
- staging CSVs in `data/staging/`
- processed CSVs in `data/processed/`
- MongoDB backup collection `processed_transactions`
- MariaDB tables `transactions`, `graph_edges`, `addresses`
- Neo4j graph `(:Address)-[:TRANSFER]->(:Address)`

## Performance Notes

- transform now clears old processed outputs before each run to prevent duplicate CSV growth
- raw Mongo block storage uses a unique `block_number` index plus upserts, which prevents duplicate blocks from inflating later stages
- raw Mongo transaction storage uses one document per transaction plus indexes on block number, processed state, and addresses for fast AML queries
- transform prefers the flattened transaction collection and only falls back to raw block blobs when a block still needs backfill
- MariaDB loads use chunked CSV reads and idempotent upserts
- Neo4j loads use batched `UNWIND` writes instead of one transaction per row
- MongoDB backups use bulk upserts keyed by `tx_hash`

## Troubleshooting

- If MariaDB fails, confirm the configured user can create databases and tables.
- If Neo4j fails, confirm Bolt is enabled and the configured database exists.
- If `transactions.csv` or `graph_edges.csv` is missing, run `python run_transform.py` first.
- If dependencies are missing, reactivate the same virtualenv and rerun `pip install -r requirements.txt`.
