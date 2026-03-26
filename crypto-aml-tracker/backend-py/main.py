import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from db.mongo import connect_mongo
from db.neo4j import connect_neo4j
from routes.transactions import router as tx_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    await connect_mongo()
    try:
        await connect_neo4j()
    except Exception as e:
        print(f"Neo4j not available — graph features disabled: {e}")
    yield
    # shutdown (nothing needed)

app = FastAPI(title="Crypto AML Tracker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tx_router, prefix="/api/transactions")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 4000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
