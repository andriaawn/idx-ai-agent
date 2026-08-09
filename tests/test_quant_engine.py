import unittest
import pandas as pd
import numpy as np
from src.indicators.technical import TechnicalIndicators
from src.analysis.regime import MarketRegimeAnalyzer
from src.analysis.multi_timeframe import MultiTimeframeAnalyzer

def generate_sample_data(length=60):
    dates = pd.date_range("2024-01-01", periods=length, freq="D")
    prices = np.linspace(100, 150, length) + np.random.normal(0, 1, length)
    df = pd.DataFrame({
        "open": prices - 0.5,
        "high": prices + 1.0,
        "low": prices - 1.0,
        "close": prices,
        "volume": np.random.randint(1000, 5000, length)
    }, index=dates)
    return df


def generate_price_data(closes):
    closes = np.asarray(closes, dtype=float)
    dates = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    return pd.DataFrame({
        "open": closes,
        "high": closes + 1.0,
        "low": closes - 1.0,
        "close": closes,
        "volume": np.full(len(closes), 1_000.0),
    }, index=dates)

class TestQuantEngine(unittest.TestCase):

    def test_technical_indicators_calculation(self):
        df = generate_sample_data(60)
        snapshot = TechnicalIndicators.get_snapshot(df)
        self.assertIsNotNone(snapshot)
        self.assertGreater(snapshot.close, 0)
        self.assertTrue(0 <= snapshot.rsi_14 <= 100)
        self.assertGreater(snapshot.ema_20, 0)
        self.assertIn(snapshot.trend_alignment, ["BULLISH", "BEARISH", "NEUTRAL"])

    def test_market_regime_analysis(self):
        df = generate_sample_data(60)
        result = MarketRegimeAnalyzer.analyze_regime(df)
        self.assertIn("regime", result)
        self.assertGreater(result["confidence"], 0)

    def test_multi_timeframe_alignment(self):
        df1 = generate_sample_data(60)
        df2 = generate_sample_data(60)
        snap1 = TechnicalIndicators.get_snapshot(df1)
        snap2 = TechnicalIndicators.get_snapshot(df2)
        mtf = MultiTimeframeAnalyzer.evaluate_alignment(snap1, snap2)
        self.assertTrue(0 <= mtf["alignment_score"] <= 100)

    def test_multi_timeframe_unavailable_has_no_direction_or_score(self):
        df = generate_sample_data(60)
        snapshot = TechnicalIndicators.get_snapshot(df)

        mtf = MultiTimeframeAnalyzer.evaluate_alignment(None, snapshot)

        self.assertIsNone(mtf["alignment_score"])
        self.assertEqual(mtf["direction"], "UNAVAILABLE")

    def test_rsi_is_100_for_persistent_gains_with_zero_average_loss(self):
        result = TechnicalIndicators.calculate_all(generate_price_data(range(100, 121)))

        self.assertEqual(result["rsi_14"].iloc[-1], 100.0)

    def test_rsi_is_0_for_persistent_losses_with_zero_average_gain(self):
        result = TechnicalIndicators.calculate_all(generate_price_data(range(120, 99, -1)))

        self.assertEqual(result["rsi_14"].iloc[-1], 0.0)

    def test_rsi_is_50_for_flat_prices(self):
        result = TechnicalIndicators.calculate_all(generate_price_data([100.0] * 21))

        self.assertEqual(result["rsi_14"].iloc[-1], 50.0)

    def test_normal_length_rsi_preserves_ordinary_formula(self):
        closes = [100, 102, 101, 104, 103, 105, 104, 107, 106, 108, 107, 109, 108, 111, 110, 112, 111, 114, 113, 115]
        result = TechnicalIndicators.calculate_all(generate_price_data(closes))
        deltas = np.diff(closes, prepend=np.nan)
        deltas[0] = 0.0
        deltas = deltas[-14:]
        average_gain = np.where(deltas > 0, deltas, 0).mean()
        average_loss = np.where(deltas < 0, -deltas, 0).mean()
        expected = 100 - (100 / (1 + average_gain / average_loss))

        self.assertAlmostEqual(result["rsi_14"].iloc[-1], expected)

    def test_insufficient_history_has_no_indicator_columns(self):
        short = generate_price_data(range(100, 119))
        result = TechnicalIndicators.calculate_all(short)

        self.assertEqual(list(result.columns), list(short.columns))
        self.assertEqual(len(result), len(short))

    def test_short_non_empty_history_has_no_snapshot(self):
        snapshot = TechnicalIndicators.get_snapshot(generate_price_data(range(100, 119)))

        self.assertIsNone(snapshot)

    def test_existing_indicators_remain_available_at_minimum_history(self):
        result = TechnicalIndicators.calculate_all(generate_price_data(range(100, 120)))
        snapshot = TechnicalIndicators.get_snapshot(generate_price_data(range(100, 120)))

        self.assertIn("ema_20", result.columns)
        self.assertIn("macd_line", result.columns)
        self.assertIn("atr_14", result.columns)
        self.assertIn("rvol", result.columns)
        self.assertIn("roc_10", result.columns)
        self.assertIsNotNone(snapshot)

if __name__ == "__main__":
    unittest.main()
