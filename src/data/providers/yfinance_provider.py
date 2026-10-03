import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import pandas as pd
import yfinance as yf
from src.data.providers.base import MarketDataProvider

logger = logging.getLogger(__name__)

# Simbol yang terbukti tak punya data di Yahoo (delisted / tidak terdaftar)
# di-cache supaya scan harian tidak memanggil jaringan berulang kali. Tanpa ini,
# tiap scan (~964 ticker) membuang ~1,6s per simbol mati dan menulis 1 log ERROR
# — 111 simbol x tiap scan = ratusan error/hari yang murni noise.
#
# PENTING: satu hasil kosong TIDAK cukup untuk menyimpulkan simbol mati. Yahoo
# kadang mengembalikan kosong secara transient (rate-limit/crumb) untuk simbol
# yang sebenarnya valid — terukur: BBRI (blue chip) sempat kosong di bawah
# concurrency tinggi padahal 245 baris saat diisolasi. Karena itu simbol baru
# ditandai setelah _UNAVAILABLE_CONFIRMATIONS kali kosong berturut-turut.
#
# Cache disimpan di file agar bertahan setelah proses restart. Entri punya TTL:
# simbol yang relisting/listing baru bisa ketemu lagi setelah kedaluwarsa.
_UNAVAILABLE_TTL_SECONDS = 7 * 24 * 3600  # 7 hari
_UNAVAILABLE_CONFIRMATIONS = 3  # butuh 3x kosong berturut-turut


class YFinanceProvider(MarketDataProvider):
    """Primary data provider using Yahoo Finance."""

    # Path file cache. Bisa di-override di test.
    _cache_path: Path = Path(__file__).resolve().parent / ".unavailable_tickers.json"
    # ticker -> {"misses": int, "ts": float}  (ts = kapan terakhir kosong)
    _unavailable: Dict[str, Dict[str, float]] = {}
    _cache_loaded: bool = False

    def _format_ticker(self, symbol: str) -> str:
        """Format ticker for Yahoo Finance IDX (adds .JK if missing, unless index)."""
        symbol = symbol.upper().strip()
        if symbol.startswith("^"):
            return symbol
        if not symbol.endswith(".JK"):
            symbol = f"{symbol}.JK"
        return symbol

    # ------------------------------------------------------------------
    # Cache simbol tak tersedia
    # ------------------------------------------------------------------
    @classmethod
    def _load_cache(cls) -> None:
        if cls._cache_loaded:
            return
        cls._cache_loaded = True
        try:
            if cls._cache_path.exists():
                raw = json.loads(cls._cache_path.read_text(encoding="utf-8"))
                now = time.time()
                loaded: Dict[str, Dict[str, float]] = {}
                for ticker, entry in raw.items():
                    if not isinstance(entry, dict):
                        continue
                    ts = entry.get("ts")
                    if isinstance(ts, (int, float)) and now - ts < _UNAVAILABLE_TTL_SECONDS:
                        loaded[ticker] = {
                            "misses": float(entry.get("misses", _UNAVAILABLE_CONFIRMATIONS)),
                            "ts": float(ts),
                        }
                cls._unavailable = loaded
        except Exception as exc:  # cache rusak jangan sampai mematikan bot
            logger.warning("Could not load yfinance unavailable-ticker cache: %s", exc)
            cls._unavailable = {}

    @classmethod
    def _save_cache(cls) -> None:
        try:
            cls._cache_path.write_text(
                json.dumps(cls._unavailable), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning("Could not save yfinance unavailable-ticker cache: %s", exc)

    @classmethod
    def _is_unavailable(cls, ticker_str: str) -> bool:
        """True hanya kalau simbol sudah terkonfirmasi mati berkali-kali."""
        cls._load_cache()
        entry = cls._unavailable.get(ticker_str)
        if entry is None:
            return False
        ts = entry.get("ts", 0.0)
        if time.time() - ts >= _UNAVAILABLE_TTL_SECONDS:
            # Kedaluwarsa: buang supaya dicoba lagi.
            cls._unavailable.pop(ticker_str, None)
            cls._save_cache()
            return False
        return entry.get("misses", 0) >= _UNAVAILABLE_CONFIRMATIONS

    @classmethod
    def _mark_unavailable(cls, ticker_str: str) -> None:
        """Catat satu hasil kosong; baru 'terkunci' setelah beberapa kali."""
        cls._load_cache()
        entry = cls._unavailable.get(ticker_str)
        misses = (entry.get("misses", 0) if entry else 0) + 1
        cls._unavailable[ticker_str] = {"misses": misses, "ts": time.time()}
        cls._save_cache()

    @classmethod
    def _mark_available(cls, ticker_str: str) -> None:
        """Data ada -> hapus jejak kosong sebelumnya (reset hitungan)."""
        cls._load_cache()
        if ticker_str in cls._unavailable:
            cls._unavailable.pop(ticker_str, None)
            cls._save_cache()

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------
    async def get_historical_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1d",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None
    ) -> pd.DataFrame:
        ticker_str = self._format_ticker(symbol)

        # Simbol yang sudah terbukti tak ada di Yahoo: jangan panggil jaringan
        # lagi (buang ~1,6s + 1 log ERROR per simbol per scan).
        if self._is_unavailable(ticker_str):
            return pd.DataFrame()

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

        df = await loop.run_in_executor(None, fetch)

        # Hasil kosong = kandidat simbol mati. Jangan langsung "kunci": catat
        # sebagai satu miss dan baru dianggap unavailable setelah beberapa kali
        # (Yahoo kadang transient-empty untuk simbol valid). Kalau ada data,
        # hapus jejak miss sebelumnya.
        if df.empty:
            self._mark_unavailable(ticker_str)
        else:
            self._mark_available(ticker_str)

        return df

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
