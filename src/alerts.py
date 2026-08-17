"""End-of-day monitoring alerts for user-followed scan candidates."""
from sqlalchemy import select
from aiogram import Bot

from src.config.settings import settings
from src.data.normalizers import MarketDataNormalizer
from src.data.providers.yfinance_provider import YFinanceProvider
from src.data.validators import MarketDataValidator
from src.storage.database import AsyncSessionLocal
from src.storage.models import AlertEvent, FollowedCandidate
from src.storage.alert_preferences import get_preferences


def _event(candidate: FollowedCandidate, price: float) -> str | None:
    if candidate.stop_loss is not None and price <= candidate.stop_loss:
        return "STOP_LOSS"
    if candidate.target_1 is not None and price >= candidate.target_1:
        return "TARGET_1"
    if candidate.entry_price is not None and candidate.entry_price * 0.99 <= price <= candidate.entry_price * 1.01:
        return "ENTRY_ZONE"
    if candidate.reference_price is not None and price >= candidate.reference_price * 1.02:
        return "BREAKOUT"
    return None


async def dispatch_follow_alerts() -> int:
    """Evaluate all followed candidates once and send deduplicated EOD alerts."""
    if not settings.telegram_bot_token:
        return 0
    async with AsyncSessionLocal() as session:
        followed = list((await session.execute(select(FollowedCandidate))).scalars())
        sent = 0
        provider = YFinanceProvider()
        bot = Bot(token=settings.telegram_bot_token)
        try:
            for candidate in followed:
                raw = await provider.get_historical_ohlcv(f"{candidate.ticker}.JK", timeframe="1d")
                if raw.empty or not MarketDataValidator.validate_ohlcv(raw).is_valid:
                    continue
                price = float(MarketDataNormalizer.normalize(raw)["close"].iloc[-1])
                event_type = _event(candidate, price)
                if not event_type:
                    continue
                preference = await get_preferences(session, candidate.telegram_user_id)
                enabled = {
                    "ENTRY_ZONE": preference.entry_zone_enabled,
                    "BREAKOUT": preference.breakout_enabled,
                    "TARGET_1": preference.target_1_enabled,
                    "STOP_LOSS": True,
                }[event_type]
                if not enabled:
                    continue
                existing = (await session.execute(select(AlertEvent).where(
                    AlertEvent.followed_candidate_id == candidate.id,
                    AlertEvent.event_type == event_type,
                ))).scalar_one_or_none()
                if existing:
                    continue
                session.add(AlertEvent(followed_candidate_id=candidate.id, event_type=event_type, price=price))
                await session.flush()
                await bot.send_message(
                    candidate.telegram_user_id,
                    f"🔔 <b>{event_type.replace('_', ' ')}</b> — <b>{candidate.ticker}</b>\n"
                    f"Harga penutupan: {price:,.0f}\n"
                    f"Setup: {candidate.setup_name.replace('_', ' ')}\n"
                    "Data harian; evaluasi setelah penutupan pasar.",
                    parse_mode="HTML",
                )
                sent += 1
            await session.commit()
        finally:
            await bot.session.close()
    return sent
