"""Adapters for chart-ready data produced after the market-data integrity gate."""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from src.indicators.technical import TechnicalIndicators
from src.risk.engine import RiskPlan
from src.signals.scoring import ScoreBreakdown


@dataclass(frozen=True)
class ChartCandle:
    timestamp: Any
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class ChartSignal:
    """Signal verdict and levels for a chart annotation.

    ``analysis_direction`` records the strategy orientation considered by the
    analysis. ``direction`` is set only for an executable verdict.
    """

    direction: Optional[str]
    analysis_direction: Optional[str]
    verdict: Optional[str]
    entry: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    target_1: Optional[float]
    target_2: Optional[float]
    risk_reward: Optional[float]


@dataclass(frozen=True)
class ChartData:
    """Renderer-neutral, timestamp-aligned market and analysis data."""

    ticker: str
    timeframe: Optional[str]
    candles: Tuple[ChartCandle, ...]
    # Each indicator tuple has the same length and position as ``candles``;
    # its value at offset N belongs to ``candles[N].timestamp``.
    indicators: Dict[str, Tuple[Optional[float], ...]]
    signal: ChartSignal
    mtf_context: Optional[Dict[str, Any]]
    regime_context: Optional[Dict[str, Any]]
    data_quality_score: Optional[float]
    htf_data_quality_score: Optional[float]
    provider: Optional[str]
    as_of: Optional[Any]


class ChartDataAdapter:
    """Build chart data from an already-validated, canonical OHLCV frame.

    This adapter intentionally does not validate, normalize, sort, deduplicate,
    or impute market data. Indicator values reflect the existing
    technical-indicator engine, including any established indicator warm-up
    fill behavior. A missing indicator column is represented as ``None``.
    """

    INDICATOR_COLUMNS = (
        "ema_20", "ema_50", "ema_200", "rsi_14", "macd_line",
        "macd_signal", "atr_14", "roc_10", "rvol",
    )

    @staticmethod
    def _optional_float(value: Any) -> Optional[float]:
        return None if pd.isna(value) else float(value)

    @classmethod
    def from_analysis(
        cls,
        *,
        ticker: str,
        ohlcv: pd.DataFrame,
        risk_plan: Optional[RiskPlan],
        signal_direction: Optional[str],
        mtf_context: Optional[Dict[str, Any]],
        regime_context: Optional[Dict[str, Any]],
        data_quality_score: Optional[float],
        htf_data_quality_score: Optional[float],
        timeframe: Optional[str] = None,
        provider: Optional[str] = None,
        as_of: Optional[Any] = None,
        score_breakdown: Optional[ScoreBreakdown] = None,
    ) -> ChartData:
        calculated = TechnicalIndicators.calculate_all(ohlcv)
        candles = tuple(
            ChartCandle(
                timestamp=timestamp,
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
            )
            for timestamp, row in ohlcv[["open", "high", "low", "close", "volume"]].iterrows()
        )
        indicators = {
            column: tuple(
                cls._optional_float(value) for value in calculated[column]
            ) if column in calculated else tuple(None for _ in ohlcv.index)
            for column in cls.INDICATOR_COLUMNS
        }
        verdict = score_breakdown.signal_type if score_breakdown else None
        direction = signal_direction if verdict in {"BUY", "STRONG_BUY"} else None
        signal = ChartSignal(
            direction=direction,
            analysis_direction=signal_direction,
            verdict=verdict,
            entry=risk_plan.entry_price if risk_plan else None,
            stop_loss=risk_plan.stop_loss if risk_plan else None,
            take_profit=risk_plan.target_1 if risk_plan else None,
            target_1=risk_plan.target_1 if risk_plan else None,
            target_2=risk_plan.target_2 if risk_plan else None,
            risk_reward=risk_plan.risk_reward_ratio if risk_plan else None,
        )
        return ChartData(
            ticker=ticker,
            timeframe=timeframe,
            candles=candles,
            indicators=indicators,
            signal=signal,
            mtf_context=mtf_context,
            regime_context=regime_context,
            data_quality_score=data_quality_score,
            htf_data_quality_score=htf_data_quality_score,
            provider=provider,
            as_of=as_of,
        )
