import pandas as pd

class MarketDataNormalizer:
    """Normalizes raw dataframes into clean time-series format."""

    @staticmethod
    def normalize(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        
        clean_df = df.copy()
        clean_df = clean_df.sort_index(ascending=True)
        clean_df = clean_df[~clean_df.index.duplicated(keep='first')]
        
        for col in ["open", "high", "low", "close"]:
            if col in clean_df.columns:
                clean_df[col] = pd.to_numeric(clean_df[col], errors='coerce')
        if "volume" in clean_df.columns:
            clean_df["volume"] = pd.to_numeric(clean_df["volume"], errors='coerce').fillna(0).astype('int64')

        clean_df = clean_df.ffill().bfill()
        return clean_df
