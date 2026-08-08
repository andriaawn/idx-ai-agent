import asyncio
import logging
from src.config.settings import settings
from src.config.logging import setup_logging
from src.storage.database import init_db
from src.scripts.scheduler import start_scheduler
from src.telegram.bot import start_bot

async def main():
    setup_logging()
    logging.info("Initializing IDX AI Agent...")

    try:
        await init_db()
        logging.info("Database initialized successfully.")
    except Exception as e:
        logging.warning(f"Database initialization warning: {e}")

    start_scheduler()
    await start_bot()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("IDX AI Agent stopped.")
