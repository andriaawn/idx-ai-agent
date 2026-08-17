"""Compact end-of-day monitoring summaries for followed candidates."""
from collections import defaultdict

from aiogram import Bot
from sqlalchemy import select

from src.config.settings import settings
from src.storage.database import AsyncSessionLocal
from src.storage.models import FollowedCandidate


async def dispatch_daily_monitoring_reports() -> int:
    if not settings.telegram_bot_token:
        return 0
    async with AsyncSessionLocal() as session:
        followed = list((await session.execute(
            select(FollowedCandidate).order_by(FollowedCandidate.telegram_user_id, FollowedCandidate.followed_at)
        )).scalars())
    by_user = defaultdict(list)
    for candidate in followed:
        by_user[candidate.telegram_user_id].append(candidate)
    if not by_user:
        return 0
    bot = Bot(token=settings.telegram_bot_token)
    try:
        for user_id, candidates in by_user.items():
            lines = ["📬 <b>RINGKASAN MONITORING HARIAN</b>", "Snapshot setup yang sedang Anda ikuti:"]
            for item in candidates:
                levels = []
                if item.entry_price is not None:
                    levels.append(f"Entry {item.entry_price:,.0f}")
                if item.stop_loss is not None:
                    levels.append(f"SL {item.stop_loss:,.0f}")
                if item.target_1 is not None:
                    levels.append(f"TP1 {item.target_1:,.0f}")
                lines.append(
                    f"• <b>{item.ticker}</b> — <code>{item.signal_type}</code> (skor {item.score:.0f})\n"
                    f"  {item.setup_name.replace('_', ' ')} | {' | '.join(levels) or 'Level tidak tersedia'}"
                )
            lines.append("Gunakan <code>/follow list</code> untuk melihat monitoring Anda.")
            await bot.send_message(user_id, "\n\n".join(lines), parse_mode="HTML")
    finally:
        await bot.session.close()
    return len(by_user)
