from dataclasses import dataclass
from typing import List
from enum import Enum
from src.indicators.technical import TechnicalSnapshot

class SetupType(str, Enum):
    BREAKOUT_RETEST = "BREAKOUT_RETEST"
    MOMENTUM_CONTINUATION = "MOMENTUM_CONTINUATION"
    TREND_PULLBACK = "TREND_PULLBACK"
    SUPPORT_BOUNCE = "SUPPORT_BOUNCE"
    NO_SETUP = "NO_SETUP"

@dataclass
class DetectedSetup:
    setup_type: SetupType
    ticker: str
    evidence: List[str]
    quality_score: float
    invalidation_level: float

class SetupDetector:
    """Detects deterministic price setups from technical snapshots."""

    @staticmethod
    def detect_setups(ticker: str, snapshot: TechnicalSnapshot) -> DetectedSetup:
        if not snapshot:
            return DetectedSetup(
                setup_type=SetupType.NO_SETUP,
                ticker=ticker,
                evidence=["No technical data"],
                quality_score=0.0,
                invalidation_level=0.0
            )

        close = snapshot.close
        ema20 = snapshot.ema_20
        rsi = snapshot.rsi_14
        rvol = snapshot.rvol
        roc = snapshot.roc_10
        supports = snapshot.support_levels
        resistances = snapshot.resistance_levels

        if resistances:
            nearest_res = max(resistances)
            if close >= nearest_res and rvol > 1.2:
                return DetectedSetup(
                    setup_type=SetupType.BREAKOUT_RETEST,
                    ticker=ticker,
                    evidence=[
                        f"Price {close} broke above resistance level {nearest_res}",
                        f"Volume expansion confirmed (RVOL: {rvol})"
                    ],
                    quality_score=85.0,
                    invalidation_level=nearest_res * 0.98
                )

        if snapshot.trend_alignment == "BULLISH" and rsi > 55 and roc > 3.0 and rvol >= 1.1:
            return DetectedSetup(
                setup_type=SetupType.MOMENTUM_CONTINUATION,
                ticker=ticker,
                evidence=[
                    f"Strong trend alignment (EMA20: {ema20})",
                    f"Positive momentum ROC_10: {roc}%",
                    f"RSI bullish zone: {rsi}"
                ],
                quality_score=80.0,
                invalidation_level=snapshot.ema_20
            )

        if snapshot.trend_alignment == "BULLISH":
            dist_pct = abs(close - ema20) / ema20 * 100.0
            if dist_pct <= 2.0 and rsi >= 45:
                return DetectedSetup(
                    setup_type=SetupType.TREND_PULLBACK,
                    ticker=ticker,
                    evidence=[
                        f"Bullish trend with healthy pullback near EMA20 ({ema20})",
                        f"Distance to EMA20: {dist_pct:.2f}%",
                        f"RSI healthy: {rsi}"
                    ],
                    quality_score=75.0,
                    invalidation_level=snapshot.ema_50
                )

        if supports:
            nearest_sup = min(supports)
            dist_sup = abs(close - nearest_sup) / nearest_sup * 100.0
            if dist_sup <= 2.0 and rsi > 40:
                return DetectedSetup(
                    setup_type=SetupType.SUPPORT_BOUNCE,
                    ticker=ticker,
                    evidence=[
                        f"Price bouncing near support level {nearest_sup}",
                        f"RSI recovering: {rsi}"
                    ],
                    quality_score=70.0,
                    invalidation_level=nearest_sup * 0.97
                )

        return DetectedSetup(
            setup_type=SetupType.NO_SETUP,
            ticker=ticker,
            evidence=["Insufficient setup criteria"],
            quality_score=0.0,
            invalidation_level=0.0
        )
