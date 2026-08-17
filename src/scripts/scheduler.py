import logging
import asyncio
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.data.universe import IDXUniverseRefresher
from src.storage.database import AsyncSessionLocal
from src.alerts import dispatch_follow_alerts
from src.agents.tools import QuantAgentTools
from src.reports.daily_monitoring import dispatch_daily_monitoring_reports

scheduler = AsyncIOScheduler(timezone=ZoneInfo("Asia/Jakarta"))
market_scan_lock = asyncio.Lock()

async def job_refresh_universe():
    logging.info("Running scheduled job: Refresh IDX stock universe...")
    try:
        async with AsyncSessionLocal() as session:
            count = await IDXUniverseRefresher.sync_universe_to_db(session)
            logging.info(f"Universe refreshed. Synced {count} new instruments.")
    except Exception as e:
        logging.error(f"Error in job_refresh_universe: {e}")

async def job_dispatch_follow_alerts():
    if market_scan_lock.locked():
        logging.warning("Skipping follow alerts because the market scan is still running.")
        return
    try:
        sent = await dispatch_follow_alerts()
        logging.info(f"Follow-alert evaluation completed. Sent {sent} alert(s).")
    except Exception:
        logging.exception("Follow-alert evaluation failed")


async def job_run_market_scan():
    """Produce one shared end-of-day scan snapshot for every bot user."""
    if market_scan_lock.locked():
        logging.warning("Skipping scheduled market scan because a previous scan is still running.")
        return
    try:
        async with market_scan_lock:
            results = await QuantAgentTools().scan_universe()
            logging.info("Scheduled market scan completed. Found %s candidate(s).", len(results))
    except Exception:
        logging.exception("Scheduled market scan failed")

async def job_dispatch_daily_monitoring_reports():
    if market_scan_lock.locked():
        logging.warning("Skipping daily monitoring report because the market scan is still running.")
        return
    try:
        recipients = await dispatch_daily_monitoring_reports()
        logging.info("Daily monitoring reports sent to %s user(s).", recipients)
    except Exception:
        logging.exception("Daily monitoring report failed")

def start_scheduler():
    scheduler.add_job(job_refresh_universe, "cron", hour=6, minute=0)
    scheduler.add_job(
        job_run_market_scan, "cron", hour=16, minute=20,
        id="market_scan", replace_existing=True, max_instances=1, coalesce=True,
    )
    scheduler.add_job(job_dispatch_follow_alerts, "cron", hour=16, minute=30, id="follow_alerts", replace_existing=True)
    scheduler.add_job(job_dispatch_daily_monitoring_reports, "cron", hour=16, minute=40, id="daily_monitoring_report", replace_existing=True)
    scheduler.start()
    logging.info("APScheduler initialized.")
