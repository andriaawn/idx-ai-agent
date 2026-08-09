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

if __name__ == "__main__":
    unittest.main()
