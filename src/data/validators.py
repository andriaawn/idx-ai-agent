from dataclasses import dataclass
from typing import List
import pandas as pd

@dataclass
class DataQualityResult:
    is_valid: bool
    score: float  # 0.0 to 100.0
    issues: List[str]

class MarketDataValidator:
    """Validates financial market data for anomalies, zeros, missing values, and inconsistent OHLC relations."""

    @staticmethod
    def validate_ohlcv(df: pd.DataFrame) -> DataQualityResult:
        issues = []
        score = 100.0

        if df.empty:
            return DataQualityResult(is_valid=False, score=0.0, issues=["Empty DataFrame"])

        required_cols = ["open", "high", "low", "close", "volume"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return DataQualityResult(is_valid=False, score=0.0, issues=[f"Missing columns: {missing_cols}"])

        null_count = df[required_cols].isnull().sum().sum()
        if null_count > 0:
            score -= min(30.0, float(null_count * 5.0))
            issues.append(f"Found {null_count} null values")

        invalid_prices = ((df["open"] <= 0) | (df["high"] <= 0) | (df["low"] <= 0) | (df["close"] <= 0)).sum()
        if invalid_prices > 0:
            score -= min(40.0, float(invalid_prices * 10.0))
            issues.append(f"Found {invalid_prices} zero/negative prices")

        high_violations = ((df["high"] < df["open"]) | (df["high"] < df["close"]) | (df["high"] < df["low"])).sum()
        low_violations = ((df["low"] > df["open"]) | (df["low"] > df["close"]) | (df["low"] > df["high"])).sum()
        
        if high_violations > 0:
            score -= min(30.0, float(high_violations * 10.0))
            issues.append(f"Found {high_violations} High price logical violations")
        
        if low_violations > 0:
            score -= min(30.0, float(low_violations * 10.0))
            issues.append(f"Found {low_violations} Low price logical violations")

        zero_volume = (df["volume"] <= 0).sum()
        if zero_volume > 0:
            score -= min(15.0, float((zero_volume / len(df)) * 20.0))
            issues.append(f"Found {zero_volume} zero volume entries")

        final_score = max(0.0, score)
        is_valid = final_score >= 60.0 and null_count == 0

        return DataQualityResult(is_valid=is_valid, score=final_score, issues=issues)
