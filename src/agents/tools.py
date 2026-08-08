import asyncio
from typing import Dict, Any, List, Optional
from src.data.providers.yfinance_provider import YFinanceProvider
from src.data.normalizers import MarketDataNormalizer
from src.data.validators import MarketDataValidator
from src.indicators.technical import TechnicalIndicators
from src.analysis.regime import MarketRegimeAnalyzer
from src.analysis.setup_detection import SetupDetector
from src.risk.engine import RiskEngine
from src.signals.scoring import SignalScorer
from src.backtesting.engine import BacktestEngine
from src.data.universe import POPULAR_IDX_STOCKS, IDXUniverseRefresher

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

    async def scan_universe(
        self, 
        tickers: Optional[List[str]] = None, 
        max_concurrent: int = 15,
        limit: Optional[int] = None,
        save_to_db: bool = True
    ) -> List[Dict[str, Any]]:
        """Scans stock universe concurrently for valid setup candidates and persists signals to DB."""
        if not tickers:
            fetched = await IDXUniverseRefresher.fetch_idx_stocks()
            tickers = [s["ticker"] for s in fetched] if fetched else [s["ticker"] for s in POPULAR_IDX_STOCKS]

        if limit and limit > 0:
            tickers = tickers[:limit]

        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_sem(t: str):
            async with semaphore:
                try:
                    return await self.analyze_stock(t)
                except Exception:
                    return {"status": "ERROR", "ticker": t}

        tasks = [analyze_with_sem(t) for t in tickers]
        results = await asyncio.gather(*tasks)

        valid_results = []
        for res in results:
            if res.get("status") == "SUCCESS":
                score = res["score_breakdown"]
                if score.signal_type in ["BUY", "STRONG_BUY", "WATCHLIST"]:
                    valid_results.append(res)

        valid_results.sort(key=lambda x: x["score_breakdown"].total_score, reverse=True)

        if save_to_db and valid_results:
            try:
                await self.save_scan_results_to_db(valid_results)
            except Exception:
                pass

        return valid_results

    async def save_scan_results_to_db(self, scan_results: List[Dict[str, Any]]) -> int:
        """Persists valid scan signal results into the database."""
        from src.storage.database import AsyncSessionLocal
        from src.storage.models import Signal
        from datetime import datetime

        saved_count = 0
        async with AsyncSessionLocal() as session:
            for res in scan_results:
                ticker = res["ticker"]
                score = res["score_breakdown"]
                setup = res["setup"]
                risk = res.get("risk_plan")

                sig = Signal(
                    ticker=ticker,
                    timestamp=datetime.utcnow(),
                    signal_type=score.signal_type,
                    setup_name=setup.setup_type.value if setup else "NO_SETUP",
                    score=score.total_score,
                    entry_price=risk.entry_price if risk else 0.0,
                    stop_loss=risk.stop_loss if risk else 0.0,
                    target_1=risk.target_1 if risk else 0.0,
                    risk_reward=risk.risk_reward_ratio if risk else 0.0,
                    status="ACTIVE"
                )
                session.add(sig)
                saved_count += 1
            await session.commit()
        return saved_count
