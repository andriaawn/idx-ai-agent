import pandas as pd


class MarketDataNormalizer:
    """Coerces provider fields into the canonical OHLCV representation.

    Validation is deliberately performed before this method in live pipelines.
    This method never reorders, deduplicates, or imputes provider observations.
    """

    @staticmethod
    def normalize(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df.copy()

        clean_df = df.copy()
        for col in ["open", "high", "low", "close", "volume"]:
            if col in clean_df.columns:
                clean_df[col] = pd.to_numeric(clean_df[col], errors="coerce")
        return clean_df
