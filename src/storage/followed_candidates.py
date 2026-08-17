"""Per-user monitoring lists built from the latest shared scan snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import func, select

from src.storage.database import AsyncSessionLocal
from src.storage.models import FollowedCandidate, ScanCandidate, ScanRun, UserProfile

from datetime import datetime, timedelta

FREE_FOLLOW_LIMIT = 2


@dataclass(frozen=True)
class FollowResult:
    status: str
    tier: str
    limit: Optional[int]
    followed_count: int


def _resolve_effective_tier(user: Optional[UserProfile]) -> tuple[str, Optional[datetime]]:
    """Determine user's active tier based on expiration timestamp."""
    if user is None:
        return "FREE", None
    tier = user.subscription_tier.upper()
    if tier != "PREMIUM":
        return "FREE", None
    if user.subscription_expires_at is not None:
        if datetime.utcnow() > user.subscription_expires_at:
            return "FREE", user.subscription_expires_at
    return "PREMIUM", user.subscription_expires_at


async def get_user_tier(telegram_user_id: int) -> tuple[str, Optional[datetime]]:
    """Get active tier and expiry datetime for a user."""
    async with AsyncSessionLocal() as session:
        user = await session.get(UserProfile, telegram_user_id)
        return _resolve_effective_tier(user)


async def follow_latest_candidate(telegram_user_id: int, username: Optional[str], ticker: str) -> FollowResult:
    """Follow a ticker only when it exists in the latest market scan."""
    normalized_ticker = ticker.upper().removesuffix(".JK")
    async with AsyncSessionLocal() as session:
        user = await session.get(UserProfile, telegram_user_id)
        if user is None:
            user = UserProfile(telegram_user_id=telegram_user_id, username=username)
            session.add(user)
            await session.flush()
        elif username and user.username != username:
            user.username = username

        tier, _ = _resolve_effective_tier(user)
        limit = None if tier == "PREMIUM" else FREE_FOLLOW_LIMIT
        count = int((await session.execute(
            select(func.count(FollowedCandidate.id)).where(FollowedCandidate.telegram_user_id == telegram_user_id)
        )).scalar_one())
        existing = (await session.execute(
            select(FollowedCandidate).where(
                FollowedCandidate.telegram_user_id == telegram_user_id,
                FollowedCandidate.ticker == normalized_ticker,
            )
        )).scalar_one_or_none()
        if existing:
            return FollowResult("ALREADY_FOLLOWING", tier, limit, count)
        if limit is not None and count >= limit:
            return FollowResult("LIMIT_REACHED", tier, limit, count)

        latest_run = (await session.execute(
            select(ScanRun).order_by(ScanRun.created_at.desc(), ScanRun.id.desc()).limit(1)
        )).scalar_one_or_none()
        if latest_run is None:
            return FollowResult("NO_SCAN", tier, limit, count)
        candidate = (await session.execute(
            select(ScanCandidate).where(
                ScanCandidate.scan_run_id == latest_run.id,
                ScanCandidate.ticker == normalized_ticker,
            )
        )).scalar_one_or_none()
        if candidate is None:
            return FollowResult("NOT_A_CANDIDATE", tier, limit, count)

        session.add(FollowedCandidate(
            telegram_user_id=telegram_user_id,
            ticker=candidate.ticker,
            source_scan_run_id=latest_run.id,
            signal_type=candidate.signal_type,
            setup_name=candidate.setup_name,
            score=candidate.score,
            reference_price=candidate.reference_price,
            entry_price=candidate.entry_price,
            stop_loss=candidate.stop_loss,
            target_1=candidate.target_1,
            risk_reward=candidate.risk_reward,
        ))
        await session.commit()
        return FollowResult("FOLLOWED", tier, limit, count + 1)


async def list_followed_candidates(telegram_user_id: int) -> tuple[str, Optional[int], List[FollowedCandidate], Optional[datetime]]:
    async with AsyncSessionLocal() as session:
        user = await session.get(UserProfile, telegram_user_id)
        tier, expires_at = _resolve_effective_tier(user)
        limit = None if tier == "PREMIUM" else FREE_FOLLOW_LIMIT
        followed = list((await session.execute(
            select(FollowedCandidate)
            .where(FollowedCandidate.telegram_user_id == telegram_user_id)
            .order_by(FollowedCandidate.followed_at.desc(), FollowedCandidate.id.desc())
        )).scalars())
        return tier, limit, followed, expires_at


async def unfollow_candidate(telegram_user_id: int, ticker: str) -> bool:
    normalized_ticker = ticker.upper().removesuffix(".JK")
    async with AsyncSessionLocal() as session:
        followed = (await session.execute(
            select(FollowedCandidate).where(
                FollowedCandidate.telegram_user_id == telegram_user_id,
                FollowedCandidate.ticker == normalized_ticker,
            )
        )).scalar_one_or_none()
        if followed is None:
            return False
        await session.delete(followed)
        await session.commit()
        return True


async def set_subscription_tier(
    telegram_user_id: int, tier: str, duration_days: Optional[int] = 30
) -> Optional[datetime]:
    """Set tier with optional duration in days (default 30 days for PREMIUM)."""
    normalized_tier = tier.upper()
    expires_at = None
    if normalized_tier == "PREMIUM" and duration_days and duration_days > 0:
        expires_at = datetime.utcnow() + timedelta(days=duration_days)

    async with AsyncSessionLocal() as session:
        user = await session.get(UserProfile, telegram_user_id)
        if user is None:
            user = UserProfile(
                telegram_user_id=telegram_user_id,
                subscription_tier=normalized_tier,
                subscription_expires_at=expires_at,
            )
            session.add(user)
        else:
            user.subscription_tier = normalized_tier
            user.subscription_expires_at = expires_at
        await session.commit()
        return expires_at
