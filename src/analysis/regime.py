from enum import Enum
from typing import Dict, Any
import pandas as pd
from src.indicators.technical import TechnicalIndicators

class MarketRegime(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    SIDEWAYS = "SIDEWAYS"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    UNCERTAIN = "UNCERTAIN"

class MarketRegimeAnalyzer:
    """Analyzes overall market regime (e.g. using IHSG benchmark ^JKSE)."""

    @staticmethod
    def analyze_regime(ihsg_df: pd.DataFrame) -> Dict[str, Any]:
        if ihsg_df.empty or len(ihsg_df) < 50:
            return {"regime": MarketRegime.UNCERTAIN.value, "confidence": 0.5}

        df_calc = TechnicalIndicators.calculate_all(ihsg_df)
        latest = df_calc.iloc[-1]

        close = float(latest["close"])
        ema20 = float(latest["ema_20"])
        ema50 = float(latest["ema_50"])
        rsi = float(latest["rsi_14"])
        atr_pct = float(latest["atr_pct"])

        if atr_pct > 3.0:
            regime = MarketRegime.HIGH_VOLATILITY
            confidence = 0.8
        elif close > ema20 and ema20 > ema50 and rsi > 50:
            regime = MarketRegime.BULLISH
            confidence = 0.9
        elif close < ema20 and ema20 < ema50 and rsi < 50:
            regime = MarketRegime.BEARISH
            confidence = 0.9
        else:
            regime = MarketRegime.SIDEWAYS
            confidence = 0.7

        return {
            "regime": regime.value,
            "confidence": confidence,
            "ihsg_close": close,
            "rsi": rsi,
            "atr_pct": atr_pct
        }
