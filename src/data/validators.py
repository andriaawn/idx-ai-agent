from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd


@dataclass
class DataQualityResult:
    is_valid: bool
    score: float  # 0.0 to 100.0
    issues: List[str]


class MarketDataValidator:
    """Validate raw provider OHLCV without repairing it first."""

    @staticmethod
    def validate_ohlcv(df: pd.DataFrame) -> DataQualityResult:
        if df.empty:
            return DataQualityResult(False, 0.0, ["Empty DataFrame"])

        required_cols = ["open", "high", "low", "close", "volume"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return DataQualityResult(False, 0.0, [f"Missing columns: {missing_cols}"])

        issues: List[str] = []
        score = 100.0
        hard_invalid = False

        # Timestamp order and identity are provider facts; do not normalize them
        # away before checking their integrity.
        index = df.index
        nat_count = int(pd.isna(index).sum())
        duplicate_count = int(index.duplicated(keep=False).sum())
        non_monotonic = not index.is_monotonic_increasing
        if nat_count:
            issues.append(f"Found {nat_count} NaT timestamps")
            hard_invalid = True
        if duplicate_count:
            issues.append(f"Found {duplicate_count} duplicate timestamps")
            hard_invalid = True
        if non_monotonic:
            issues.append("Timestamps are not monotonic increasing")
            hard_invalid = True

        numeric = pd.DataFrame(index=df.index)
        missing_count = 0
        invalid_count = 0
        non_finite_count = 0
        for col in required_cols:
            raw = df[col]
            coerced = pd.to_numeric(raw, errors="coerce")
            numeric[col] = coerced

            missing = raw.isna()
            invalid = ~missing & coerced.isna()
            non_finite = coerced.notna() & ~np.isfinite(coerced)
            missing_count += int(missing.sum())
            invalid_count += int(invalid.sum())
            non_finite_count += int(non_finite.sum())

        if missing_count:
            issues.append(f"Found {missing_count} missing OHLCV values")
            hard_invalid = True
        if invalid_count:
            issues.append(f"Found {invalid_count} invalid/non-numeric OHLCV values")
            hard_invalid = True
        if non_finite_count:
            issues.append(f"Found {non_finite_count} non-finite OHLCV values")
            hard_invalid = True

        prices = numeric[["open", "high", "low", "close"]]
        invalid_prices = int((prices <= 0).any(axis=1).sum())
        if invalid_prices:
            issues.append(f"Found {invalid_prices} rows with non-positive prices")
            hard_invalid = True

        high_violations = int(
            (numeric["high"] < numeric[["open", "close", "low"]].max(axis=1)).sum()
        )
        low_violations = int(
            (numeric["low"] > numeric[["open", "close", "high"]].min(axis=1)).sum()
        )
        high_low_violations = int((numeric["high"] < numeric["low"]).sum())
        if high_violations:
            issues.append(f"Found {high_violations} high-price structural violations")
            hard_invalid = True
        if low_violations:
            issues.append(f"Found {low_violations} low-price structural violations")
            hard_invalid = True
        if high_low_violations:
            issues.append(f"Found {high_low_violations} high < low violations")
            hard_invalid = True

        negative_volume = int((numeric["volume"] < 0).sum())
        zero_volume = int((numeric["volume"] == 0).sum())
        if negative_volume:
            issues.append(f"Found {negative_volume} negative volume entries")
            hard_invalid = True
        if zero_volume:
            issues.append(f"Found {zero_volume} zero volume entries")
            score -= min(15.0, float((zero_volume / len(df)) * 20.0))
        if len(df) and zero_volume == len(df):
            issues.append("All volume entries are zero")
            hard_invalid = True

        final_score = max(0.0, score)
        return DataQualityResult(not hard_invalid and final_score >= 60.0, final_score, issues)
