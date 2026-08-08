from dataclasses import dataclass
from typing import Optional
from src.indicators.technical import TechnicalSnapshot
from src.analysis.setup_detection import DetectedSetup
from src.risk.engine import RiskPlan

@dataclass
class ScoreBreakdown:
    total_score: float
    trend_score: float
    momentum_score: float
    volume_score: float
    structure_score: float
    mtf_score: float
    regime_score: float
    signal_type: str  # STRONG_BUY, BUY, WATCHLIST, NO_TRADE

class SignalScorer:
    """Transparent Scoring Framework for Signal Generation."""

    @staticmethod
    def score_signal(
        snapshot: TechnicalSnapshot, 
        setup: DetectedSetup, 
        risk_plan: Optional[RiskPlan],
        mtf_score: float = 50.0,
        regime_status: str = "BULLISH",
        min_score_threshold: float = 70.0
    ) -> ScoreBreakdown:
        if not snapshot or not risk_plan or not risk_plan.is_valid_rr:
            return ScoreBreakdown(
                total_score=0.0,
                trend_score=0.0,
                momentum_score=0.0,
                volume_score=0.0,
                structure_score=0.0,
                mtf_score=0.0,
                regime_score=0.0,
                signal_type="NO_TRADE"
            )

        trend_score = 0.0
        if snapshot.trend_alignment == "BULLISH":
            trend_score = 20.0
        elif snapshot.trend_alignment == "NEUTRAL":
            trend_score = 10.0

        momentum_score = 0.0
        if snapshot.rsi_14 > 50:
            momentum_score += 10.0
        if snapshot.roc_10 > 2.0:
            momentum_score += 10.0

        volume_score = min(15.0, snapshot.rvol * 10.0)
        structure_score = setup.quality_score * 0.20
        mtf_weighted = (mtf_score / 100.0) * 15.0
        regime_score = 10.0 if regime_status == "BULLISH" else (5.0 if regime_status == "SIDEWAYS" else 0.0)

        total = trend_score + momentum_score + volume_score + structure_score + mtf_weighted + regime_score
        total_score = round(min(100.0, total), 2)

        if total_score >= 80.0:
            signal_type = "STRONG_BUY"
        elif total_score >= min_score_threshold:
            signal_type = "BUY"
        elif total_score >= 55.0:
            signal_type = "WATCHLIST"
        else:
            signal_type = "NO_TRADE"

        return ScoreBreakdown(
            total_score=total_score,
            trend_score=round(trend_score, 2),
            momentum_score=round(momentum_score, 2),
            volume_score=round(volume_score, 2),
            structure_score=round(structure_score, 2),
            mtf_score=round(mtf_weighted, 2),
            regime_score=round(regime_score, 2),
            signal_type=signal_type
        )
