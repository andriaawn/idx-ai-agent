import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.data.universe import IDXUniverseRefresher
from src.storage.database import AsyncSessionLocal

scheduler = AsyncIOScheduler()

async def job_refresh_universe():
    logging.info("Running scheduled job: Refresh IDX stock universe...")
    try:
        async with AsyncSessionLocal() as session:
            count = await IDXUniverseRefresher.sync_universe_to_db(session)
            logging.info(f"Universe refreshed. Synced {count} new instruments.")
    except Exception as e:
        logging.error(f"Error in job_refresh_universe: {e}")

def start_scheduler():
    scheduler.add_job(job_refresh_universe, "cron", hour=6, minute=0)
    scheduler.start()
    logging.info("APScheduler initialized.")
