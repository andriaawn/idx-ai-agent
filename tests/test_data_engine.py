import unittest
import pandas as pd
from src.data.validators import MarketDataValidator
from src.data.normalizers import MarketDataNormalizer

class TestDataEngine(unittest.TestCase):

    def test_validator_and_normalizer(self):
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        prices = [1000.0 + i * 5 for i in range(30)]
        df = pd.DataFrame({
            "open": prices,
            "high": [p + 10.0 for p in prices],
            "low": [p - 10.0 for p in prices],
            "close": prices,
            "volume": [5000 for _ in range(30)]
        }, index=dates)

        normalized_df = MarketDataNormalizer.normalize(df)
        val = MarketDataValidator.validate_ohlcv(normalized_df)
        self.assertTrue(val.is_valid)
        self.assertGreaterEqual(val.score, 60.0)

if __name__ == "__main__":
    unittest.main()
