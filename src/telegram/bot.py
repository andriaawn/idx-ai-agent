import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from src.config.settings import settings
from src.telegram.handlers import router

async def start_bot():
    if not settings.telegram_bot_token:
        logging.warning("TELEGRAM_BOT_TOKEN is not set. Telegram bot will not start.")
        return

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    await bot.set_my_commands([
        BotCommand(command="start",        description="Selamat datang & panduan cepat"),
        BotCommand(command="scan",          description="Scan seluruh IDX — tampilkan 10 peluang terbaik"),
        BotCommand(command="candidates",   description="Daftar semua kandidat scan (gunakan: /candidates 2)"),
        BotCommand(command="signal",       description="Sinyal, chart, entry, SL & target — /signal BBCA"),
        BotCommand(command="analyze",      description="Laporan riset lengkap sebuah saham — /analyze BBCA"),
        BotCommand(command="backtest",     description="Simulasi historis strategi — /backtest BBCA"),
        BotCommand(command="volume_spike", description="Radar saham dengan lonjakan volume hari ini"),
        BotCommand(command="market",       description="Status & rezim pasar IHSG saat ini"),
        BotCommand(command="follow",       description="Pantau kandidat & terima alert — /follow BBCA"),
        BotCommand(command="unfollow",     description="Berhenti memantau saham — /unfollow BBCA"),
        BotCommand(command="alerts",       description="Atur notifikasi entry/breakout/target — /alerts entry on"),
        BotCommand(command="account",      description="Lihat paket & batas monitoring Anda"),
        BotCommand(command="donate",       description="Donasi / Upgrade ke PREMIUM (Mulai Rp 10.000)"),
        BotCommand(command="help",         description="Panduan lengkap semua command"),
    ])

    logging.info("Starting Telegram bot polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
