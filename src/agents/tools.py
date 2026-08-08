from typing import Dict, Any
from src.data.providers.yfinance_provider import YFinanceProvider
from src.data.normalizers import MarketDataNormalizer
from src.data.validators import MarketDataValidator
from src.indicators.technical import TechnicalIndicators
from src.analysis.regime import MarketRegimeAnalyzer
from src.analysis.setup_detection import SetupDetector
from src.risk.engine import RiskEngine
from src.signals.scoring import SignalScorer
from src.backtesting.engine import BacktestEngine

class QuantAgentTools:
    """Quantitative analysis tools callable by the AI Agent."""

    def __init__(self):
        self.provider = YFinanceProvider()

    async def get_market_status(self) -> Dict[str, Any]:
        ihsg_df = await self.provider.get_historical_ohlcv("^JKSE", timeframe="1d")
        if ihsg_df.empty:
            return {"status": "UNAVAILABLE", "message": "Failed to fetch IHSG data"}
        
        normalized_df = MarketDataNormalizer.normalize(ihsg_df)
        return MarketRegimeAnalyzer.analyze_regime(normalized_df)

    async def analyze_stock(self, ticker: str) -> Dict[str, Any]:
        """Runs complete deterministic quant analysis pipeline for a ticker."""
        df = await self.provider.get_historical_ohlcv(ticker, timeframe="1d")
        if df.empty:
            return {"status": "ERROR", "reason": "No price data found for ticker"}

        clean_df = MarketDataNormalizer.normalize(df)
        val = MarketDataValidator.validate_ohlcv(clean_df)

        if not val.is_valid:
            return {"status": "DATA_UNRELIABLE", "issues": val.issues, "score": val.score}

        snapshot = TechnicalIndicators.get_snapshot(clean_df)
        setup = SetupDetector.detect_setups(ticker, snapshot)
        risk_plan = RiskEngine.calculate_risk_plan(snapshot, setup)
        score_breakdown = SignalScorer.score_signal(snapshot, setup, risk_plan)

        return {
            "status": "SUCCESS",
            "ticker": ticker,
            "data_quality_score": val.score,
            "snapshot": snapshot,
            "setup": setup,
            "risk_plan": risk_plan,
            "score_breakdown": score_breakdown
        }

    async def run_stock_backtest(self, ticker: str) -> Dict[str, Any]:
        """Runs backtest for a ticker over historical data."""
        df = await self.provider.get_historical_ohlcv(ticker, timeframe="1d")
        if df.empty or len(df) < 50:
            return {"status": "ERROR", "reason": "Insufficient historical data"}

        clean_df = MarketDataNormalizer.normalize(df)
        engine = BacktestEngine()
        perf = engine.run_backtest(ticker, clean_df)

        return {
            "status": "SUCCESS",
            "ticker": ticker,
            "total_trades": perf.total_trades,
            "win_rate": perf.win_rate,
            "profit_factor": perf.profit_factor,
            "average_r": perf.average_r,
            "total_return_pct": perf.total_return_pct,
            "max_drawdown_pct": perf.max_drawdown_pct
        }
