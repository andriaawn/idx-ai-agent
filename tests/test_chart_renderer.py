import copy
import struct
import unittest
from unittest.mock import patch

from src.charting.data import ChartCandle, ChartData, ChartSignal
from src.charting.renderer import ChartRenderer


def chart_data(candles=None, indicators=None, signal=None):
    candles = candles or (
        ChartCandle("2024-01-01", 100.0, 105.0, 98.0, 103.0, 1000.0),
        ChartCandle("2024-01-02", 103.0, 108.0, 101.0, 102.0, 1200.0),
    )
    return ChartData(
        ticker="BBCA.JK", timeframe="1d", candles=candles,
        indicators=indicators or {"ema_20": (100.0, 102.0), "rsi_14": (50.0, 60.0)},
        signal=signal or ChartSignal("BUY", "BUY", "BUY", 103.0, 98.0, 108.0, 108.0, 112.0, 2.0),
        mtf_context={"direction": "BULLISH"}, regime_context={"regime": "BULLISH"},
        data_quality_score=100.0, htf_data_quality_score=None, provider=None, as_of=None,
    )


class TestChartRenderer(unittest.TestCase):
    def test_renders_non_empty_decodable_png_deterministically(self):
        data = chart_data()
        first = ChartRenderer.render(data)
        second = ChartRenderer.render(data)

        self.assertEqual(first, second)
        self.assertEqual(first[:8], b"\x89PNG\r\n\x1a\n")
        self.assertGreater(len(first), 100)
        self.assertEqual(struct.unpack(">I", first[16:20])[0], ChartRenderer.WIDTH)
        self.assertEqual(struct.unpack(">I", first[20:24])[0], ChartRenderer.HEIGHT)

    def test_candles_indicators_and_levels_affect_rendered_output(self):
        rendered = ChartRenderer.render(chart_data())
        changed = chart_data(candles=(
            ChartCandle("2024-01-01", 200.0, 210.0, 190.0, 205.0, 1000.0),
            ChartCandle("2024-01-02", 205.0, 220.0, 200.0, 215.0, 1200.0),
        ), indicators={"ema_20": (200.0, 210.0), "rsi_14": (40.0, 70.0)})

        self.assertNotEqual(rendered, ChartRenderer.render(changed))

    def test_optional_fields_and_short_valid_data_do_not_crash_or_mutate_input(self):
        data = chart_data(
            candles=(ChartCandle("2024-01-01", 100.0, 101.0, 99.0, 100.0, 1.0),),
            indicators={},
            signal=ChartSignal(None, None, None, None, None, None, None, None, None),
        )
        data = ChartData(data.ticker, data.timeframe, data.candles, data.indicators, data.signal, None, None, None, None, None, None)
        original = copy.deepcopy(data)

        output = ChartRenderer.render(data)

        self.assertGreater(len(output), 100)
        self.assertEqual(data, original)

    def test_renderer_does_not_use_network_access(self):
        with patch("socket.create_connection", side_effect=AssertionError("network access")):
            output = ChartRenderer.render(chart_data())

        self.assertEqual(output[:8], b"\x89PNG\r\n\x1a\n")
