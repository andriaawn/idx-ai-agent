import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
import pandas as pd
import yfinance as yf
from src.data.providers.base import MarketDataProvider

class YFinanceProvider(MarketDataProvider):
    """Primary data provider using Yahoo Finance."""

    def _format_ticker(self, symbol: str) -> str:
        """Format ticker for Yahoo Finance IDX (adds .JK if missing, unless index)."""
        symbol = symbol.upper().strip()
        if symbol.startswith("^"):
            return symbol
        if not symbol.endswith(".JK"):
            symbol = f"{symbol}.JK"
        return symbol

    async def get_historical_ohlcv(
        self, 
        symbol: str, 
        timeframe: str = "1d", 
        start: Optional[datetime] = None, 
        end: Optional[datetime] = None
    ) -> pd.DataFrame:
        ticker_str = self._format_ticker(symbol)
        loop = asyncio.get_event_loop()
        
        def fetch():
            ticker = yf.Ticker(ticker_str)
            kwargs = {"interval": timeframe}
            if start:
                kwargs["start"] = start
            if end:
                kwargs["end"] = end
            if not start and not end:
                kwargs["period"] = "1y"
                
            df = ticker.history(**kwargs)
            if df.empty:
                return pd.DataFrame()
                
            df = df.rename(columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume"
            })
            return df[["open", "high", "low", "close", "volume"]]

        return await loop.run_in_executor(None, fetch)

    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        ticker_str = self._format_ticker(symbol)
        loop = asyncio.get_event_loop()
        
        def fetch():
            ticker = yf.Ticker(ticker_str)
            info = ticker.fast_info
            return {
                "symbol": symbol,
                "last_price": getattr(info, "last_price", 0.0),
                "previous_close": getattr(info, "previous_close", 0.0),
                "open": getattr(info, "open", 0.0),
                "day_high": getattr(info, "day_high", 0.0),
                "day_low": getattr(info, "day_low", 0.0),
                "volume": getattr(info, "last_volume", 0),
                "timestamp": datetime.utcnow()
            }

        return await loop.run_in_executor(None, fetch)
