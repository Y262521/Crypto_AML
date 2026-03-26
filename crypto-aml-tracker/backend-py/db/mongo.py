import os
from motor.motor_asyncio import AsyncIOMotorClient

client: AsyncIOMotorClient = None
db = None

async def connect_mongo():
    global client, db
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    mongo_db = os.getenv("MONGO_DB", "aml_raw")
    client = AsyncIOMotorClient(uri)
    db = client[mongo_db]
    print(f"MongoDB connected → {mongo_db}")

def get_db():
    return db
