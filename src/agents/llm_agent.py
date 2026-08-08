import logging
from typing import Optional, Dict, Any
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
        """Generates interactive response using Gemini LLM API with optional quant context."""
        if not self.is_enabled():
            return ""

        prompt = f"{SYSTEM_PROMPT}\n\nPertanyaan Pengguna: {user_prompt}\n"
        if context_data:
            prompt += f"\nData Teknikal & Kuantitatif Terkait:\n{context_data}\n"

        for model in ["gemini-2.0-flash", "gemini-2.0-flash-lite"]:
            try:
                from google import genai
                client = genai.Client(api_key=self.api_key)
                response = client.models.generate_content(model=model, contents=prompt)
                if response and response.text:
                    return response.text
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    logging.warning(f"Gemini model {model} quota exhausted: {e}")
                    # Try next model in loop
                    continue
                elif "404" in err_str or "NOT_FOUND" in err_str:
                    logging.warning(f"Gemini model {model} not available: {e}")
                    continue
                else:
                    logging.error(f"Gemini model {model} unexpected error: {e}")
                    continue

        # All models failed
        return (
            "⚠️ <b>AI Research Analyst tidak tersedia saat ini.</b>\n\n"
            "Kemungkinan penyebab:\n"
            "• Kuota API Gemini harian telah habis\n"
            "• API key belum dikonfigurasi dengan benar\n\n"
            "💡 <b>Gunakan command langsung:</b>\n"
            "• <code>/signal [TICKER]</code> — Sinyal trading instan\n"
            "• <code>/analyze [TICKER]</code> — Laporan teknikal lengkap\n"
            "• <code>/scan</code> — Scan seluruh pasar IDX"
        )
