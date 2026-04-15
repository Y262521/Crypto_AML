import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.mongo import close_mongo, connect_mongo
from db.neo4j import close_neo4j, connect_neo4j
from db.mysql import close_mysql, connect_mysql
from routes.transactions import router as tx_router
from routes.clusters import router as cluster_router
from routes.placement import ensure_placement_schema, router as placement_router
from scheduler import create_scheduler, get_next_run_time, pipeline_status
from settings import get_env


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ───────────────────────────────────────────────────────────────
    await connect_mongo()

    try:
        await connect_neo4j()
    except Exception as e:
        print(f"Neo4j not available - graph features disabled: {e}")

    try:
        await connect_mysql()
        await asyncio.to_thread(ensure_placement_schema)
    except Exception as e:
        print(f"MariaDB schema bootstrap failed - processed transaction features may be unavailable: {e}")

    # Start the ETL + clustering scheduler
    scheduler = create_scheduler()
    scheduler.start()
    print(f"Scheduler started — next run: {get_next_run_time()}")

    yield

    # ── shutdown ──────────────────────────────────────────────────────────────
    scheduler.shutdown(wait=False)
    await close_neo4j()
    await close_mysql()
    await close_mongo()


app = FastAPI(title="Wallet Cluster Tracker", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tx_router, prefix="/api/transactions")
app.include_router(cluster_router, prefix="/api/clusters")
app.include_router(placement_router, prefix="/api/placement")


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
            "schedule":         get_env("PIPELINE_SCHEDULE_HOURS", default="8,20") + ":00 UTC daily",
        }
    }


if __name__ == "__main__":
    import uvicorn
    port = int(get_env("PORT", default="4000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
