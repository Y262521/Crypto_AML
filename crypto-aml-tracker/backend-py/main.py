import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from db.mongo import connect_mongo
from db.neo4j import connect_neo4j
from db.mysql import connect_mysql
from routes.transactions import router as tx_router
from routes.clusters import router as cluster_router
from scheduler import create_scheduler, get_next_run_time, pipeline_status


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ───────────────────────────────────────────────────────────────
    await connect_mongo()

    try:
        await connect_neo4j()
    except Exception as e:
        print(f"Neo4j not available — graph features disabled: {e}")

    try:
        await connect_mysql()
    except Exception as e:
        print(f"MySQL not available — falling back to MongoDB: {e}")

    # Start the ETL + clustering scheduler
    scheduler = create_scheduler()
    scheduler.start()
    print(f"Scheduler started — next run: {get_next_run_time()}")

    yield

    # ── shutdown ──────────────────────────────────────────────────────────────
    scheduler.shutdown(wait=False)


app = FastAPI(title="Crypto AML Tracker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tx_router, prefix="/api/transactions")
app.include_router(cluster_router, prefix="/api/clusters")


@app.get("/api/status")
async def get_status():
    """Return pipeline scheduler status — useful for monitoring."""
    return {
        "server_time":       datetime.now(timezone.utc).isoformat(),
        "scheduler": {
            "next_run_at":      get_next_run_time(),
            "last_run_at":      pipeline_status["last_run_at"],
            "last_run_status":  pipeline_status["last_run_status"],
            "last_run_summary": pipeline_status["last_run_summary"],
            "runs_today":       pipeline_status["runs_today"],
            "total_runs":       pipeline_status["total_runs"],
            "schedule":         os.getenv("PIPELINE_SCHEDULE_HOURS", "8,20") + ":00 UTC daily",
        }
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 4000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
