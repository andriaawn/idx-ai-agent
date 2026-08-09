from dataclasses import dataclass
from typing import List, Optional, Tuple
import pandas as pd
import numpy as np

@dataclass
class TechnicalSnapshot:
    close: float
    volume: int
    ema_20: float
    ema_50: float
    ema_200: float
    rsi_14: float
    macd_line: float
    macd_signal: float
    macd_hist: float
    atr_14: float
    atr_pct: float
    vol_ma_20: float
    rvol: float
    roc_10: float
    support_levels: List[float]
    resistance_levels: List[float]
    trend_alignment: str  # BULLISH, BEARISH, NEUTRAL

class TechnicalIndicators:
    """Deterministic calculation engine for technical indicators."""

    MINIMUM_HISTORY = 20

    @staticmethod
    def calculate_all(df: pd.DataFrame) -> pd.DataFrame:
        """Applies all technical indicator calculations to the DataFrame."""
        if df.empty or len(df) < TechnicalIndicators.MINIMUM_HISTORY:
            return df.copy()

        res = df.copy()

        # 1. Moving Averages
        res["ema_20"] = res["close"].ewm(span=20, adjust=False).mean()
        res["ema_50"] = res["close"].ewm(span=50, adjust=False).mean()
        res["ema_200"] = res["close"].ewm(span=200, adjust=False).mean()
        res["sma_20"] = res["close"].rolling(window=20).mean()

        # 2. RSI (14)
        delta = res["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        # A positive average gain with no average loss is maximally bullish;
        # the inverse is maximally bearish. A flat window is neutral. Values
        # before the 14-bar window retain the existing neutral warm-up value.
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        rsi = rsi.mask((gain > 0) & (loss == 0), 100.0)
        rsi = rsi.mask((gain == 0) & (loss > 0), 0.0)
        rsi = rsi.mask((gain == 0) & (loss == 0), 50.0)
        res["rsi_14"] = rsi.fillna(50.0)

        # 3. MACD (12, 26, 9)
        ema_12 = res["close"].ewm(span=12, adjust=False).mean()
        ema_26 = res["close"].ewm(span=26, adjust=False).mean()
        res["macd_line"] = ema_12 - ema_26
        res["macd_signal"] = res["macd_line"].ewm(span=9, adjust=False).mean()
        res["macd_hist"] = res["macd_line"] - res["macd_signal"]

        # 4. ATR (14)
        high_low = res["high"] - res["low"]
        high_close = (res["high"] - res["close"].shift()).abs()
        low_close = (res["low"] - res["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        res["atr_14"] = tr.rolling(window=14).mean().bfill()
        res["atr_pct"] = (res["atr_14"] / res["close"]) * 100.0

        # 5. Volume Indicators
        res["vol_ma_20"] = res["volume"].rolling(window=20).mean()
        res["rvol"] = res["volume"] / res["vol_ma_20"].replace(0, np.nan)
        res["rvol"] = res["rvol"].fillna(1.0)

        # 6. Rate of Change (ROC 10)
        res["roc_10"] = ((res["close"] - res["close"].shift(10)) / res["close"].shift(10)) * 100.0
        res["roc_10"] = res["roc_10"].fillna(0.0)

        return res

    @staticmethod
    def find_support_resistance(df: pd.DataFrame, window: int = 5) -> Tuple[List[float], List[float]]:
        """Identifies dynamic Support and Resistance levels from recent price swings."""
        if len(df) < window * 2:
            return [], []

        highs = df["high"].values
        lows = df["low"].values

        support = []
        resistance = []

        for i in range(window, len(df) - window):
            if highs[i] == max(highs[i - window : i + window + 1]):
                resistance.append(round(float(highs[i]), 2))
            if lows[i] == min(lows[i - window : i + window + 1]):
                support.append(round(float(lows[i]), 2))

        unique_res = sorted(list(set(resistance)))[-3:]
        unique_sup = sorted(list(set(support)))[:3]
        return unique_sup, unique_res

    @staticmethod
    def get_snapshot(df: pd.DataFrame) -> Optional[TechnicalSnapshot]:
        """Calculates indicators and returns a latest snapshot when available.

        Frames below ``MINIMUM_HISTORY`` have no complete indicator set and
        therefore return ``None`` rather than fabricated snapshot values.
        """
        df_calc = TechnicalIndicators.calculate_all(df)
        if df_calc.empty or len(df_calc) < TechnicalIndicators.MINIMUM_HISTORY:
            return None

        latest = df_calc.iloc[-1]
        sup, res_levels = TechnicalIndicators.find_support_resistance(df_calc)

        close = float(latest["close"])
        ema20 = float(latest["ema_20"])
        ema50 = float(latest["ema_50"])
        
        if close > ema20 > ema50:
            trend = "BULLISH"
        elif close < ema20 < ema50:
            trend = "BEARISH"
        else:
            trend = "NEUTRAL"

        return TechnicalSnapshot(
            close=close,
            volume=int(latest["volume"]),
            ema_20=round(float(latest["ema_20"]), 2),
            ema_50=round(float(latest["ema_50"]), 2),
            ema_200=round(float(latest["ema_200"]), 2) if not np.isnan(latest["ema_200"]) else 0.0,
            rsi_14=round(float(latest["rsi_14"]), 2),
            macd_line=round(float(latest["macd_line"]), 2),
            macd_signal=round(float(latest["macd_signal"]), 2),
            macd_hist=round(float(latest["macd_hist"]), 2),
            atr_14=round(float(latest["atr_14"]), 2),
            atr_pct=round(float(latest["atr_pct"]), 2),
            vol_ma_20=round(float(latest["vol_ma_20"]), 2),
            rvol=round(float(latest["rvol"]), 2),
            roc_10=round(float(latest["roc_10"]), 2),
            support_levels=sup,
            resistance_levels=res_levels,
            trend_alignment=trend
        )
