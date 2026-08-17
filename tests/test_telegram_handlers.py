import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.telegram import handlers


class FakeMessage:
    def __init__(self, text="/analyze BBCA", user_id=12345, username="testuser"):
        self.text = text
        self.events = []
        self.from_user = SimpleNamespace(id=user_id, username=username)

    async def answer(self, text, parse_mode=None):
        self.events.append(("text", text, parse_mode))

    async def answer_photo(self, photo):
        self.events.append(("photo", photo))


def successful_analysis(chart_data):
    return {
        "status": "SUCCESS",
        "chart_data": chart_data,
        "score_breakdown": object(),
        "setup": object(),
        "risk_plan": object(),
    }


class TestTelegramChartDelivery(unittest.IsolatedAsyncioTestCase):
    async def test_analyze_sends_chart_photo_before_report(self):
        message = FakeMessage()
        with patch.object(handlers.tools, "analyze_stock", new=AsyncMock(return_value=successful_analysis(object()))), \
             patch("src.telegram.handlers.ChartRenderer.render", return_value=b"png"), \
             patch("src.telegram.handlers.ResearchReportGenerator.generate_full_research_report", return_value="report"):
            await handlers.handle_analyze(message)

        self.assertEqual(message.events[1][0], "photo")
        self.assertEqual(message.events[2][0], "text")
        self.assertEqual(message.events[2][1], "report")

    async def test_missing_chart_data_still_sends_report(self):
        message = FakeMessage()
        with patch.object(handlers.tools, "analyze_stock", new=AsyncMock(return_value=successful_analysis(None))), \
             patch("src.telegram.handlers.ResearchReportGenerator.generate_full_research_report", return_value="report"):
            await handlers.handle_analyze(message)

        self.assertEqual([event[0] for event in message.events], ["text", "text"])
        self.assertEqual(message.events[-1][1], "report")


class TestCandidatesCommand(unittest.IsolatedAsyncioTestCase):
    async def test_candidates_displays_latest_snapshot_page(self):
        message = FakeMessage("/candidates page 2")
        run = SimpleNamespace(candidate_count=25, total_scanned=964, created_at=__import__("datetime").datetime(2026, 8, 16, 9, 30))
        candidate = SimpleNamespace(
            ticker="BBCA", signal_type="BUY", score=85.0, setup_name="BREAKOUT",
            entry_price=9250.0, stop_loss=9000.0, target_1=9750.0,
        )
        with patch.object(handlers.tools, "get_user_tier", new=AsyncMock(return_value=("PREMIUM", None))), \
             patch.object(handlers.tools, "get_latest_scan_candidates", new=AsyncMock(return_value=(run, [candidate]))) as latest:
            await handlers.handle_candidates(message)

        latest.assert_awaited_once_with(offset=10, limit=10)
        self.assertIn("HALAMAN 2", message.events[0][1])
        self.assertIn("BBCA", message.events[0][1])
        self.assertIn("/candidates page 3", message.events[0][1])

    async def test_candidates_without_snapshot_explains_next_step(self):
        message = FakeMessage("/candidates")
        with patch.object(handlers.tools, "get_latest_scan_candidates", new=AsyncMock(return_value=(None, []))):
            await handlers.handle_candidates(message)

        self.assertIn("/scan", message.events[0][1])


class TestVolumeSpikeCommand(unittest.IsolatedAsyncioTestCase):
    async def test_volume_spike_displays_ranked_radar(self):
        message = FakeMessage("/volume_spike")
        results = [{
            "ticker": "BBCA.JK", "label": "BREAKOUT", "rvol": 2.5,
            "price_change_pct": 3.1, "turnover": 15_000_000_000.0, "trend": "BULLISH",
        }]
        with patch("src.telegram.handlers.IDXUniverseRefresher.fetch_idx_stocks", new=AsyncMock(return_value=[{"ticker": "BBCA"}])), \
             patch.object(handlers.tools, "scan_volume_spikes", new=AsyncMock(return_value=results)):
            await handlers.handle_volume_spike(message)

        self.assertIn("VOLUME SPIKE", message.events[1][1])
        self.assertIn("BBCA", message.events[1][1])

    async def test_renderer_failure_does_not_prevent_report(self):
        message = FakeMessage()
        with patch.object(handlers.tools, "analyze_stock", new=AsyncMock(return_value=successful_analysis(object()))), \
             patch("src.telegram.handlers.ChartRenderer.render", side_effect=RuntimeError("render failed")), \
             patch("src.telegram.handlers.ResearchReportGenerator.generate_full_research_report", return_value="report"):
            await handlers.handle_analyze(message)

        self.assertEqual([event[0] for event in message.events], ["text", "text"])
        self.assertEqual(message.events[-1][1], "report")

    async def test_photo_delivery_failure_does_not_prevent_report(self):
        message = FakeMessage()
        with patch.object(handlers.tools, "analyze_stock", new=AsyncMock(return_value=successful_analysis(object()))), \
             patch("src.telegram.handlers.ChartRenderer.render", return_value=b"png"), \
             patch("src.telegram.handlers.send_png_photo", side_effect=RuntimeError("photo failed")), \
             patch("src.telegram.handlers.ResearchReportGenerator.generate_full_research_report", return_value="report"):
            await handlers.handle_analyze(message)

        self.assertEqual([event[0] for event in message.events], ["text", "text"])
        self.assertEqual(message.events[-1][1], "report")
