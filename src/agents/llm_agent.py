import asyncio
import logging
import re
from typing import Optional
from src.config.settings import settings
from src.agents.tools import QuantAgentTools

SYSTEM_PROMPT = """Anda adalah IDX AI Agent, Senior Equity Research Analyst & Quantitative Specialist untuk Bursa Efek Indonesia (IDX).
Tugas Anda adalah membantu investor & trader dengan analisis saham yang cerdas, obyektif, mendalam, dan berbasis data teknikal/kuantitatif.

Panduan Respons:
1. Berikan jawaban profesional, lugas, dan terstruktur dalam Bahasa Indonesia.
2. Gunakan data teknikal (EMA, RSI, RVOL, ROC, Support & Resistance) dan skor kuantitatif jika tersedia.
3. Jika pengguna membandingkan dua atau lebih saham, bandingkan aspek tren, momentum, dan manajemen risiko masing-masing.
4. Berikan wawasan mengenai potensi risiko dan ingatkan bahwa analisis kuantitatif bersifat probabilitas.
"""

MODELS = ["gemini-3.5-flash","gemini-3.1-flash-lite"]
MAX_RETRIES = 3


def _extract_retry_delay(err_str: str, default: float = 5.0) -> float:
    """Extract retryDelay seconds from API error string."""
    match = re.search(r"retryDelay['\"]:\s*['\"](\d+(?:\.\d+)?)s['\"]", err_str)
    if match:
        return min(float(match.group(1)), 90.0)  # honor retryDelay up to 90s
    return default


class LLMAgentService:
    """Service providing interactive two-way AI discussion using Google Gemini API."""

    def __init__(self, tools: Optional[QuantAgentTools] = None):
        self.tools = tools or QuantAgentTools()

    @property
    def api_key(self) -> str:
        return settings.llm_api_key

    def is_enabled(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    async def generate_response(self, user_prompt: str, context_data: Optional[str] = None) -> str:
        """Generates interactive response using Gemini LLM API with retry on rate limit."""
        if not self.is_enabled():
            return ""

        from google import genai
        client = genai.Client(api_key=self.api_key)

        prompt = f"{SYSTEM_PROMPT}\n\nPertanyaan Pengguna: {user_prompt}\n"
        if context_data:
            prompt += f"\nData Teknikal & Kuantitatif Terkait:\n{context_data}\n"

        for model in MODELS:
            for attempt in range(MAX_RETRIES):
                try:
                    response = client.models.generate_content(model=model, contents=prompt)
                    if response and response.text:
                        return response.text
                except Exception as e:
                    err_str = str(e)

                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                        retry_delay = _extract_retry_delay(err_str)
                        if attempt < MAX_RETRIES - 1:
                            logging.warning(
                                f"Gemini [{model}] rate limited (attempt {attempt+1}/{MAX_RETRIES}). "
                                f"Waiting {retry_delay:.0f}s before retry..."
                            )
                            await asyncio.sleep(retry_delay)
                            continue  # retry same model
                        else:
                            logging.warning(f"Gemini [{model}] rate limited after {MAX_RETRIES} attempts. Trying next model.")
                            break  # try next model

                    elif "404" in err_str or "NOT_FOUND" in err_str:
                        logging.warning(f"Gemini [{model}] not available: {e}")
                        break  # try next model

                    else:
                        logging.error(f"Gemini [{model}] unexpected error: {e}")
                        break  # try next model

        # All models and retries exhausted
        return (
            "⚠️ <b>AI Research Analyst tidak tersedia saat ini.</b>\n\n"
            "Kemungkinan penyebab:\n"
            "• Batas permintaan per-menit (RPM) sedang tercapai, silakan coba lagi dalam 1 menit\n"
            "• Kuota API Gemini harian telah habis\n\n"
            "💡 <b>Gunakan command langsung sementara:</b>\n"
            "• <code>/signal [TICKER]</code> — Sinyal trading instan\n"
            "• <code>/analyze [TICKER]</code> — Laporan teknikal lengkap\n"
            "• <code>/scan</code> — Scan seluruh pasar IDX"
        )
