import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
import pandas as pd
import urllib.request
import re
from src.data.providers.base import MarketDataProvider

class GoogleFinanceProvider(MarketDataProvider):
    """Fallback market data provider utilizing Google Finance public web endpoint."""

    def _format_ticker(self, symbol: str) -> str:
        symbol = symbol.upper().strip().replace(".JK", "")
        return f"IDX:{symbol}"

    async def get_historical_ohlcv(
        self, 
        symbol: str, 
        timeframe: str = "1d", 
        start: Optional[datetime] = None, 
        end: Optional[datetime] = None
    ) -> pd.DataFrame:
        # Fallback provider returning empty dataframe if historical data endpoint is not public
        return pd.DataFrame()

    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        formatted_ticker = self._format_ticker(symbol)
        url = f"https://www.google.com/finance/quote/{formatted_ticker.replace(':', '-')}"
        
        loop = asyncio.get_event_loop()
        
        def fetch():
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    html = response.read().decode('utf-8')
                    match = re.search(r'data-last-price="([^"]+)"', html)
                    if match:
                        price = float(match.group(1).replace(',', ''))
                        return {
                            "symbol": symbol,
                            "last_price": price,
                            "source": "Google Finance",
                            "timestamp": datetime.utcnow()
                        }
            except Exception:
                pass
            return {}

        return await loop.run_in_executor(None, fetch)
