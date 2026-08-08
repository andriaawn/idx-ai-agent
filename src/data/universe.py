import asyncio
import urllib.request
import json
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.storage.models import Instrument

POPULAR_IDX_STOCKS = [
    {"ticker": "BBCA", "name": "Bank Central Asia Tbk."},
    {"ticker": "BBRI", "name": "Bank Rakyat Indonesia (Persero) Tbk."},
    {"ticker": "BMRI", "name": "Bank Mandiri (Persero) Tbk."},
    {"ticker": "BBNI", "name": "Bank Negara Indonesia (Persero) Tbk."},
    {"ticker": "TLKM", "name": "Telkom Indonesia (Persero) Tbk."},
    {"ticker": "ASII", "name": "Astra International Tbk."},
    {"ticker": "UNTR", "name": "United Tractors Tbk."},
    {"ticker": "ADRO", "name": "Adaro Energy Indonesia Tbk."},
    {"ticker": "GOTO", "name": "GoTo Gojek Tokopedia Tbk."},
    {"ticker": "AMRT", "name": "Sumber Alfaria Trijaya Tbk."},
    {"ticker": "ICBP", "name": "Indofood CBP Sukses Makmur Tbk."},
    {"ticker": "INDF", "name": "Indofood Sukses Makmur Tbk."},
    {"ticker": "KLBF", "name": "Kalbe Farma Tbk."},
    {"ticker": "PGAS", "name": "Perusahaan Gas Negara Tbk."},
    {"ticker": "PTBA", "name": "Bukit Asam Tbk."},
]

class IDXUniverseRefresher:
    """Manages the IDX stock universe list."""

    @staticmethod
    async def fetch_idx_stocks() -> List[Dict[str, Any]]:
        """Fetch stock universe from official IDX endpoint or fallback to curated liquid list."""
        loop = asyncio.get_event_loop()

        def fetch():
            url = "https://www.idx.co.id/primary/StockData/GetSecuritiesStock?start=0&length=1000"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    records = data.get("data", [])
                    if records:
                        return [
                            {
                                "ticker": item.get("Code", "").strip(),
                                "name": item.get("Name", "").strip(),
                                "sector": item.get("Sector", "").strip() if item.get("Sector") else "Unknown"
                            }
                            for item in records if item.get("Code")
                        ]
            except Exception:
                pass
            return POPULAR_IDX_STOCKS

        return await loop.run_in_executor(None, fetch)

    @staticmethod
    async def sync_universe_to_db(db: AsyncSession) -> int:
        """Sync fetched stock list into instruments table."""
        stocks = await IDXUniverseRefresher.fetch_idx_stocks()
        synced_count = 0

        for stock in stocks:
            ticker = stock["ticker"]
            stmt = select(Instrument).where(Instrument.ticker == ticker)
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if not existing:
                inst = Instrument(
                    ticker=ticker,
                    name=stock["name"],
                    sector=stock.get("sector", "Unknown"),
                    listing_status="ACTIVE"
                )
                db.add(inst)
                synced_count += 1
            else:
                existing.name = stock["name"]
                if stock.get("sector"):
                    existing.sector = stock.get("sector")

        await db.commit()
        return synced_count
