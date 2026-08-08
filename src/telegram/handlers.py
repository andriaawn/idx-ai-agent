import re
from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from src.agents.orchestrator import AgentOrchestrator
from src.agents.tools import QuantAgentTools
from src.data.universe import IDXUniverseRefresher

router = Router()
orchestrator = AgentOrchestrator()
tools = QuantAgentTools()

@router.message(CommandStart())
async def handle_start(message: types.Message):
    welcome_text = (
        "🤖 <b>IDX AI Agent — Quantitative Equity Research Assistant</b>\n\n"
        "Selamat datang! Saya adalah asisten riset kuantitatif independen untuk Bursa Efek Indonesia (IDX).\n\n"
        "📌 <b>Perintah Utama:</b>\n"
        "• <code>/signal BBCA</code> - Sinyal trading cepat (Entry, Stop Loss, Target, R:R)\n"
        "• <code>/analyze BBCA</code> - Laporan riset ekuitas lengkap 22 poin\n"
        "• <code>/scan</code> - Pemindaian pasar mencari saham momentum &amp; breakout terbaik\n"
        "• <code>/market</code> - Status pasar IHSG (Regime &amp; Volatilitas)\n"
        "• <code>/backtest BBCA</code> - Simulasi performa sinyal historis\n"
        "• <code>/help</code> - Panduan penggunaan\n\n"
        "💡 <b>Pertanyaan Natural:</b> Anda juga bisa langsung mengetik pesan seperti:\n"
        "<i>'analisa BBCA'</i>, <i>'bagaimana kondisi pasar?'</i>, <i>'sinyal TLKM'</i>\n"
    )
    await message.answer(welcome_text, parse_mode="HTML")

@router.message(Command("help"))
async def handle_help(message: types.Message):
    help_text = (
        "📖 <b>Panduan Penggunaan Bot:</b>\n\n"
        "1. <code>/signal [TICKER]</code> : Mendapatkan rekomendasi BUY/WATCHLIST/NO TRADE beserta kalkulasi risk management.\n"
        "2. <code>/analyze [TICKER]</code> : Membuat laporan analisis teknikal komprehensif.\n"
        "3. <code>/scan</code> : Pemindaian otomatis seluruh universe IDX untuk rekomendasi teratas.\n"
        "4. <code>/backtest [TICKER]</code> : Melakukan uji historis strategi pada saham tertentu.\n"
        "5. <code>/market</code> : Cek kondisi rezim IHSG terkini.\n"
    )
    await message.answer(help_text, parse_mode="HTML")

@router.message(Command("market"))
async def handle_market(message: types.Message):
    await message.answer("🔄 Menganalisis kondisi pasar IHSG...")
    res = await tools.get_market_status()
    text = (
        f"📊 <b>STATUS REZIM PASAR IHSG</b>\n\n"
        f"• <b>Regime:</b> <code>{res.get('regime', 'UNKNOWN')}</code>\n"
        f"• <b>Confidence:</b> {res.get('confidence', 0)*100:.0f}%\n"
        f"• <b>IHSG Close:</b> {res.get('ihsg_close', 0):,.2f}\n"
        f"• <b>RSI (14):</b> {res.get('rsi', 0):.2f}\n"
        f"• <b>ATR Volatility:</b> {res.get('atr_pct', 0):.2f}%\n"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("signal"))
async def handle_signal(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Gunakan format: <code>/signal [TICKER]</code> (Contoh: <code>/signal BBCA</code>)", parse_mode="HTML")
        return

    ticker = args[1].upper()
    await message.answer(f"⏳ Mengalkulasi sinyal kuantitatif untuk <b>{ticker}</b>...", parse_mode="HTML")
    response = await orchestrator.process_ticker_analysis(ticker, detailed=False)
    await message.answer(response)

@router.message(Command("analyze"))
async def handle_analyze(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Gunakan format: <code>/analyze [TICKER]</code> (Contoh: <code>/analyze BBCA</code>)", parse_mode="HTML")
        return

    ticker = args[1].upper()
    await message.answer(f"🔍 Menyusun laporan riset ekuitas lengkap untuk <b>{ticker}</b>...", parse_mode="HTML")
    response = await orchestrator.process_ticker_analysis(ticker, detailed=True)
    await message.answer(response)

@router.message(Command("backtest"))
async def handle_backtest(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Gunakan format: <code>/backtest [TICKER]</code> (Contoh: <code>/backtest BBCA</code>)", parse_mode="HTML")
        return

    ticker = args[1].upper()
    await message.answer(f"🧪 Melakukan pengujian historis (backtest) untuk <b>{ticker}</b>...", parse_mode="HTML")
    res = await tools.run_stock_backtest(ticker)

    if res.get("status") != "SUCCESS":
        await message.answer(f"❌ Gagal melakukan backtest: {res.get('reason')}")
        return

    text = (
        f"🧪 <b>HASIL BACKTEST STRATEGI: {ticker}</b>\n\n"
        f"• <b>Total Perdagangan:</b> {res['total_trades']}\n"
        f"• <b>Win Rate:</b> {res['win_rate']}%\n"
        f"• <b>Profit Factor:</b> {res['profit_factor']}\n"
        f"• <b>Average R (Expectancy):</b> {res['average_r']} R\n"
        f"• <b>Total Return:</b> {res['total_return_pct']}%\n"
        f"• <b>Max Drawdown:</b> {res['max_drawdown_pct']}%\n"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("scan"))
async def handle_scan(message: types.Message):
    stocks = await IDXUniverseRefresher.fetch_idx_stocks()
    total_universe = len(stocks)
    await message.answer(f"🔎 Memindai universe pasar IDX (<b>{total_universe} Saham</b>)...", parse_mode="HTML")
    results = await tools.scan_universe()

    if not results:
        await message.answer("ℹ️ <b>NO TRADE</b> — Tidak ditemukan setup yang memenuhi standar konfluensi saat ini.", parse_mode="HTML")
        return

    summary = f"🔥 <b>HASIL SCANNING PASAR IDX TERATAS ({len(results)} Ditemukan dari {total_universe} Saham):</b>\n\n"
    for res in results[:10]:
        t = res["ticker"]
        score = res["score_breakdown"]
        setup = res["setup"]
        icon = "🟢" if "BUY" in score.signal_type else "🟡"
        setup_display = setup.setup_type.value.replace("_", " ")
        summary += f"{icon} <b>{t}</b> — <code>{score.signal_type}</code> (Skor: {score.total_score}/100)\n   Setup: {setup_display}\n\n"

    summary += "Ketik <code>/signal [TICKER]</code> untuk detail sinyal."
    await message.answer(summary, parse_mode="HTML")

@router.message()
async def handle_natural_language(message: types.Message):
    text = message.text.upper()
    match = re.search(r'\b[A-Z]{4}\b', text)

    if "MARKET" in text or "IHSG" in text or "PASAR" in text:
        await handle_market(message)
    elif ("ANALISA" in text or "ANALYZE" in text or "LAPORAN" in text) and match:
        ticker = match.group(0)
        await message.answer(f"🔍 Menyusun laporan riset ekuitas lengkap untuk <b>{ticker}</b>...", parse_mode="HTML")
        response = await orchestrator.process_ticker_analysis(ticker, detailed=True)
        await message.answer(response)
    elif ("SINYAL" in text or "SIGNAL" in text or "ANALISA" in text) and match:
        ticker = match.group(0)
        await message.answer(f"⏳ Mengalkulasi sinyal kuantitatif untuk <b>{ticker}</b>...", parse_mode="HTML")
        response = await orchestrator.process_ticker_analysis(ticker, detailed=False)
        await message.answer(response)
    elif match:
        ticker = match.group(0)
        await message.answer(f"⏳ Mengalkulasi sinyal kuantitatif untuk <b>{ticker}</b>...", parse_mode="HTML")
        response = await orchestrator.process_ticker_analysis(ticker, detailed=False)
        await message.answer(response)
    else:
        await message.answer("🤖 Ketik <code>/help</code> untuk melihat daftar perintah yang tersedia.", parse_mode="HTML")
