"""User-controlled notification preferences; risk alerts remain mandatory."""
from sqlalchemy.ext.asyncio import AsyncSession

from src.storage.models import AlertPreference, UserProfile

_FIELDS = {"entry": "entry_zone_enabled", "breakout": "breakout_enabled", "target": "target_1_enabled"}

async def get_preferences(session: AsyncSession, user_id: int) -> AlertPreference:
    preference = await session.get(AlertPreference, user_id)
    if preference is None:
        preference = AlertPreference(telegram_user_id=user_id)
        session.add(preference)
        await session.flush()
    return preference

async def update_preference(user_id: int, alert_name: str, enabled: bool) -> bool:
    field = _FIELDS.get(alert_name)
    if field is None:
        return False
    from src.storage.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        if await session.get(UserProfile, user_id) is None:
            session.add(UserProfile(telegram_user_id=user_id))
            await session.flush()
        preference = await get_preferences(session, user_id)
        setattr(preference, field, int(enabled))
        await session.commit()
    return True
