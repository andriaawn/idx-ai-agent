"""Tests for the follow-list limit.

Semua fitur bot ini gratis — `FOLLOW_LIMIT` cuma batas teknis anti-abuse
(bukan batas jualan), dan tidak lagi bergantung pada tier user.
"""

import unittest
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession

from src.storage import followed_candidates
from src.storage.followed_candidates import FOLLOW_LIMIT
from src.storage.models import Base, ScanCandidate, ScanRun


def _make_engine():
    return create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)


async def _seed_scan(session, tickers):
    run = ScanRun(total_scanned=len(tickers), candidate_count=len(tickers))
    session.add(run)
    await session.flush()
    for ticker in tickers:
        session.add(ScanCandidate(
            scan_run_id=run.id,
            ticker=ticker,
            signal_type="BUY",
            setup_name="BREAKOUT",
            score=80.0,
            reference_price=1000.0,
            entry_price=1000.0,
            stop_loss=950.0,
            target_1=1100.0,
            risk_reward=2.0,
        ))
    await session.commit()


class TestFollowLimit(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = _make_engine()
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.Session = async_sessionmaker(bind=self.engine, class_=AsyncSession, expire_on_commit=False)

        self._patcher = patch.object(followed_candidates, "AsyncSessionLocal", self.Session)
        self._patcher.start()
        async with self.Session() as session:
            await _seed_scan(session, [f"AAA{i}" for i in range(FOLLOW_LIMIT + 3)])

    async def asyncTearDown(self):
        self._patcher.stop()
        await self.engine.dispose()

    async def test_limit_is_ten_not_two(self):
        """Batas lama 2 (jualan premium) → sekarang 10 (anti-abuse)."""
        self.assertEqual(FOLLOW_LIMIT, 10)

    async def test_user_can_follow_up_to_limit_without_premium(self):
        """User tanpa tier premium tetap bisa follow sampai batas teknis."""
        user_id = 999001
        for i in range(FOLLOW_LIMIT):
            result = await followed_candidates.follow_latest_candidate(user_id, "tester", f"AAA{i}")
            self.assertEqual(result.status, "FOLLOWED", f"gagal di index {i}")

        # Satu lagi harus ditolak karena batas teknis
        overflow = await followed_candidates.follow_latest_candidate(user_id, "tester", f"AAA{FOLLOW_LIMIT}")
        self.assertEqual(overflow.status, "LIMIT_REACHED")
        self.assertEqual(overflow.limit, FOLLOW_LIMIT)

    async def test_limit_does_not_depend_on_subscription_tier(self):
        """Tier premium tidak memberi batas berbeda — semuanya 10."""
        user_id = 999002
        async with self.Session() as session:
            from src.storage.models import UserProfile
            session.add(UserProfile(telegram_user_id=user_id, username="vip", subscription_tier="PREMIUM"))
            await session.commit()

        _, limit, _, _ = await followed_candidates.list_followed_candidates(user_id)
        self.assertEqual(limit, FOLLOW_LIMIT)

    async def test_free_user_list_limit_is_also_ten(self):
        user_id = 999003
        _, limit, _, _ = await followed_candidates.list_followed_candidates(user_id)
        self.assertEqual(limit, FOLLOW_LIMIT)
