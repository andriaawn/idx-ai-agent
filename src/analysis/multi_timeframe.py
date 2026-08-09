from typing import Dict, Any
from src.indicators.technical import TechnicalSnapshot

class MultiTimeframeAnalyzer:
    """Evaluates multi-timeframe alignment between Higher Timeframe (HTF) and Lower Timeframe (LTF)."""

    @staticmethod
    def evaluate_alignment(
        htf_snapshot: TechnicalSnapshot, 
        ltf_snapshot: TechnicalSnapshot
    ) -> Dict[str, Any]:
        if not htf_snapshot or not ltf_snapshot:
            return {
                "alignment_score": None,
                "status": "INSUFFICIENT_DATA",
                "direction": "UNAVAILABLE",
                "htf_trend": htf_snapshot.trend_alignment if htf_snapshot else None,
                "ltf_trend": ltf_snapshot.trend_alignment if ltf_snapshot else None,
            }

        score = 50.0

        if htf_snapshot.trend_alignment == "BULLISH" and ltf_snapshot.trend_alignment == "BULLISH":
            score += 30.0
            status = "STRONG_BULLISH_ALIGNMENT"
            direction = "BULLISH"
        elif htf_snapshot.trend_alignment == "BEARISH" and ltf_snapshot.trend_alignment == "BEARISH":
            score += 30.0
            status = "STRONG_BEARISH_ALIGNMENT"
            direction = "BEARISH"
        elif htf_snapshot.trend_alignment != ltf_snapshot.trend_alignment:
            score -= 20.0
            status = "TIMEFRAME_DIVERGENCE"
            direction = "NEUTRAL"
        else:
            status = "NEUTRAL"
            direction = "NEUTRAL"

        if htf_snapshot.rsi_14 > 50 and ltf_snapshot.rsi_14 > 50:
            score += 10.0
        elif htf_snapshot.rsi_14 < 50 and ltf_snapshot.rsi_14 < 50:
            score += 10.0

        final_score = max(0.0, min(100.0, score))

        return {
            "alignment_score": round(final_score, 2),
            "status": status,
            "direction": direction,
            "htf_trend": htf_snapshot.trend_alignment,
            "ltf_trend": ltf_snapshot.trend_alignment
        }
