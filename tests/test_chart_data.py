import unittest

import numpy as np
import pandas as pd

from src.charting.data import ChartDataAdapter
from src.indicators.technical import TechnicalIndicators
from src.risk.engine import RiskPlan
from src.signals.scoring import ScoreBreakdown


def sample_ohlcv(length=30):
    dates = pd.date_range("2024-01-01", periods=length, freq="D")
    prices = np.linspace(100.0, 130.0, length)
    return pd.DataFrame({
        "open": prices - 1,
        "high": prices + 2,
        "low": prices - 2,
        "close": prices,
        "volume": np.full(length, 1_000.0),
    }, index=dates)


def score(verdict):
    return ScoreBreakdown(80.0, 20.0, 20.0, 15.0, 15.0, 0.0, 10.0, verdict)


class TestChartDataAdapter(unittest.TestCase):
    def test_preserves_candle_values_indicator_alignment_and_context(self):
        ohlcv = sample_ohlcv()
        risk = RiskPlan(120.0, 119.0, 121.0, 115.0, 130.0, 135.0, 5.0, 10.0, 2.0, 115.0, True)
        mtf = {"direction": "BULLISH", "alignment_score": 90.0}
        regime = {"regime": "BULLISH"}
        as_of = pd.Timestamp("2024-02-01T10:00:00Z")
        chart = ChartDataAdapter.from_analysis(
            ticker="BBCA.JK", ohlcv=ohlcv, risk_plan=risk,
            signal_direction="BUY", mtf_context=mtf, regime_context=regime,
            data_quality_score=100.0, htf_data_quality_score=100.0,
            timeframe="1d", provider="yfinance", as_of=as_of,
            score_breakdown=score("BUY"),
        )
        calculated = TechnicalIndicators.calculate_all(ohlcv)

        self.assertEqual([c.timestamp for c in chart.candles], list(ohlcv.index))
        self.assertEqual([c.open for c in chart.candles], list(ohlcv["open"]))
        self.assertEqual([c.high for c in chart.candles], list(ohlcv["high"]))
        self.assertEqual([c.low for c in chart.candles], list(ohlcv["low"]))
        self.assertEqual([c.close for c in chart.candles], list(ohlcv["close"]))
        self.assertEqual([c.volume for c in chart.candles], list(ohlcv["volume"]))
        for column, values in chart.indicators.items():
            self.assertEqual(len(values), len(chart.candles))
            self.assertEqual(list(values), [
                None if pd.isna(value) else float(value) for value in calculated[column]
            ])
        self.assertEqual(chart.signal.direction, "BUY")
        self.assertEqual(chart.signal.analysis_direction, "BUY")
        self.assertEqual(chart.signal.verdict, "BUY")
        self.assertEqual(chart.signal.take_profit, 130.0)
        self.assertEqual(chart.signal.target_1, 130.0)
        self.assertEqual(chart.signal.target_2, 135.0)
        self.assertEqual(chart.signal.risk_reward, 2.0)
        self.assertEqual(chart.mtf_context, mtf)
        self.assertEqual(chart.regime_context, regime)
        self.assertEqual(chart.data_quality_score, 100.0)
        self.assertEqual(chart.htf_data_quality_score, 100.0)
        self.assertEqual(chart.provider, "yfinance")
        self.assertEqual(chart.as_of, as_of)

    def test_no_trade_preserves_analysis_direction_without_execution_direction(self):
        chart = ChartDataAdapter.from_analysis(
            ticker="BBCA.JK", ohlcv=sample_ohlcv(), risk_plan=None,
            signal_direction="BUY", mtf_context=None, regime_context=None,
            data_quality_score=100.0, htf_data_quality_score=None,
            score_breakdown=score("NO_TRADE"),
        )

        self.assertIsNone(chart.signal.direction)
        self.assertEqual(chart.signal.analysis_direction, "BUY")
        self.assertEqual(chart.signal.verdict, "NO_TRADE")
        self.assertIsNone(chart.signal.entry)
        self.assertIsNone(chart.signal.target_1)
        self.assertIsNone(chart.signal.target_2)

    def test_indicator_availability_matches_existing_indicator_engine(self):
        short = ChartDataAdapter.from_analysis(
            ticker="BBCA.JK", ohlcv=sample_ohlcv(10), risk_plan=None,
            signal_direction=None, mtf_context=None, regime_context=None,
            data_quality_score=100.0, htf_data_quality_score=None,
        )
        calculated = ChartDataAdapter.from_analysis(
            ticker="BBCA.JK", ohlcv=sample_ohlcv(30), risk_plan=None,
            signal_direction=None, mtf_context=None, regime_context=None,
            data_quality_score=100.0, htf_data_quality_score=None,
        )

        self.assertTrue(all(value is None for value in short.indicators["ema_20"]))
        self.assertEqual(calculated.indicators["rsi_14"][0], 50.0)
        self.assertEqual(calculated.indicators["roc_10"][0], 0.0)
        self.assertIsNotNone(calculated.indicators["atr_14"][0])
