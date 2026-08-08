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

    async def generate_response(self, user_prompt: str, context_data: Optional[Dict[str, Any]] = None) -> str:
        """Generates interactive response using Gemini LLM API with optional quant context."""
        if not self.is_enabled():
            return ""

        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)

            prompt = f"{SYSTEM_PROMPT}\n\nPertanyaan Pengguna: {user_prompt}\n"
            if context_data:
                prompt += f"\nData Teknikal & Kuantitatif Terkait:\n{context_data}\n"

            # Use gemini-2.5-flash or gemini-1.5-flash as default model
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            return response.text if response and response.text else "Maaf, AI tidak mengembalikan respon."
        except Exception as e:
            logging.error(f"Error calling Gemini LLM API: {e}")
            # Fallback attempt if gemini-2.5-flash fails or legacy model name required
            try:
                from google import genai
                client = genai.Client(api_key=self.api_key)
                response = client.models.generate_content(
                    model="gemini-1.5-flash",
                    contents=prompt
                )
                return response.text if response and response.text else "Maaf, AI tidak mengembalikan respon."
            except Exception as ex:
                logging.error(f"Fallback Gemini LLM API call also failed: {ex}")
                return f"⚠️ Terjadi kendala saat menghubungi AI Agent API: {ex}"
