#!/usr/bin/env python3
"""One-off helper: insert temporary mock layering detector hits and delete this script.

Usage: set MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB in environment and run this script.
This script inserts random integer scores (0-10) for five known layering detectors for every entity in the latest completed layering run.
It then deletes itself to avoid leaving temporary insertion code in the repo.
"""
import os
import random
import sys

try:
    import pymysql
    from pymysql.cursors import DictCursor
except Exception:
    print("pymysql is required. Install with: pip install pymysql")
    sys.exit(1)

DETECTORS = [
    'peeling_chain',
    'mixing_interaction',
    'bridge_hopping',
    'shell_wallet_network',
    'high_depth_transaction_chaining',
]

HOST = os.getenv('MYSQL_HOST', 'localhost')
PORT = int(os.getenv('MYSQL_PORT', 3306))
USER = os.getenv('MYSQL_USER', 'hakim')
PASSWORD = os.getenv('MYSQL_PASSWORD', 'hakim22')
DB = os.getenv('MYSQL_DB', 'aml_db')

conn = None
try:
    conn = pymysql.connect(host=HOST, port=PORT, user=USER, password=PASSWORD, db=DB, charset='utf8mb4', cursorclass=DictCursor, autocommit=True)
    cur = conn.cursor()

    cur.execute("SELECT id FROM layering_runs WHERE status = 'completed' ORDER BY completed_at DESC, created_at DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        print('No completed layering run found. Aborting.')
        sys.exit(0)
    run_id = row['id']
    print(f'Using run_id={run_id}')

    cur.execute("SELECT entity_id, entity_type FROM layering_alerts WHERE run_id = %s", (run_id,))
    entities = cur.fetchall()
    if not entities:
        print('No layering_alerts found for run. Aborting.')
        sys.exit(0)

    inserted = 0
    for ent in entities:
        entity_id = ent['entity_id']
        entity_type = ent.get('entity_type') or 'address'
        for det in DETECTORS:
            score = random.randint(0, 10)
            summary = f'Mock hit: {score}'
            cur.execute(
                "INSERT INTO layering_detector_hits (run_id, entity_id, entity_type, detector_type, confidence_score, summary_text, created_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())",
                (run_id, entity_id, entity_type, det, score, summary),
            )
            inserted += 1

    print(f'Inserted {inserted} mock detector hits for {len(entities)} entities.')

finally:
    if conn:
        conn.close()

# Self-delete file so insertion code is not left in repo
try:
    script_path = os.path.realpath(__file__)
    print(f'Deleting script {script_path}')
    os.remove(script_path)
except Exception as e:
    print('Warning: failed to delete script:', e)
