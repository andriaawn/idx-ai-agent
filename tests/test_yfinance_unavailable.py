"""Test: simbol yfinance yang tak tersedia di-cache supaya tidak diulang tiap scan.

Masalah nyata (2026-10-03): scan harian mengiterasi ~964 ticker; ~111 di antaranya
sudah tak ada di Yahoo (delisted) sehingga tiap scan memanggil yfinance, memakan
~1,6s/ticker dan menulis 1 log ERROR. Selama 3 hari: 687 error, berulang tiap hari
karena tidak ada cache.

Jebakan penting (terukur): Yahoo kadang mengembalikan kosong secara TRANSIENT
(rate-limit/crumb) untuk simbol yang valid — BBRI (blue chip) sempat kosong di
bawah concurrency tinggi padahal 245 baris saat diisolasi. Jadi satu hasil kosong
TIDAK boleh langsung mengunci simbol. Simbol baru ditandai setelah beberapa kali
kosong berturut-turut, dan hitungan di-reset begitu ada data.

Aturan yang dikunci:
- Simbol terkonfirmasi mati (beberapa kali kosong) TIDAK memanggil yfinance lagi.
- Satu hasil kosong saja BELUM mengunci simbol.
- Simbol valid tetap di-fetch normal dan tidak pernah dicache.
- Entri cache punya TTL; kedaluwarsa -> fetch ulang.
"""

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.data.providers.yfinance_provider import (
    YFinanceProvider,
    _UNAVAILABLE_CONFIRMATIONS,
)


def _empty_df():
    return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])


def _valid_df(length=5):
    dates = pd.date_range("2024-01-01", periods=length, freq="D")
    return pd.DataFrame(
        {
            "Open": [100.0] * length,
            "High": [110.0] * length,
            "Low": [90.0] * length,
            "Close": [105.0] * length,
            "Volume": [1000.0] * length,
        },
        index=dates,
    )


class _FakeTicker:
    """Ticker yfinance palsu; mencatat berapa kali history() dipanggil."""

    def __init__(self, df):
        self._df = df
        self.calls = 0

    def history(self, **kwargs):
        self.calls += 1
        return self._df


class TestYFinanceUnavailableCache(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        fd, self._cache_file = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(self._cache_file)
        self._orig_path = YFinanceProvider._cache_path
        YFinanceProvider._cache_path = Path(self._cache_file)
        YFinanceProvider._unavailable = {}
        YFinanceProvider._cache_loaded = True

    def tearDown(self):
        YFinanceProvider._cache_path = self._orig_path
        YFinanceProvider._unavailable = {}
        YFinanceProvider._cache_loaded = False
        if os.path.exists(self._cache_file):
            os.unlink(self._cache_file)

    async def test_single_empty_does_not_lock_ticker(self):
        """SATU hasil kosong belum cukup — simbol valid bisa transient-empty."""
        fake = _FakeTicker(_empty_df())
        with patch("src.data.providers.yfinance_provider.yf.Ticker", return_value=fake):
            provider = YFinanceProvider()
            await provider.get_historical_ohlcv("BBRI", timeframe="1d")

        self.assertFalse(
            YFinanceProvider._is_unavailable("BBRI.JK"),
            "satu hasil kosong tidak boleh langsung mengunci simbol",
        )

    async def test_repeated_empty_locks_ticker(self):
        """Kosong berkali-kali -> simbol ditandai unavailable."""
        fake = _FakeTicker(_empty_df())
        with patch("src.data.providers.yfinance_provider.yf.Ticker", return_value=fake):
            provider = YFinanceProvider()
            for _ in range(_UNAVAILABLE_CONFIRMATIONS):
                await provider.get_historical_ohlcv("WSKT", timeframe="1d")

        self.assertTrue(YFinanceProvider._is_unavailable("WSKT.JK"))

    async def test_known_unavailable_ticker_skips_yfinance(self):
        """Simbol yang sudah terkonfirmasi mati TIDAK boleh memanggil yfinance lagi."""
        YFinanceProvider._unavailable["WSKT.JK"] = {
            "misses": _UNAVAILABLE_CONFIRMATIONS,
            "ts": time.time(),
        }
        fake = _FakeTicker(_empty_df())
        with patch(
            "src.data.providers.yfinance_provider.yf.Ticker", return_value=fake
        ) as mocked:
            provider = YFinanceProvider()
            df = await provider.get_historical_ohlcv("WSKT", timeframe="1d")

        self.assertTrue(df.empty)
        self.assertEqual(fake.calls, 0, "simbol mati tidak boleh fetch ulang")
        mocked.assert_not_called()

    async def test_valid_ticker_resets_miss_counter(self):
        """Data ada -> hitungan miss direset, simbol tidak pernah terkunci."""
        YFinanceProvider._unavailable["BBRI.JK"] = {"misses": 2, "ts": time.time()}
        fake = _FakeTicker(_valid_df())
        with patch("src.data.providers.yfinance_provider.yf.Ticker", return_value=fake):
            provider = YFinanceProvider()
            df = await provider.get_historical_ohlcv("BBRI", timeframe="1d")

        self.assertFalse(df.empty)
        self.assertNotIn("BBRI.JK", YFinanceProvider._unavailable)

    async def test_valid_ticker_still_fetches(self):
        """Simbol valid tetap di-fetch normal dan TIDAK dicache sebagai mati."""
        fake = _FakeTicker(_valid_df())
        with patch("src.data.providers.yfinance_provider.yf.Ticker", return_value=fake):
            provider = YFinanceProvider()
            df = await provider.get_historical_ohlcv("BBCA", timeframe="1d")

        self.assertFalse(df.empty)
        self.assertEqual(fake.calls, 1)
        self.assertNotIn("BBCA.JK", YFinanceProvider._unavailable)

    async def test_expired_cache_is_refetched(self):
        """Entri cache yang kedaluwarsa harus di-fetch ulang (simbol relisting)."""
        YFinanceProvider._unavailable["SRIL.JK"] = {
            "misses": _UNAVAILABLE_CONFIRMATIONS,
            "ts": time.time() - (8 * 24 * 3600),
        }
        fake = _FakeTicker(_empty_df())
        with patch("src.data.providers.yfinance_provider.yf.Ticker", return_value=fake):
            provider = YFinanceProvider()
            await provider.get_historical_ohlcv("SRIL", timeframe="1d")

        self.assertGreater(fake.calls, 0, "cache kedaluwarsa harus fetch ulang")

    async def test_cache_persists_across_instances(self):
        """Cache ditulis ke file supaya bertahan setelah proses restart."""
        fake = _FakeTicker(_empty_df())
        with patch("src.data.providers.yfinance_provider.yf.Ticker", return_value=fake):
            provider = YFinanceProvider()
            for _ in range(_UNAVAILABLE_CONFIRMATIONS):
                await provider.get_historical_ohlcv("TECH", timeframe="1d")

        # Simulasi restart: lupakan state in-memory, muat ulang dari file.
        YFinanceProvider._unavailable = {}
        YFinanceProvider._cache_loaded = False
        self.assertTrue(
            YFinanceProvider._is_unavailable("TECH.JK"),
            "cache harus dimuat ulang dari file setelah restart",
        )


if __name__ == "__main__":
    unittest.main()
