import asyncio
from typing import Dict, Any, List, Optional
from src.data.providers.yfinance_provider import YFinanceProvider
from src.data.normalizers import MarketDataNormalizer
from src.data.validators import MarketDataValidator
from src.indicators.technical import TechnicalIndicators
from src.analysis.regime import MarketRegimeAnalyzer
from src.analysis.multi_timeframe import MultiTimeframeAnalyzer
from src.analysis.setup_detection import SetupDetector
from src.risk.engine import RiskEngine
from src.signals.scoring import SignalScorer
from src.backtesting.engine import BacktestEngine
from src.data.universe import POPULAR_IDX_STOCKS, IDXUniverseRefresher
from src.data.ticker_resolver import TickerResolver
from src.charting.data import ChartDataAdapter

class QuantAgentTools:
    """Quantitative analysis tools callable by the AI Agent."""

    MINIMUM_HTF_BARS = 50

    def __init__(self):
        self.provider = YFinanceProvider()

    async def get_market_status(self) -> Dict[str, Any]:
        ihsg_df = await self.provider.get_historical_ohlcv("^JKSE", timeframe="1d")
        if ihsg_df.empty:
            return {"status": "UNAVAILABLE", "message": "Failed to fetch IHSG data"}
        validation = MarketDataValidator.validate_ohlcv(ihsg_df)
        if not validation.is_valid:
            return {"status": "UNAVAILABLE", "message": "IHSG data is unreliable", "issues": validation.issues}
        normalized_df = MarketDataNormalizer.normalize(ihsg_df)
        return MarketRegimeAnalyzer.analyze_regime(normalized_df)

    async def analyze_stock(self, ticker: str) -> Dict[str, Any]:
        """Runs complete deterministic quant analysis pipeline for a ticker."""
        canonical_ticker = await TickerResolver.resolve_ticker(ticker)
        if not canonical_ticker:
            return {"status": "ERROR", "reason": "Ticker is not a valid IDX listing"}

        df, htf_df, market_regime = await asyncio.gather(
            self.provider.get_historical_ohlcv(canonical_ticker, timeframe="1d"),
            self.provider.get_historical_ohlcv(canonical_ticker, timeframe="1wk"),
            self.get_market_status(),
            return_exceptions=True,
        )
        if isinstance(df, Exception):
            return {"status": "ERROR", "reason": "Failed to fetch daily price data"}
        if isinstance(htf_df, Exception):
            htf_df = df.iloc[0:0]
        if isinstance(market_regime, Exception):
            market_regime = {"status": "UNAVAILABLE", "message": "Failed to fetch IHSG data"}
        if df.empty:
            return {"status": "ERROR", "reason": "No price data found for ticker"}

        val = MarketDataValidator.validate_ohlcv(df)

        if not val.is_valid:
            return {"status": "DATA_UNRELIABLE", "issues": val.issues, "score": val.score}
        clean_df = MarketDataNormalizer.normalize(df)

        snapshot = TechnicalIndicators.get_snapshot(clean_df)
        htf_snapshot = None
        htf_data_quality_score = None
        if not htf_df.empty:
            htf_validation = MarketDataValidator.validate_ohlcv(htf_df)
            if htf_validation.is_valid and len(htf_df) >= self.MINIMUM_HTF_BARS:
                clean_htf_df = MarketDataNormalizer.normalize(htf_df)
                htf_data_quality_score = htf_validation.score
                htf_snapshot = TechnicalIndicators.get_snapshot(clean_htf_df)
            else:
                # An invalid or insufficient HTF dataset is unavailable for MTF
                # scoring, so do not expose its partial diagnostic score as usable
                # HTF data quality.
                htf_data_quality_score = 0.0

        mtf_analysis = MultiTimeframeAnalyzer.evaluate_alignment(htf_snapshot, snapshot)
        setup = SetupDetector.detect_setups(canonical_ticker, snapshot)
        risk_plan = RiskEngine.calculate_risk_plan(snapshot, setup)
        score_breakdown = SignalScorer.score_signal(
            snapshot,
            setup,
            risk_plan,
            mtf_score=mtf_analysis["alignment_score"],
            mtf_direction=mtf_analysis["direction"],
            regime_status=market_regime.get("regime"),
            signal_direction=SignalScorer.BUY_DIRECTION,
        )
        chart_data = ChartDataAdapter.from_analysis(
            ticker=canonical_ticker,
            ohlcv=clean_df,
            risk_plan=risk_plan,
            signal_direction=SignalScorer.BUY_DIRECTION,
            mtf_context=mtf_analysis,
            regime_context=market_regime,
            data_quality_score=val.score,
            htf_data_quality_score=htf_data_quality_score,
            timeframe="1d",
            score_breakdown=score_breakdown,
        )

        return {
            "status": "SUCCESS",
            "ticker": canonical_ticker,
            "data_quality_score": val.score,
            "htf_data_quality_score": htf_data_quality_score,
            "snapshot": snapshot,
            "htf_snapshot": htf_snapshot,
            "mtf_analysis": mtf_analysis,
            "market_regime": market_regime,
            "setup": setup,
            "risk_plan": risk_plan,
            "score_breakdown": score_breakdown,
            "chart_data": chart_data,
        }

    async def run_stock_backtest(self, ticker: str) -> Dict[str, Any]:
        """Runs backtest for a ticker over historical data."""
        canonical_ticker = await TickerResolver.resolve_ticker(ticker)
        if not canonical_ticker:
            return {"status": "ERROR", "reason": "Ticker is not a valid IDX listing"}

        df = await self.provider.get_historical_ohlcv(canonical_ticker, timeframe="1d")
        if df.empty or len(df) < 50:
            return {"status": "ERROR", "reason": "Insufficient historical data"}

        clean_df = MarketDataNormalizer.normalize(df)
        engine = BacktestEngine()
        perf = engine.run_backtest(canonical_ticker, clean_df)

        return {
            "status": "SUCCESS",
            "ticker": canonical_ticker,
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
                db_ticker = ticker[:-3] if ticker.endswith(".JK") else ticker
                score = res["score_breakdown"]
                setup = res["setup"]
                risk = res.get("risk_plan")

                sig = Signal(
                    ticker=db_ticker,
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
