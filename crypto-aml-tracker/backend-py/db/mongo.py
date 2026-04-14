import os
from motor.motor_asyncio import AsyncIOMotorClient

from settings import get_mongo_db_name

client: AsyncIOMotorClient = None
db = None

async def connect_mongo():
    global client, db
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    mongo_db = get_mongo_db_name()
    client = AsyncIOMotorClient(uri)
    db = client[mongo_db]
    print(f"MongoDB connected → {mongo_db}")

async def close_mongo():
    global client, db
    if client is not None:
        client.close()
        client = None
        db = None

def get_db():
    return db
