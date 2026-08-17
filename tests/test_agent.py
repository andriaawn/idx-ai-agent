import unittest
from unittest.mock import AsyncMock, patch
import numpy as np
import pandas as pd
from src.agents.tools import QuantAgentTools
from src.agents.orchestrator import AgentOrchestrator


def sample_ohlcv(length=80):
    dates = pd.date_range("2024-01-01", periods=length, freq="D")
    prices = np.linspace(1000, 1400, length)
    return pd.DataFrame({
        "open": prices - 2,
        "high": prices + 5,
        "low": prices - 5,
        "close": prices,
        "volume": np.full(length, 20_000),
    }, index=dates)

class TestAgentSystem(unittest.IsolatedAsyncioTestCase):

    async def test_quant_agent_tools(self):
        tools = QuantAgentTools()
        market = await tools.get_market_status()
        self.assertTrue("regime" in market or market.get("status") == "UNAVAILABLE")

        analysis = await tools.analyze_stock("BBCA")
        self.assertIn(analysis["status"], ["SUCCESS", "DATA_UNRELIABLE", "ERROR"])

    async def test_agent_orchestrator(self):
        orchestrator = AgentOrchestrator()
        alert = await orchestrator.process_ticker_analysis("BBCA", detailed=False)
        self.assertGreater(len(alert), 0)
        self.assertIn("BBCA", alert)

    async def test_weekly_fetch_failure_keeps_live_analysis_conservative(self):
        class Provider:
            async def get_historical_ohlcv(self, symbol, timeframe="1d"):
                if timeframe == "1wk":
                    raise RuntimeError("weekly provider unavailable")
                return sample_ohlcv()

        tools = QuantAgentTools()
        tools.provider = Provider()
        tools.get_market_status = AsyncMock(return_value={"regime": "BULLISH"})
        with patch("src.agents.tools.TickerResolver.resolve_ticker", new=AsyncMock(return_value="BBCA.JK")):
            analysis = await tools.analyze_stock("BBCA")

        self.assertEqual(analysis["status"], "SUCCESS")
        self.assertEqual(analysis["mtf_analysis"]["status"], "INSUFFICIENT_DATA")
        self.assertEqual(analysis["score_breakdown"].mtf_score, 0.0)
        self.assertIn("chart_data", analysis)
        self.assertEqual(analysis["chart_data"].signal.verdict, analysis["score_breakdown"].signal_type)
        self.assertEqual(
            analysis["chart_data"].signal.direction,
            "BUY" if analysis["score_breakdown"].signal_type in {"BUY", "STRONG_BUY"} else None,
        )

    async def test_ihsg_failure_keeps_live_analysis_conservative(self):
        class Provider:
            async def get_historical_ohlcv(self, symbol, timeframe="1d"):
                return sample_ohlcv()

        tools = QuantAgentTools()
        tools.provider = Provider()
        tools.get_market_status = AsyncMock(side_effect=RuntimeError("IHSG unavailable"))
        with patch("src.agents.tools.TickerResolver.resolve_ticker", new=AsyncMock(return_value="BBCA.JK")):
            analysis = await tools.analyze_stock("BBCA")

        self.assertEqual(analysis["status"], "SUCCESS")
        self.assertEqual(analysis["market_regime"]["status"], "UNAVAILABLE")
        self.assertEqual(analysis["score_breakdown"].regime_score, 0.0)

    async def test_invalid_daily_raw_data_is_rejected_before_normalization(self):
        class Provider:
            async def get_historical_ohlcv(self, symbol, timeframe="1d"):
                df = sample_ohlcv()
                if timeframe == "1d" and symbol == "BBCA.JK":
                    df.loc[df.index[0], "open"] = None
                return df

        tools = QuantAgentTools()
        tools.provider = Provider()
        tools.get_market_status = AsyncMock(return_value={"regime": "BULLISH"})
        with patch("src.agents.tools.TickerResolver.resolve_ticker", new=AsyncMock(return_value="BBCA.JK")):
            analysis = await tools.analyze_stock("BBCA")

        self.assertEqual(analysis["status"], "DATA_UNRELIABLE")
        self.assertIn("missing OHLCV", " ".join(analysis["issues"]))

    async def test_invalid_ihsg_raw_data_is_unavailable(self):
        class Provider:
            async def get_historical_ohlcv(self, symbol, timeframe="1d"):
                df = sample_ohlcv()
                if symbol == "^JKSE":
                    df.loc[df.index[0], "volume"] = None
                return df

        tools = QuantAgentTools()
        tools.provider = Provider()
        market = await tools.get_market_status()

        self.assertEqual(market["status"], "UNAVAILABLE")
        self.assertIn("missing OHLCV", " ".join(market["issues"]))

    async def test_invalid_weekly_data_is_not_used_for_mtf(self):
        class Provider:
            async def get_historical_ohlcv(self, symbol, timeframe="1d"):
                df = sample_ohlcv()
                if timeframe == "1wk":
                    df["high"] = df["low"] - 1
                return df

        tools = QuantAgentTools()
        tools.provider = Provider()
        tools.get_market_status = AsyncMock(return_value={"regime": "BULLISH"})
        with patch("src.agents.tools.TickerResolver.resolve_ticker", new=AsyncMock(return_value="BBCA.JK")):
            analysis = await tools.analyze_stock("BBCA")

        self.assertEqual(analysis["status"], "SUCCESS")
        self.assertEqual(analysis["htf_data_quality_score"], 0.0)
        self.assertEqual(analysis["mtf_analysis"]["direction"], "UNAVAILABLE")

    async def test_insufficient_weekly_data_is_not_used_for_mtf(self):
        class Provider:
            async def get_historical_ohlcv(self, symbol, timeframe="1d"):
                return sample_ohlcv(20 if timeframe == "1wk" else 80)

        tools = QuantAgentTools()
        tools.provider = Provider()
        tools.get_market_status = AsyncMock(return_value={"regime": "BULLISH"})
        with patch("src.agents.tools.TickerResolver.resolve_ticker", new=AsyncMock(return_value="BBCA.JK")):
            analysis = await tools.analyze_stock("BBCA")

        self.assertEqual(analysis["status"], "SUCCESS")
        self.assertIsNone(analysis["htf_snapshot"])
        self.assertEqual(analysis["mtf_analysis"]["status"], "INSUFFICIENT_DATA")

    async def test_volume_spike_requires_relative_volume_and_positive_price_confirmation(self):
        qualifying = sample_ohlcv(25)
        qualifying.loc[qualifying.index[-2], "open"] = 998.0
        qualifying.loc[qualifying.index[-2], "high"] = 1_005.0
        qualifying.loc[qualifying.index[-2], "low"] = 995.0
        qualifying.loc[qualifying.index[-2], "close"] = 1_000.0

        qualifying.loc[qualifying.index[-1], "open"] = 1_002.0
        qualifying.loc[qualifying.index[-1], "high"] = 1_035.0
        qualifying.loc[qualifying.index[-1], "low"] = 1_000.0
        qualifying.loc[qualifying.index[-1], "close"] = 1_030.0
        qualifying.loc[qualifying.index[-1], "volume"] = 100_000
        rejected = sample_ohlcv(25)

        class Provider:
            async def get_historical_ohlcv(self, symbol, timeframe="1d"):
                return qualifying if symbol == "GOOD.JK" else rejected

        tools = QuantAgentTools()
        tools.provider = Provider()
        results = await tools.scan_volume_spikes(
            tickers=["GOOD", "QUIET"], minimum_turnover=0.0, minimum_rvol=1.8
        )

        self.assertEqual([result["ticker"] for result in results], ["GOOD.JK"])
        self.assertGreater(results[0]["rvol"], 1.8)
        self.assertGreater(results[0]["price_change_pct"], 1.0)

if __name__ == "__main__":
    unittest.main()
