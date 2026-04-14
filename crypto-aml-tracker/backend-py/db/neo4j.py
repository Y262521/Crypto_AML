import os
from neo4j import AsyncGraphDatabase

from settings import get_env

driver = None

async def connect_neo4j():
    global driver
    uri  = os.getenv("NEO4J_URI",      "bolt://127.0.0.1:7687")
    user = os.getenv("NEO4J_USER",     "neo4j")
    pwd  = os.getenv("NEO4J_PASSWORD", "")
    database = get_env("NEO4J_DATABASE", default="neo4j")
    driver = AsyncGraphDatabase.driver(uri, auth=(user, pwd))
    # verify connectivity
    async with driver.session(database=database) as session:
        await session.run("RETURN 1")
    print("Neo4j connected")

async def close_neo4j():
    global driver
    if driver is not None:
        await driver.close()
        driver = None

def get_driver():
    return driver
