import unittest
from unittest.mock import AsyncMock, patch

from src.scripts import scheduler


class TestSchedulerGuards(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        while scheduler.market_scan_lock.locked():
            scheduler.market_scan_lock.release()

    async def test_alerts_are_skipped_while_scan_is_running(self):
        await scheduler.market_scan_lock.acquire()
        try:
            with patch("src.scripts.scheduler.dispatch_follow_alerts", new=AsyncMock()) as dispatch:
                await scheduler.job_dispatch_follow_alerts()
            dispatch.assert_not_awaited()
        finally:
            scheduler.market_scan_lock.release()

    async def test_scan_is_serialized(self):
        with patch("src.scripts.scheduler.QuantAgentTools") as tools_type:
            tools_type.return_value.scan_universe = AsyncMock(return_value=[])
            await scheduler.job_run_market_scan()
        tools_type.return_value.scan_universe.assert_awaited_once()
