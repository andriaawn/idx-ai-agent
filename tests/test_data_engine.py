import unittest
import pandas as pd
from src.data.validators import MarketDataValidator
from src.data.normalizers import MarketDataNormalizer

class TestDataEngine(unittest.TestCase):

    @staticmethod
    def valid_ohlcv(length=3):
        return pd.DataFrame({
            "open": [100.0] * length,
            "high": [110.0] * length,
            "low": [90.0] * length,
            "close": [105.0] * length,
            "volume": [1000.0] * length,
        }, index=pd.date_range("2024-01-01", periods=length, freq="D"))

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

    def test_normalizer_does_not_impute_or_reorder_provider_data(self):
        df = self.valid_ohlcv()
        df.iloc[1, df.columns.get_loc("open")] = None
        unordered = df.iloc[[2, 0, 1]]

        normalized = MarketDataNormalizer.normalize(unordered)

        self.assertTrue(normalized["open"].isna().iloc[2])
        self.assertListEqual(list(normalized.index), list(unordered.index))

    def test_missing_each_required_value_is_hard_invalid(self):
        for column in ["open", "high", "low", "close", "volume"]:
            with self.subTest(column=column):
                df = self.valid_ohlcv()
                df.loc[df.index[0], column] = None
                result = MarketDataValidator.validate_ohlcv(df)
                self.assertFalse(result.is_valid)
                self.assertIn("missing OHLCV", " ".join(result.issues))

    def test_non_numeric_ohlcv_is_hard_invalid(self):
        for column in ["open", "high", "low", "close", "volume"]:
            with self.subTest(column=column):
                df = self.valid_ohlcv()
                df[column] = df[column].astype("object")
                df.loc[df.index[0], column] = "not-a-number"
                result = MarketDataValidator.validate_ohlcv(df)
                self.assertFalse(result.is_valid)
                self.assertIn("invalid/non-numeric", " ".join(result.issues))

    def test_single_structural_ohlc_contradiction_is_hard_invalid(self):
        df = self.valid_ohlcv()
        df.loc[df.index[1], "high"] = 95.0

        result = MarketDataValidator.validate_ohlcv(df)

        self.assertFalse(result.is_valid)
        self.assertGreaterEqual(result.score, 60.0)
        self.assertIn("structural", " ".join(result.issues))

    def test_volume_policies(self):
        cases = {
            "all_zero": ("volume", [0.0, 0.0, 0.0], "All volume entries are zero"),
            "negative": ("volume", [-1.0, 1000.0, 1000.0], "negative volume"),
        }
        for name, (column, values, expected_issue) in cases.items():
            with self.subTest(case=name):
                df = self.valid_ohlcv()
                df[column] = values
                result = MarketDataValidator.validate_ohlcv(df)
                self.assertFalse(result.is_valid)
                self.assertIn(expected_issue, " ".join(result.issues))

    def test_timestamp_integrity_is_hard_invalid(self):
        duplicate = self.valid_ohlcv()
        duplicate.index = pd.DatetimeIndex([duplicate.index[0], duplicate.index[0], duplicate.index[2]])
        unordered = self.valid_ohlcv().iloc[[1, 0, 2]]
        nat = self.valid_ohlcv()
        nat.index = pd.DatetimeIndex([nat.index[0], pd.NaT, nat.index[2]])

        for df, expected_issue in [
            (duplicate, "duplicate timestamps"),
            (unordered, "not monotonic"),
            (nat, "NaT timestamps"),
        ]:
            with self.subTest(expected_issue=expected_issue):
                result = MarketDataValidator.validate_ohlcv(df)
                self.assertFalse(result.is_valid)
                self.assertIn(expected_issue, " ".join(result.issues))

    def test_non_finite_values_are_hard_invalid(self):
        for value in [float("inf"), float("-inf")]:
            with self.subTest(value=value):
                df = self.valid_ohlcv()
                df.loc[df.index[0], "close"] = value
                result = MarketDataValidator.validate_ohlcv(df)
                self.assertFalse(result.is_valid)
                self.assertIn("non-finite", " ".join(result.issues))

if __name__ == "__main__":
    unittest.main()
