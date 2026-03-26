import os
from neo4j import AsyncGraphDatabase

driver = None

async def connect_neo4j():
    global driver
    uri  = os.getenv("NEO4J_URI",      "bolt://127.0.0.1:7687")
    user = os.getenv("NEO4J_USER",     "neo4j")
    pwd  = os.getenv("NEO4J_PASSWORD", "")
    driver = AsyncGraphDatabase.driver(uri, auth=(user, pwd))
    # verify connectivity
    async with driver.session() as session:
        await session.run("RETURN 1")
    print("Neo4j connected")

def get_driver():
    return driver
