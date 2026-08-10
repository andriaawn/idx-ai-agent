import unittest
from unittest.mock import AsyncMock, patch

from src.telegram import handlers


class FakeMessage:
    def __init__(self, text="/analyze BBCA"):
        self.text = text
        self.events = []

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
