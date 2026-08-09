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

    BUY_DIRECTION = "BUY"
    SELL_DIRECTION = "SELL"

    @staticmethod
    def _directional_score(
        raw_score: Optional[float],
        source_direction: Optional[str],
        signal_direction: Optional[str],
        maximum: float,
    ) -> float:
        """Award confirmation only when a directional input supports the trade.

        The current setup/risk pipeline is long-only, but accepting an explicit
        direction keeps MTF and regime scoring correct for future short setups.
        Unknown, neutral, or unavailable context intentionally earns no points.
        """
        if raw_score is None or not source_direction or not signal_direction:
            return 0.0

        source = source_direction.upper()
        trade = signal_direction.upper()
        expected_source = "BULLISH" if trade == SignalScorer.BUY_DIRECTION else (
            "BEARISH" if trade == SignalScorer.SELL_DIRECTION else None
        )
        if source != expected_source:
            return 0.0

        bounded_score = max(0.0, min(100.0, raw_score))
        return (bounded_score / 100.0) * maximum

    @staticmethod
    def score_signal(
        snapshot: TechnicalSnapshot, 
        setup: DetectedSetup, 
        risk_plan: Optional[RiskPlan],
        mtf_score: Optional[float] = None,
        mtf_direction: Optional[str] = None,
        regime_status: Optional[str] = None,
        signal_direction: Optional[str] = None,
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
        mtf_weighted = SignalScorer._directional_score(
            mtf_score, mtf_direction, signal_direction, maximum=15.0
        )

        actual_regime = regime_status.upper() if regime_status else "UNAVAILABLE"
        regime_score = SignalScorer._directional_score(
            100.0, actual_regime, signal_direction, maximum=10.0
        )

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
