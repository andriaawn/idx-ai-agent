import re
from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from src.agents.orchestrator import AgentOrchestrator
from src.agents.tools import QuantAgentTools

router = Router()
orchestrator = AgentOrchestrator()
tools = QuantAgentTools()

@router.message(CommandStart())
async def handle_start(message: types.Message):
    welcome_text = (
        "🤖 *IDX AI Agent — Quantitative Equity Research Assistant*\n\n"
        "Selamat datang! Saya adalah asisten riset kuantitatif independen untuk Bursa Efek Indonesia (IDX).\n\n"
        "📌 *Perintah Utama:*\n"
        "• `/signal BBCA` - Sinyal trading cepat (Entry, Stop Loss, Target, R:R)\n"
        "• `/analyze BBCA` - Laporan riset ekuitas lengkap 22 poin\n"
        "• `/scan` - Pemindaian pasar mencari saham momentum & breakout terbaik\n"
        "• `/market` - Status pasar IHSG (Regime & Volatilitas)\n"
        "• `/backtest BBCA` - Simulasi performa sinyal historis\n"
        "• `/help` - Panduan penggunaan\n\n"
        "💡 *Pertanyaan Natural:* Anda juga bisa langsung mengetik pesan seperti:\n"
        "_'analisa BBCA'_, _'bagaimana kondisi pasar?'_, _'sinyal TLKM'_\n"
    )
    await message.answer(welcome_text, parse_mode="Markdown")

@router.message(Command("help"))
async def handle_help(message: types.Message):
    help_text = (
        "📖 *Panduan Penggunaan Bot:*\n\n"
        "1. `/signal [TICKER]` : Mendapatkan rekomendasi BUY/WATCHLIST/NO TRADE beserta kalkulasi risk management.\n"
        "2. `/analyze [TICKER]` : Membuat laporan analisis teknikal komprehensif.\n"
        "3. `/scan` : Pemindaian otomatis seluruh universe IDX untuk rekomendasi teratas.\n"
        "4. `/backtest [TICKER]` : Melakukan uji historis strategi pada saham tertentu.\n"
        "5. `/market` : Cek kondisi rezim IHSG terkini.\n"
    )
    await message.answer(help_text, parse_mode="Markdown")

@router.message(Command("market"))
async def handle_market(message: types.Message):
    await message.answer("🔄 Menganalisis kondisi pasar IHSG...")
    res = await tools.get_market_status()
    text = (
        f"📊 *STATUS REZIM PASAR IHSG*\n\n"
        f"• *Regime:* `{res.get('regime', 'UNKNOWN')}`\n"
        f"• *Confidence:* {res.get('confidence', 0)*100:.0f}%\n"
        f"• *IHSG Close:* {res.get('ihsg_close', 0):,.2f}\n"
        f"• *RSI (14):* {res.get('rsi', 0):.2f}\n"
        f"• *ATR Volatility:* {res.get('atr_pct', 0):.2f}%\n"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("signal"))
async def handle_signal(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Gunakan format: `/signal [TICKER]` (Contoh: `/signal BBCA`)", parse_mode="Markdown")
        return

    ticker = args[1].upper()
    await message.answer(f"⏳ Mengalkulasi sinyal kuantitatif untuk *{ticker}*...", parse_mode="Markdown")
    response = await orchestrator.process_ticker_analysis(ticker, detailed=False)
    await message.answer(response)

@router.message(Command("analyze"))
async def handle_analyze(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Gunakan format: `/analyze [TICKER]` (Contoh: `/analyze BBCA`)", parse_mode="Markdown")
        return

    ticker = args[1].upper()
    await message.answer(f"🔍 Menyusun laporan riset ekuitas lengkap untuk *{ticker}*...", parse_mode="Markdown")
    response = await orchestrator.process_ticker_analysis(ticker, detailed=True)
    await message.answer(response, parse_mode="Markdown")

@router.message(Command("backtest"))
async def handle_backtest(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Gunakan format: `/backtest [TICKER]` (Contoh: `/backtest BBCA`)", parse_mode="Markdown")
        return

    ticker = args[1].upper()
    await message.answer(f"🧪 Melakukan pengujian historis (backtest) untuk *{ticker}*...", parse_mode="Markdown")
    res = await tools.run_stock_backtest(ticker)

    if res.get("status") != "SUCCESS":
        await message.answer(f"❌ Gagal melakukan backtest: {res.get('reason')}")
        return

    text = (
        f"🧪 *HASIL BACKTEST STRATEGI: {ticker}*\n\n"
        f"• *Total Perdagangan:* {res['total_trades']}\n"
        f"• *Win Rate:* {res['win_rate']}%\n"
        f"• *Profit Factor:* {res['profit_factor']}\n"
        f"• *Average R (Expectancy):* {res['average_r']} R\n"
        f"• *Total Return:* {res['total_return_pct']}%\n"
        f"• *Max Drawdown:* {res['max_drawdown_pct']}%\n"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("scan"))
async def handle_scan(message: types.Message):
    await message.answer("🔎 Memindai universe IDX untuk saham momentum terbaik...")
    top_tickers = ["BBCA", "BBRI", "BMRI", "TLKM", "ASII"]
    results = []

    for t in top_tickers:
        res = await tools.analyze_stock(t)
        if res.get("status") == "SUCCESS":
            score = res["score_breakdown"]
            if score.signal_type in ["BUY", "STRONG_BUY", "WATCHLIST"]:
                results.append((t, score.signal_type, score.total_score, res["setup"].setup_type.value))

    if not results:
        await message.answer("ℹ️ *NO TRADE* — Tidak ditemukan setup yang memenuhi standar konfluensi saat ini.", parse_mode="Markdown")
        return

    summary = "🔥 *HASIL SCANNING PASAR IDX TERATAS:*\n\n"
    for r in results:
        icon = "🟢" if "BUY" in r[1] else "🟡"
        summary += f"{icon} *{r[0]}* — `{r[1]}` (Skor: {r[2]}/100)\n   Setup: {r[3]}\n\n"

    summary += "Ketik `/signal [TICKER]` untuk detail sinyal."
    await message.answer(summary, parse_mode="Markdown")

@router.message()
async def handle_natural_language(message: types.Message):
    text = message.text.upper()
    match = re.search(r'\b[A-Z]{4}\b', text)
    
    if "MARKET" in text or "IHSG" in text or "PASAR" in text:
        await handle_market(message)
    elif "ANALISA" in text and match:
        message.text = f"/analyze {match.group(0)}"
        await handle_analyze(message)
    elif match:
        message.text = f"/signal {match.group(0)}"
        await handle_signal(message)
    else:
        await message.answer("🤖 Ketik `/help` untuk melihat daftar perintah yang tersedia.")
