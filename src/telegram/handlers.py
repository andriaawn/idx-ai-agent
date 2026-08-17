import logging

from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from src.agents.tools import QuantAgentTools
from src.agents.llm_agent import LLMAgentService
from src.agents.reporter import ResearchReportGenerator
from src.charting.renderer import ChartRenderer
from src.data.universe import IDXUniverseRefresher
from src.data.ticker_resolver import TickerResolver
from src.config.settings import settings
from src.telegram.messages import send_markdown_message, send_message_chunks, send_png_photo

router = Router()
tools = QuantAgentTools()
llm_agent = LLMAgentService(tools=tools)

logger = logging.getLogger("telegram.bot")


@router.message.outer_middleware()
async def log_incoming_messages(handler, event: types.Message, data: dict):
    user = event.from_user
    username_str = f"@{user.username}" if user and user.username else "no_username"
    user_id = user.id if user else "unknown"
    text = event.text or event.caption or "<non-text message>"
    logger.info(f"Incoming command from User ID: {user_id} ({username_str}) -> Text: {text}")
    return await handler(event, data)


async def _send_chart_if_available(message: types.Message, analysis: dict) -> None:
    """Best-effort chart delivery that never prevents the text response."""
    chart_data = analysis.get("chart_data")
    if chart_data is None:
        return
    try:
        chart_bytes = ChartRenderer.render(chart_data)
        await send_png_photo(message, chart_bytes, filename="analysis-chart.png")
    except Exception:
        logging.exception("Chart delivery failed; continuing with analytical text")


async def _deliver_ticker_analysis(message: types.Message, ticker: str, detailed: bool) -> None:
    """Deliver the existing deterministic analysis, with an optional chart first."""
    analysis = await tools.analyze_stock(ticker)
    if analysis.get("status") != "SUCCESS":
        response = f"âš ï¸ Analysis failed for {ticker}: {analysis.get('reason', 'Data unavailable')}"
    else:
        await _send_chart_if_available(message, analysis)
        if detailed:
            response = ResearchReportGenerator.generate_full_research_report(analysis)
        else:
            response = ResearchReportGenerator.generate_short_signal_alert(
                ticker=ticker,
                score=analysis["score_breakdown"],
                setup=analysis["setup"],
                risk=analysis["risk_plan"],
            )
    if detailed:
        await send_markdown_message(message, response)
    else:
        await send_message_chunks(message, response)

@router.message(CommandStart())
async def handle_start(message: types.Message):
    welcome_text = (
        "🤖 <b>IDX AI Agent</b>\n"
        "<i>Asisten riset kuantitatif saham IDX — bukan rekomendasi investasi.</i>\n\n"

        "<b>🔎 Temukan Peluang</b>\n"
        "• <code>/scan</code> — Scan seluruh IDX, tampilkan 10 kandidat terbaik\n"
        "• <code>/candidates</code> — Lihat semua kandidat (lanjut: <code>/candidates 2</code>)\n"
        "• <code>/volume_spike</code> — Radar saham dengan lonjakan volume hari ini\n"
        "• <code>/market</code> — Status & rezim pasar IHSG saat ini\n\n"

        "<b>📊 Analisis Saham</b>\n"
        "• <code>/signal BBCA</code> — Sinyal, chart, entry, SL & target\n"
        "• <code>/analyze BBCA</code> — Laporan riset lengkap\n"
        "• <code>/backtest BBCA</code> — Simulasi historis strategi\n\n"

        "<b>📌 Monitoring Pribadi</b>\n"
        "• <code>/follow BBCA</code> — Pantau kandidat & terima alert otomatis\n"
        "• <code>/follow list</code> — Lihat daftar saham yang dipantau\n"
        "• <code>/unfollow BBCA</code> — Berhenti memantau\n\n"

        "Ketik <code>/help</code> untuk panduan lengkap & detail setiap command."
    )
    await message.answer(welcome_text, parse_mode="HTML")

@router.message(Command("help"))
async def handle_help(message: types.Message):
    help_text = (
        "📖 <b>PANDUAN LENGKAP IDX AI AGENT</b>\n\n"

        "<b>🔎 Temukan Peluang</b>\n"
        "• <code>/scan</code>\n"
        "  Scan seluruh universe IDX, tampilkan 10 saham dengan setup terkuat.\n"
        "• <code>/candidates</code> atau <code>/candidates 2</code>\n"
        "  Lihat semua kandidat dari scan terakhir secara bertahap (10 per halaman).\n"
        "• <code>/volume_spike</code>\n"
        "  Radar saham dengan lonjakan volume signifikan & konfirmasi harga hari ini.\n"
        "• <code>/market</code>\n"
        "  Cek kondisi & rezim pasar IHSG (Bullish/Sideways/Bearish, RSI, ATR).\n\n"

        "<b>📊 Analisis Ticker</b>\n"
        "• <code>/signal BBCA</code>\n"
        "  Ringkasan setup, chart teknikal, harga entry, stop-loss, dan target profit.\n"
        "• <code>/analyze BBCA</code>\n"
        "  Laporan riset ekuitas lengkap: skor konfluensi, indikator, level kunci.\n"
        "• <code>/backtest BBCA</code>\n"
        "  Simulasi historis strategi: win rate, profit factor, max drawdown, dll.\n\n"

        "<b>📌 Monitoring & Akun</b>\n"
        "• <code>/follow BBCA</code> — Tambahkan kandidat dari scan ke daftar pantau.\n"
        "• <code>/follow list</code> — Lihat semua saham yang sedang dipantau.\n"
        "• <code>/unfollow BBCA</code> — Hapus saham dari daftar pantau.\n"
        "• <code>/alerts entry on/off</code> — Aktifkan/nonaktifkan alert entry.\n"
        "  Jenis alert: <code>entry</code>, <code>breakout</code>, <code>target</code>.\n"
        "  ⚠️ Alert stop-loss selalu aktif dan tidak dapat dinonaktifkan.\n"
        "• <code>/account</code> — Lihat paket, jumlah saham dipantau, dan sisa masa aktif.\n"
        "• <code>/donate</code> — Informasi upgrade ke <b>PREMIUM</b> (30 Hari).\n\n"

        "<b>💬 Cara Cepat (tanpa command)</b>\n"
        "Anda juga bisa mengetik langsung, misalnya:\n"
        "• <i>analisa BBCA</i> — laporan lengkap\n"
        "• <i>sinyal TLKM</i> — sinyal trading\n"
        "• <i>BBCA</i> — sinyal default untuk ticker tersebut\n"
        "• <i>kondisi pasar</i> atau <i>IHSG</i> — status pasar\n\n"

        "ℹ️ <i>Informasi ini bersifat edukatif, bukan rekomendasi investasi.</i>"
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
    await send_message_chunks(message, text, parse_mode="HTML")

@router.message(Command("signal"))
async def handle_signal(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Gunakan format: <code>/signal [TICKER]</code> (Contoh: <code>/signal BBCA</code>)", parse_mode="HTML")
        return

    ticker = args[1].upper()
    await message.answer(f"⏳ Mengalkulasi sinyal kuantitatif untuk <b>{ticker}</b>...", parse_mode="HTML")
    await _deliver_ticker_analysis(message, ticker, detailed=False)

@router.message(Command("analyze"))
async def handle_analyze(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Gunakan format: <code>/analyze [TICKER]</code> (Contoh: <code>/analyze BBCA</code>)", parse_mode="HTML")
        return

    ticker = args[1].upper()
    await message.answer(f"🔍 Menyusun laporan riset ekuitas lengkap untuk <b>{ticker}</b>...", parse_mode="HTML")
    await _deliver_ticker_analysis(message, ticker, detailed=True)

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
    await send_message_chunks(message, text, parse_mode="HTML")

@router.message(Command("scan"))
async def handle_scan(message: types.Message):
    user_id, _ = _telegram_identity(message)
    tier, _ = await tools.get_user_tier(user_id)
    stocks = await IDXUniverseRefresher.fetch_idx_stocks()
    total_universe = len(stocks)
    await message.answer(f"🔎 Memindai universe pasar IDX (<b>{total_universe} Saham</b>)...", parse_mode="HTML")
    results = await tools.scan_universe(tickers=[stock["ticker"] for stock in stocks])

    if not results:
        await message.answer("ℹ️ <b>NO TRADE</b> — Tidak ditemukan setup yang memenuhi standar konfluensi saat ini.", parse_mode="HTML")
        return

    display_limit = 5 if tier == "FREE" else 10
    display_results = results[:display_limit]

    summary = f"🔥 <b>HASIL SCANNING PASAR IDX TERATAS ({len(results)} Ditemukan dari {total_universe} Saham):</b>\n\n"
    for res in display_results:
        t = res["ticker"]
        if t.endswith(".JK"):
            t = t[:-3]
        score = res["score_breakdown"]
        setup = res["setup"]
        icon = "🟢" if "BUY" in score.signal_type else "🟡"
        setup_display = setup.setup_type.value.replace("_", " ")
        summary += f"{icon} <b>{t}</b> — <code>{score.signal_type}</code> (Skor: {score.total_score}/100)\n   Setup: {setup_display}\n\n"

    if tier == "FREE" and len(results) > display_limit:
        summary += (
            f"🔒 <i>Menampilkan Top 5 (Paket FREE). {len(results) - display_limit} peluang lainnya tersedia untuk donatur.</i>\n"
            "Ketik <code>/donate</code> untuk upgrade ke <b>PREMIUM</b>.\n\n"
        )
    else:
        summary += "Lihat seluruh kandidat: <code>/candidates</code>\n\n"

    summary += "Ketik <code>/signal [TICKER]</code> untuk detail sinyal."
    await send_message_chunks(message, summary, parse_mode="HTML")

@router.message(Command("candidates"))
async def handle_candidates(message: types.Message):
    """Show a page from the latest persisted market scan without rescanning."""
    user_id, _ = _telegram_identity(message)
    tier, _ = await tools.get_user_tier(user_id)
    args = message.text.split()
    page = 1
    if len(args) >= 3 and args[1].lower() == "page":
        try:
            page = max(1, int(args[2]))
        except ValueError:
            await message.answer("⚠️ Gunakan format: <code>/candidates page 2</code>", parse_mode="HTML")
            return
    elif len(args) >= 2:
        try:
            page = max(1, int(args[1]))
        except ValueError:
            await message.answer("⚠️ Gunakan format: <code>/candidates</code> atau <code>/candidates page 2</code>", parse_mode="HTML")
            return

    if tier == "FREE" and page > 1:
        await message.answer(
            "🔒 <b>Fitur Khusus Donatur (PREMIUM)</b>\n\n"
            "Akses kandidat halaman 2 dan seterusnya khusus untuk pengguna yang berdonasi (mulai Rp 10.000 / 30 hari).\n\n"
            "Ketik <code>/donate</code> untuk informasi upgrade.",
            parse_mode="HTML"
        )
        return

    page_size = 10
    run, candidates = await tools.get_latest_scan_candidates(
        offset=(page - 1) * page_size, limit=page_size
    )
    if run is None:
        await message.answer("ℹ️ Belum ada snapshot scan. Jalankan <code>/scan</code> terlebih dahulu.", parse_mode="HTML")
        return
    if not candidates:
        await message.answer(
            f"ℹ️ Tidak ada kandidat pada halaman {page}. Gunakan <code>/candidates</code> untuk kembali ke halaman pertama.",
            parse_mode="HTML",
        )
        return

    if tier == "FREE":
        candidates = candidates[:5]

    created_at = run.created_at.strftime("%d %b %Y %H:%M UTC")
    lines = [
        f"📋 <b>KANDIDAT SCAN — HALAMAN {page}</b>",
        f"Snapshot: {created_at} | {run.candidate_count} kandidat dari {run.total_scanned} saham\n",
    ]
    for index, candidate in enumerate(candidates, start=(page - 1) * page_size + 1):
        levels = []
        if candidate.entry_price is not None:
            levels.append(f"Entry {candidate.entry_price:,.0f}")
        if candidate.stop_loss is not None:
            levels.append(f"SL {candidate.stop_loss:,.0f}")
        if candidate.target_1 is not None:
            levels.append(f"TP {candidate.target_1:,.0f}")
        level_text = f"\n   {' | '.join(levels)}" if levels else ""
        lines.append(
            f"{index}. <b>{candidate.ticker}</b> — <code>{candidate.signal_type}</code> "
            f"(Skor {candidate.score:.0f})\n   {candidate.setup_name.replace('_', ' ')}{level_text}"
        )
    if tier == "PREMIUM" and page * page_size < run.candidate_count:
        lines.append(f"\nHalaman berikutnya: <code>/candidates page {page + 1}</code>")
    elif tier == "FREE" and run.candidate_count > 5:
        lines.append("\n🔒 <i>Upgrade ke PREMIUM untuk melihat seluruh halaman & kandidat: <code>/donate</code></i>")
    await send_message_chunks(message, "\n\n".join(lines), parse_mode="HTML")


@router.message(Command("volume_spike"))
async def handle_volume_spike(message: types.Message):
    user_id, _ = _telegram_identity(message)
    tier, _ = await tools.get_user_tier(user_id)
    stocks = await IDXUniverseRefresher.fetch_idx_stocks()
    await message.answer(
        f"📈 Memindai lonjakan volume berkualitas pada {len(stocks)} saham IDX...",
        parse_mode="HTML",
    )
    results = await tools.scan_volume_spikes(tickers=[stock["ticker"] for stock in stocks])
    if not results:
        await message.answer(
            "ℹ️ Tidak ada volume spike yang memenuhi kriteria likuiditas dan konfirmasi harga saat ini.",
            parse_mode="HTML",
        )
        return

    limit_count = 3 if tier == "FREE" else 20
    display_results = results[:limit_count]

    lines = ["📈 <b>VOLUME SPIKE — RADAR MOMENTUM</b>", "RVOL dibandingkan rata-rata volume 20 hari. Ini radar riset, bukan rekomendasi beli.\n"]
    for index, result in enumerate(display_results, start=1):
        ticker = result["ticker"][:-3] if result["ticker"].endswith(".JK") else result["ticker"]
        lines.append(
            f"{index}. <b>{ticker}</b> — <code>{result['label']}</code>\n"
            f"   RVOL {result['rvol']:.2f}x | Harga {result['price_change_pct']:+.2f}% | "
            f"Nilai {result['turnover'] / 1_000_000_000:.1f}B | {result['trend']}"
        )
    if tier == "FREE" and len(results) > limit_count:
        lines.append(
            f"\n🔒 <i>Menampilkan Top 3 (Paket FREE). Total {len(results)} radar saham terdeteksi.</i>\n"
            "Ketik <code>/donate</code> untuk membuka seluruh radar volume spike."
        )
    await send_message_chunks(message, "\n\n".join(lines), parse_mode="HTML")


def _telegram_identity(message: types.Message):
    user = message.from_user
    return user.id, user.username


@router.message(Command("follow"))
async def handle_follow(message: types.Message):
    args = message.text.split()
    user_id, username = _telegram_identity(message)
    if len(args) >= 2 and args[1].lower() == "list":
        tier, limit, followed, _ = await tools.list_followed_candidates(user_id)
        limit_text = "tanpa batas" if limit is None else str(limit)
        if not followed:
            await message.answer(f"📌 Monitoring Anda kosong. Paket <code>{tier}</code>: maksimal {limit_text} kandidat.", parse_mode="HTML")
            return
        lines = [f"📌 <b>MONITORING ANDA</b> — <code>{tier}</code> ({len(followed)}/{limit_text})"]
        for item in followed:
            levels = f"Entry {item.entry_price:,.0f} | SL {item.stop_loss:,.0f} | TP {item.target_1:,.0f}" if item.entry_price is not None and item.stop_loss is not None and item.target_1 is not None else "Level tidak tersedia"
            lines.append(f"• <b>{item.ticker}</b> — {item.signal_type}, skor {item.score:.0f}\n  {item.setup_name.replace('_', ' ')} | {levels}")
        await send_message_chunks(message, "\n\n".join(lines), parse_mode="HTML")
        return
    if len(args) < 2:
        await message.answer("⚠️ Gunakan <code>/follow BBCA</code> atau <code>/follow list</code>.", parse_mode="HTML")
        return
    result = await tools.follow_latest_candidate(user_id, username, args[1])
    if result.status == "FOLLOWED":
        limit_text = "tanpa batas" if result.limit is None else str(result.limit)
        await message.answer(f"✅ Kandidat <b>{args[1].upper()}</b> ditambahkan ke monitoring Anda ({result.followed_count}/{limit_text}).", parse_mode="HTML")
    elif result.status == "LIMIT_REACHED":
        await message.answer("🔒 Batas akun gratis (2 kandidat) tercapai. Upgrade ke <b>PREMIUM</b> (<code>/donate</code>) untuk memantau tanpa batas.", parse_mode="HTML")
    elif result.status == "NOT_A_CANDIDATE":
        await message.answer("ℹ️ Ticker tersebut tidak ada di kandidat scan terbaru. Lihat <code>/candidates</code>.", parse_mode="HTML")
    elif result.status == "NO_SCAN":
        await message.answer("ℹ️ Jalankan <code>/scan</code> terlebih dahulu.", parse_mode="HTML")
    else:
        await message.answer("ℹ️ Kandidat tersebut sudah Anda ikuti.", parse_mode="HTML")


@router.message(Command("unfollow"))
async def handle_unfollow(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Gunakan <code>/unfollow BBCA</code>.", parse_mode="HTML")
        return
    user_id, _ = _telegram_identity(message)
    removed = await tools.unfollow_candidate(user_id, args[1])
    text = f"✅ <b>{args[1].upper()}</b> dihapus dari monitoring." if removed else "ℹ️ Ticker tersebut tidak ada di monitoring Anda."
    await message.answer(text, parse_mode="HTML")


@router.message(Command("account"))
async def handle_account(message: types.Message):
    user_id, _ = _telegram_identity(message)
    tier, limit, followed, expires_at = await tools.list_followed_candidates(user_id)
    limit_text = "Tanpa batas" if limit is None else str(limit)

    expiry_info = ""
    if tier == "PREMIUM":
        if expires_at:
            expiry_info = f"\n⏳ Masa Aktif: Sampai <b>{expires_at.strftime('%d %b %Y %H:%M UTC')}</b>"
        else:
            expiry_info = "\n⏳ Masa Aktif: <b>Permanen</b>"
    else:
        expiry_info = "\n💡 Upgrade ke <b>PREMIUM</b> via donasi: <code>/donate</code>"

    await message.answer(
        f"👤 <b>INFORMASI AKUN</b>\n\n"
        f"• <b>User ID:</b> <code>{user_id}</code>\n"
        f"• <b>Paket:</b> <code>{tier}</code>\n"
        f"• <b>Monitoring Kuota:</b> {len(followed)}/{limit_text}"
        f"{expiry_info}",
        parse_mode="HTML",
    )


@router.message(Command("donate"))
@router.message(Command("upgrade"))
async def handle_donate(message: types.Message):
    user_id, username = _telegram_identity(message)
    donate_text = (
        "⭐ <b>UPGRADE KE IDX AI AGENT PREMIUM</b>\n\n"
        "Dukung pengembangan bot ini dengan berdonasi minimal <b>Rp 10.000</b> dan dapatkan akses <b>PREMIUM (30 Hari)</b>:\n\n"
        "<b>Keuntungan PREMIUM:</b>\n"
        "• 📌 Pantau saham tanpa batas di <code>/follow</code> (Free: maks 2)\n"
        "• 🔎 Akses penuh seluruh kandidat <code>/scan</code> & <code>/candidates</code>\n"
        "• 📈 Radar lengkap Top 20 saham <code>/volume_spike</code>\n"
        "• 📬 Notifikasi & laporan harian portofolio pantauan\n\n"
        "<b>Cara Berdonasi & Aktivasi:</b>\n"
        f"1. Salin <b>User ID</b> Telegram Anda: <code>{user_id}</code>\n"
        "2. Hubungi Admin: @bapakeew untuk info pembayaran (QRIS / Transfer / E-Wallet)\n"
        f"3. Kirim bukti donasi beserta User ID <code>{user_id}</code> ke @bapakeew untuk aktivasi instan."
    )
    await message.answer(donate_text, parse_mode="HTML")


@router.message(Command("alerts"))
async def handle_alerts(message: types.Message):
    args = message.text.split()
    if len(args) != 3 or args[1].lower() not in {"entry", "breakout", "target"} or args[2].lower() not in {"on", "off"}:
        await message.answer("🔔 Atur alert: <code>/alerts entry on</code>, <code>/alerts breakout off</code>, atau <code>/alerts target on</code>. Stop-loss selalu aktif.", parse_mode="HTML")
        return
    user_id, _ = _telegram_identity(message)
    enabled = args[2].lower() == "on"
    await tools.update_alert_preference(user_id, args[1].lower(), enabled)
    await message.answer(f"✅ Alert <code>{args[1].upper()}</code> {'aktif' if enabled else 'nonaktif'}. Stop-loss selalu aktif.", parse_mode="HTML")


async def _set_tier(message: types.Message, tier: str) -> None:
    admin_id = str(settings.admin_id).strip()
    if not admin_id or str(message.from_user.id) != admin_id:
        await message.answer("⛔ Command ini hanya untuk admin.", parse_mode="HTML")
        return
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer(f"⚠️ Gunakan: <code>/{'grant_premium' if tier == 'PREMIUM' else 'revoke_premium'} USER_ID [DURASI_HARI]</code>", parse_mode="HTML")
        return
    target_id = int(args[1])
    days = 30
    if len(args) >= 3 and args[2].isdigit():
        days = int(args[2])

    expires_at = await tools.set_subscription_tier(target_id, tier, duration_days=days)
    if tier == "PREMIUM" and expires_at:
        await message.answer(f"✅ User <code>{target_id}</code> sekarang <code>PREMIUM</code> aktif selama {days} hari (sampai {expires_at.strftime('%d %b %Y %H:%M UTC')}).", parse_mode="HTML")
    else:
        await message.answer(f"✅ User <code>{target_id}</code> sekarang berstatus <code>{tier}</code>.", parse_mode="HTML")


@router.message(Command("grant_premium"))
async def handle_grant_premium(message: types.Message):
    await _set_tier(message, "PREMIUM")


@router.message(Command("revoke_premium"))
async def handle_revoke_premium(message: types.Message):
    await _set_tier(message, "FREE")

@router.message()
async def handle_natural_language(message: types.Message):
    text = message.text.upper()
    original_text = message.text  # preserve original casing for LLM
    tickers = await TickerResolver.resolve_text(original_text)

    # --- Fast deterministic path: ticker + command keyword ---
    if "MARKET" in text or "IHSG" in text or "PASAR" in text:
        await handle_market(message)

    elif (("ANALISA" in text or "ANALYZE" in text or "LAPORAN" in text or "DETAIL" in text) and tickers):
        ticker = tickers[0]
        await message.answer(f"🔍 Menyusun laporan riset ekuitas lengkap untuk <b>{ticker}</b>...", parse_mode="HTML")
        await _deliver_ticker_analysis(message, ticker, detailed=True)

    elif (("SINYAL" in text or "SIGNAL" in text or "BELI" in text or "ENTRY" in text) and tickers):
        ticker = tickers[0]
        await message.answer(f"⏳ Mengalkulasi sinyal kuantitatif untuk <b>{ticker}</b>...", parse_mode="HTML")
        await _deliver_ticker_analysis(message, ticker, detailed=False)

    elif tickers and len(text.split()) <= 2:
        # Short query with just a ticker — default to signal
        ticker = tickers[0]
        await message.answer(f"⏳ Mengalkulasi sinyal kuantitatif untuk <b>{ticker}</b>...", parse_mode="HTML")
        await _deliver_ticker_analysis(message, ticker, detailed=False)

    else:
        # --- Interactive AI path: open-ended, comparative, educational ---
        if llm_agent.is_enabled():
            await message.answer("🧠 <i>Menghubungi AI Research Analyst...</i>", parse_mode="HTML")

            # Enrich the AI request with every valid IDX ticker mentioned.
            quant_contexts = []
            for ticker in tickers:
                try:
                    res = await tools.analyze_stock(ticker)
                    if res.get("status") == "SUCCESS":
                        snap = res["snapshot"]
                        score = res["score_breakdown"]
                        setup = res["setup"]
                        quant_contexts.append(
                            f"Ticker: {ticker}\n"
                            f"Harga Terakhir: {snap.close:,.0f} IDR\n"
                            f"Tren: {snap.trend_alignment}, RSI-14: {snap.rsi_14:.1f}, ROC-10: {snap.roc_10:.2f}%\n"
                            f"RVOL: {snap.rvol:.2f}x, EMA20: {snap.ema_20:,.0f}, EMA50: {snap.ema_50:,.0f}\n"
                            f"Setup Terdeteksi: {setup.setup_type.value}, Skor: {score.total_score}/100, Sinyal: {score.signal_type}\n"
                            f"Support: {snap.support_levels}, Resistance: {snap.resistance_levels}"
                        )
                except Exception:
                    pass

            ai_response = await llm_agent.generate_response(
                original_text,
                "\n\n".join(quant_contexts) if quant_contexts else None,
            )
            if ai_response:
                await send_markdown_message(message, ai_response)
            else:
                await message.answer("🤖 Ketik <code>/help</code> untuk melihat daftar perintah yang tersedia.", parse_mode="HTML")
        else:
            await message.answer(
                "🤖 Perintah tidak dikenali.\n\n"
                "Coba gunakan salah satu perintah berikut:\n"
                "• <code>/signal BBCA</code> — Sinyal trading\n"
                "• <code>/analyze BBCA</code> — Laporan lengkap\n"
                "• <code>/scan</code> — Scan pasar IDX\n"
                "• <code>/market</code> — Status IHSG\n"
                "• <code>/help</code> — Panduan lengkap",
                parse_mode="HTML"
            )
