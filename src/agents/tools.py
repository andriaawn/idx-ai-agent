import asyncio
import logging
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

    async def analyze_stock(
        self, ticker: str, *, canonical_ticker: Optional[str] = None,
        market_regime: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Runs complete deterministic quant analysis pipeline for a ticker."""
        canonical_ticker = canonical_ticker or await TickerResolver.resolve_ticker(ticker)
        if not canonical_ticker:
            return {"status": "ERROR", "reason": "Ticker is not a valid IDX listing"}

        fetches = [
            self.provider.get_historical_ohlcv(canonical_ticker, timeframe="1d"),
            self.provider.get_historical_ohlcv(canonical_ticker, timeframe="1wk"),
        ]
        if market_regime is None:
            fetches.append(self.get_market_status())
        fetched = await asyncio.gather(*fetches, return_exceptions=True)
        df, htf_df = fetched[0], fetched[1]
        market_regime = fetched[2] if len(fetched) == 3 else market_regime
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
        shared_market_regime = await self.get_market_status()

        async def analyze_with_sem(t: str):
            async with semaphore:
                try:
                    canonical_ticker = t if t.endswith(".JK") else f"{t}.JK"
                    return await self.analyze_stock(
                        t, canonical_ticker=canonical_ticker, market_regime=shared_market_regime
                    )
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

        if save_to_db:
            try:
                await self.save_scan_results_to_db(valid_results, total_scanned=len(tickers))
            except Exception:
                logging.exception("Failed to persist market scan snapshot")

        return valid_results

    async def save_scan_results_to_db(self, scan_results: List[Dict[str, Any]], total_scanned: int) -> int:
        """Persist the ranked scan as a shared immutable research snapshot."""
        from src.storage.scan_results import save_scan_snapshot
        return await save_scan_snapshot(scan_results, total_scanned)

    async def get_latest_scan_candidates(
        self, offset: int = 0, limit: int = 10, signal_type: Optional[str] = None
    ):
        from src.storage.scan_results import get_latest_scan_candidates
        return await get_latest_scan_candidates(offset=offset, limit=limit, signal_type=signal_type)

    async def scan_volume_spikes(
        self,
        tickers: Optional[List[str]] = None,
        max_concurrent: int = 15,
        limit: Optional[int] = None,
        minimum_rvol: float = 1.8,
        minimum_turnover: float = 1_000_000_000.0,
        minimum_price_change_pct: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """Find liquid daily volume expansions with positive price confirmation.

        This is deliberately independent of the full signal score: unusual
        volume alone is research context, not a buy recommendation.
        """
        if not tickers:
            fetched = await IDXUniverseRefresher.fetch_idx_stocks()
            tickers = [stock["ticker"] for stock in fetched]
        if limit and limit > 0:
            tickers = tickers[:limit]

        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_ticker(ticker: str) -> Optional[Dict[str, Any]]:
            canonical_ticker = ticker if ticker.endswith(".JK") else f"{ticker}.JK"
            async with semaphore:
                try:
                    raw = await self.provider.get_historical_ohlcv(canonical_ticker, timeframe="1d")
                except Exception:
                    return None
            if raw.empty or len(raw) < TechnicalIndicators.MINIMUM_HISTORY:
                return None
            validation = MarketDataValidator.validate_ohlcv(raw)
            if not validation.is_valid:
                return None
            clean = MarketDataNormalizer.normalize(raw)
            snapshot = TechnicalIndicators.get_snapshot(clean)
            if snapshot is None or len(clean) < 2:
                return None

            previous_close = float(clean["close"].iloc[-2])
            change_pct = ((snapshot.close - previous_close) / previous_close) * 100.0 if previous_close else 0.0
            turnover = snapshot.close * snapshot.volume
            if (
                snapshot.rvol < minimum_rvol
                or turnover < minimum_turnover
                or change_pct < minimum_price_change_pct
            ):
                return None
            label = "BREAKOUT" if snapshot.trend_alignment == "BULLISH" and snapshot.roc_10 > 3.0 else "VOLUME MOMENTUM"
            return {
                "ticker": canonical_ticker,
                "rvol": snapshot.rvol,
                "turnover": turnover,
                "price_change_pct": round(change_pct, 2),
                "close": snapshot.close,
                "volume": snapshot.volume,
                "trend": snapshot.trend_alignment,
                "label": label,
            }

        results = await asyncio.gather(*(analyze_ticker(ticker) for ticker in tickers))
        spikes = [result for result in results if result is not None]
        return sorted(spikes, key=lambda result: (result["rvol"], result["turnover"]), reverse=True)

    async def list_followed_candidates(self, telegram_user_id: int):
        from src.storage.followed_candidates import list_followed_candidates
        return await list_followed_candidates(telegram_user_id)

    async def get_user_tier(self, telegram_user_id: int):
        from src.storage.followed_candidates import get_user_tier
        return await get_user_tier(telegram_user_id)

    async def follow_latest_candidate(
        self, telegram_user_id: int, username: Optional[str], ticker: str
    ):
        from src.storage.followed_candidates import follow_latest_candidate
        return await follow_latest_candidate(telegram_user_id, username, ticker)

    async def unfollow_candidate(self, telegram_user_id: int, ticker: str) -> bool:
        from src.storage.followed_candidates import unfollow_candidate
        return await unfollow_candidate(telegram_user_id, ticker)

    async def set_subscription_tier(
        self, telegram_user_id: int, tier: str, duration_days: Optional[int] = 30
    ):
        from src.storage.followed_candidates import set_subscription_tier
        return await set_subscription_tier(telegram_user_id, tier, duration_days=duration_days)

    async def update_alert_preference(self, telegram_user_id: int, alert_name: str, enabled: bool) -> bool:
        from src.storage.alert_preferences import update_preference
        return await update_preference(telegram_user_id, alert_name, enabled)
