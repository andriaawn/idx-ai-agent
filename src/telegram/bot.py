import asyncio
import logging
from aiogram import Bot, Dispatcher
from src.config.settings import settings
from src.telegram.handlers import router

async def start_bot():
    if not settings.telegram_bot_token:
        logging.warning("TELEGRAM_BOT_TOKEN is not set. Telegram bot will not start.")
        return

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)

    logging.info("Starting Telegram bot polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
