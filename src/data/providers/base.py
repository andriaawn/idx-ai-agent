from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd

class MarketDataProvider(ABC):
    """Abstract interface for all market data providers."""

    @abstractmethod
    async def get_historical_ohlcv(
        self, 
        symbol: str, 
        timeframe: str = "1d", 
        start: Optional[datetime] = None, 
        end: Optional[datetime] = None
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data. Returns DataFrame with open, high, low, close, volume columns."""
        pass

    @abstractmethod
    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Fetch real-time or latest quote for a symbol."""
        pass
