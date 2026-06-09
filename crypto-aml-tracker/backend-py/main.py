import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.mongo import close_mongo, connect_mongo
from db.neo4j import close_neo4j, connect_neo4j
from db.mysql import close_mysql, connect_mysql
from routes.transactions import router as tx_router
from routes.clusters import router as cluster_router
from routes.etl import router as etl_router, get_databases_health as etl_get_databases_health
from routes.layering import ensure_layering_schema, router as layering_router
from routes.placement import ensure_placement_schema, router as placement_router
from routes.risk import router as risk_router
from routes.integration import ensure_integration_schema, router as integration_router
from routes.chain_of_custody import router as custody_router
from routes.mva import ensure_mva_schema, router as mva_router
from routes.mvrv import router as mvrv_router
from routes.chains import router as chains_router
from services.mvrv_calculator import _ensure_hist_price_schema, warm_hist_price_cache
from scheduler import create_scheduler, get_next_run_time, pipeline_status
from settings import get_env

logger = logging.getLogger(__name__)


async def _cleanup_stale_running_rows() -> None:
    """
    Mark any placement_runs rows left in status='running' as 'failed'.

    These rows are stale — they belong to a previous server process that
    crashed or was killed before it could finalise the run.  Leaving them
    as 'running' causes the dashboard to show a ghost RUNNING state even
    when no ETL execution is active.  Called once at startup.
    """
    try:
        from db.mysql import get_pool
        pool = get_pool()
        if pool is None:
            return

        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE placement_runs
                    SET    status       = 'failed',
                           completed_at = NOW(),
                           summary_json = JSON_SET(
                               COALESCE(summary_json, '{}'),
                               '$.error',
                               'Run interrupted: server restarted before pipeline completed.'
                           )
                    WHERE  status = 'running'
                    """
                )
                affected = cur.rowcount

        if affected:
            logger.warning(
                "Startup cleanup: marked %d stale 'running' placement_run(s) as 'failed'.",
                affected,
            )
        else:
            logger.debug("Startup cleanup: no stale running placement_runs found.")

    except Exception as exc:
        # Non-fatal — log and continue.  The status endpoint has its own guard.
        logger.warning("Startup cleanup of stale running rows failed (non-fatal): %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # -- startup --
    await connect_mongo()

    try:
        await connect_neo4j()
        # Phase 1: run Neo4j chain migrations (adds chain_name indexes)
        try:
            from db.neo4j import get_driver as get_neo4j_driver
            from settings import get_env as _get_env
            _neo4j_driver = get_neo4j_driver()
            if _neo4j_driver is not None:
                import sys as _sys
                from pathlib import Path as _Path
                _aml_src = str(_Path(__file__).resolve().parents[2] / "AML" / "src")
                if _aml_src not in _sys.path:
                    _sys.path.insert(0, _aml_src)
                from aml_pipeline.chains.migrations import run_neo4j_chain_migrations
                _neo4j_db = _get_env("NEO4J_DATABASE", default="neo4j")
                await asyncio.to_thread(run_neo4j_chain_migrations, _neo4j_driver, _neo4j_db)
        except Exception as _e:
            print(f"Neo4j chain migration skipped (non-fatal): {_e}")

    except Exception as e:
        print(f"Neo4j not available - graph features disabled: {e}")

    try:
        await connect_mysql()
        # ensure_placement_schema / ensure_layering_schema / ensure_integration_schema
        # are synchronous functions — run them in a thread to avoid blocking the event loop
        await asyncio.to_thread(ensure_placement_schema)
        await asyncio.to_thread(ensure_layering_schema)
        await asyncio.to_thread(ensure_integration_schema)
        # ensure_mva_schema is async — await it directly
        await ensure_mva_schema()
        await _ensure_hist_price_schema()
        # Warm historical price cache once at startup
        await warm_hist_price_cache()
        # Backfill usd_at_execution for all chains using Chainlink prices
        try:
            from services.mvrv_calculator import backfill_usd_at_execution_all_chains
            backfill_result = await backfill_usd_at_execution_all_chains()
            total_updated = backfill_result.get("total_updated", 0)
            if total_updated > 0:
                print(f"💰 USD backfill complete: {total_updated:,} transactions updated across all chains")
                print(f"   Per asset: {backfill_result.get('updated', {})}")
            else:
                print("💰 USD backfill: all transactions already have USD values")
        except Exception as bf_e:
            print(f"USD backfill non-fatal: {bf_e}")
        # ── Stale run cleanup ─────────────────────────────────────────────────
        # Any placement_run row left with status='running' from a previous
        # server process is stale — that process is gone.  Mark them failed so
        # the dashboard never shows a ghost RUNNING state.
        await _cleanup_stale_running_rows()
    except Exception as e:
        print(f"MariaDB schema bootstrap failed - processed transaction features may be unavailable: {e}")

    # Start the ETL + clustering scheduler
    scheduler = create_scheduler()
    scheduler.start()
    print(f"Scheduler started - next run: {get_next_run_time()}")

    yield

    # -- shutdown --
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

app.include_router(tx_router,          prefix="/api/transactions")
app.include_router(cluster_router,     prefix="/api/clusters")
app.include_router(etl_router,         prefix="/api/etl")
app.include_router(placement_router,   prefix="/api/placement")
app.include_router(layering_router,    prefix="/api/layering")
app.include_router(risk_router,        prefix="/api/risk")
app.include_router(integration_router, prefix="/api/integration")
app.include_router(custody_router,     prefix="/api/chain-of-custody")
app.include_router(mva_router,         prefix="/api/mva")
app.include_router(mvrv_router,        prefix="/api/mvrv")
app.include_router(chains_router,      prefix="/api/chains")


@app.get("/api/status")
async def get_status():
    """Return pipeline scheduler status - useful for monitoring."""
    return {
        "server_time": datetime.now(timezone.utc).isoformat(),
        "scheduler": {
            "next_run_at":      get_next_run_time(),
            "last_run_at":      pipeline_status["last_run_at"],
            "last_run_status":  pipeline_status["last_run_status"],
            "last_run_summary": pipeline_status["last_run_summary"],
            "runs_today":       pipeline_status["runs_today"],
            "total_runs":       pipeline_status["total_runs"],
            "schedule":         get_env("PIPELINE_SCHEDULE_HOURS", default="8,20") + ":00 UTC daily",
        },
    }


@app.get("/api/databases/health")
async def get_databases_health():
    """
    Wrapper endpoint for database health — mirrors /api/etl/databases/health.
    Frontend ETL dashboard expects this path specifically.
    """
    return await etl_get_databases_health()


if __name__ == "__main__":
    import uvicorn
    port = int(get_env("PORT", default="4000"))
    host = get_env("HOST", default="0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=True)
