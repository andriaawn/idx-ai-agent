import os
import asyncio
import urllib.request
import json
import logging
import pandas as pd
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.storage.models import Instrument

POPULAR_IDX_STOCKS = [
    {"ticker": "BBCA", "name": "Bank Central Asia Tbk."},
    {"ticker": "BBRI", "name": "Bank Rakyat Indonesia (Persero) Tbk."},
    {"ticker": "BMRI", "name": "Bank Mandiri (Persero) Tbk."},
    {"ticker": "BBNI", "name": "Bank Negara Indonesia (Persero) Tbk."},
    {"ticker": "BRIS", "name": "Bank Syariah Indonesia Tbk."},
    {"ticker": "TLKM", "name": "Telkom Indonesia (Persero) Tbk."},
    {"ticker": "ISAT", "name": "Indosat Tbk."},
    {"ticker": "EXCL", "name": "XL Axiata Tbk."},
    {"ticker": "ASII", "name": "Astra International Tbk."},
    {"ticker": "UNTR", "name": "United Tractors Tbk."},
    {"ticker": "ADRO", "name": "Adaro Energy Indonesia Tbk."},
    {"ticker": "PTBA", "name": "Bukit Asam Tbk."},
    {"ticker": "ITMG", "name": "Indo Tambangraya Megah Tbk."},
    {"ticker": "ANTM", "name": "Aneka Tambang Tbk."},
    {"ticker": "INCO", "name": "Vale Indonesia Tbk."},
    {"ticker": "MDKA", "name": "Merdeka Copper Gold Tbk."},
    {"ticker": "PGAS", "name": "Perusahaan Gas Negara Tbk."},
    {"ticker": "MEDC", "name": "Medco Energi Internasional Tbk."},
    {"ticker": "AKRA", "name": "AKR Corporindo Tbk."},
    {"ticker": "GOTO", "name": "GoTo Gojek Tokopedia Tbk."},
    {"ticker": "AMRT", "name": "Sumber Alfaria Trijaya Tbk."},
    {"ticker": "ICBP", "name": "Indofood CBP Sukses Makmur Tbk."},
    {"ticker": "INDF", "name": "Indofood Sukses Makmur Tbk."},
    {"ticker": "KLBF", "name": "Kalbe Farma Tbk."},
    {"ticker": "CPIN", "name": "Charoen Pokphand Indonesia Tbk."},
    {"ticker": "JPFA", "name": "Japfa Comfeed Indonesia Tbk."},
    {"ticker": "SMGR", "name": "Semen Indonesia (Persero) Tbk."},
    {"ticker": "INTP", "name": "Indocement Tunggal Prakarsa Tbk."},
    {"ticker": "BRPT", "name": "Barito Pacific Tbk."},
    {"ticker": "TPIA", "name": "Chandra Asri Petrochemical Tbk."},
    {"ticker": "ACES", "name": "Aspirasi Hidup Indonesia Tbk."},
    {"ticker": "ERAA", "name": "Erajaya Swasembada Tbk."},
    {"ticker": "HEAL", "name": "Medikaloka Hermina Tbk."},
    {"ticker": "MIKA", "name": "Mitra Keluarga Karyasehat Tbk."},
    {"ticker": "PGEO", "name": "Pertamina Geothermal Energy Tbk."},
    {"ticker": "NCKL", "name": "Trimegah Bangun Persada Tbk."},
    {"ticker": "MBMA", "name": "Merdeka Battery Materials Tbk."},
    {"ticker": "PTRO", "name": "Petrosea Tbk."},
    {"ticker": "ESSA", "name": "Essence Indonesia Tbk."}
]

class IDXUniverseRefresher:
    """Manages the IDX stock universe list."""

    @staticmethod
    def load_excel_stocks() -> List[Dict[str, Any]]:
        """Load stock universe from local Daftar_Saham.xlsx file if available."""
        file_candidates = [
            "Daftar_Saham.xlsx",
            os.path.join(os.getcwd(), "Daftar_Saham.xlsx"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Daftar_Saham.xlsx")
        ]
        for path in file_candidates:
            if os.path.exists(path):
                try:
                    df = pd.read_excel(path)
                    stocks = []
                    for _, row in df.iterrows():
                        ticker = str(row.get("Kode", "")).strip().upper()
                        name = str(row.get("Nama Perusahaan", "")).strip()
                        board = str(row.get("Papan Pencatatan", "Unknown")).strip()
                        if ticker and len(ticker) == 4:
                            stocks.append({
                                "ticker": ticker,
                                "name": name,
                                "sector": board
                            })
                    if stocks:
                        return stocks
                except Exception as e:
                    logging.warning(f"Could not load Excel universe file at {path}: {e}")
        return []

    @staticmethod
    async def fetch_idx_stocks() -> List[Dict[str, Any]]:
        """Fetch stock universe from local Excel, official IDX endpoint, or fallback."""
        excel_stocks = IDXUniverseRefresher.load_excel_stocks()
        if excel_stocks:
            return excel_stocks

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
