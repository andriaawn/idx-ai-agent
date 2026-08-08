import unittest
import pandas as pd
import numpy as np
from src.backtesting.engine import BacktestEngine

def generate_trending_data(length=120):
    dates = pd.date_range("2024-01-01", periods=length, freq="D")
    prices = np.linspace(1000, 1600, length) + np.random.normal(0, 5, length)
    df = pd.DataFrame({
        "open": prices - 2.0,
        "high": prices + 5.0,
        "low": prices - 5.0,
        "close": prices,
        "volume": np.random.randint(10000, 50000, length)
    }, index=dates)
    return df

class TestBacktestEngine(unittest.TestCase):

    def test_backtest_engine(self):
        df = generate_trending_data(120)
        engine = BacktestEngine(min_score=60.0, min_rr=1.2)
        perf = engine.run_backtest("BBCA", df)
        
        self.assertIsNotNone(perf)
        self.assertGreaterEqual(perf.win_rate, 0.0)
        self.assertGreaterEqual(perf.total_trades, 0)

if __name__ == "__main__":
    unittest.main()
