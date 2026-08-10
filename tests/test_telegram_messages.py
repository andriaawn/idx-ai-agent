import re
import unittest

from src.telegram.messages import (
    markdown_to_telegram_html,
    send_png_photo,
    send_markdown_message,
    split_telegram_message,
)
from aiogram.types import BufferedInputFile


class FakeMessage:
    def __init__(self):
        self.sent = []

    async def answer(self, text, parse_mode=None):
        self.sent.append((text, parse_mode))

    async def answer_photo(self, photo):
        self.sent.append(("photo", photo))


class TestTelegramMessageSplitting(unittest.TestCase):
    def test_converts_bold_and_italic_markdown(self):
        self.assertEqual(
            markdown_to_telegram_html("**Tebal** dan *miring* serta _alternatif_."),
            "<b>Tebal</b> dan <i>miring</i> serta <i>alternatif</i>.",
        )

    def test_converts_mixed_markdown_constructs(self):
        markdown = (
            "# Judul\n"
            "- **Poin** dengan `kode`\n"
            "1. [Dokumentasi](https://example.com/docs)\n"
            "```python\nprint('<aman>')\n```"
        )
        self.assertEqual(
            markdown_to_telegram_html(markdown),
            "<b>Judul</b>\n"
            "• <b>Poin</b> dengan <code>kode</code>\n"
            "1. <a href=\"https://example.com/docs\">Dokumentasi</a>\n"
            "<pre><code>print(&#x27;&lt;aman&gt;&#x27;)</code></pre>",
        )

    def test_escapes_html_characters(self):
        self.assertEqual(
            markdown_to_telegram_html("Harga < target & risiko > batas"),
            "Harga &lt; target &amp; risiko &gt; batas",
        )

    def test_plain_text_is_split_without_losing_content(self):
        text = ("Analisis saham yang panjang. " * 500) + "Selesai."
        chunks = split_telegram_message(text, max_length=250)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 250 for chunk in chunks))
        self.assertEqual("".join(chunks), text)

    def test_html_chunks_are_individually_balanced(self):
        text = "<b>Ringkasan:</b> " + ("<i>Data teknikal penting.</i> " * 300)
        chunks = split_telegram_message(text, parse_mode="HTML", max_length=250)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 250 for chunk in chunks))
        self.assertTrue(all(chunk.count("<b>") == chunk.count("</b>") for chunk in chunks))
        self.assertTrue(all(chunk.count("<i>") == chunk.count("</i>") for chunk in chunks))
        self.assertEqual(
            re.sub(r"</?[^>]+>", "", "".join(chunks)),
            re.sub(r"</?[^>]+>", "", text),
        )

    def test_long_formatted_message_splits_inside_formatting_safely(self):
        html = markdown_to_telegram_html("**" + ("analisis penting " * 100) + "**")
        chunks = split_telegram_message(html, parse_mode="HTML", max_length=250)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 250 for chunk in chunks))
        self.assertTrue(all(chunk.startswith("<b>") for chunk in chunks))
        self.assertTrue(all(chunk.endswith("</b>") for chunk in chunks))
        self.assertEqual(
            re.sub(r"</?b>", "", "".join(chunks)),
            re.sub(r"</?b>", "", html),
        )


class TestMarkdownDelivery(unittest.IsolatedAsyncioTestCase):
    async def test_research_report_delivery_formats_and_chunks_markdown(self):
        message = FakeMessage()
        report = "# Laporan BBCA\n\n- **Ticker:** `BBCA`\n" + ("*Catatan penting.*\n" * 500)

        await send_markdown_message(message, report)

        self.assertGreater(len(message.sent), 1)
        self.assertTrue(all(parse_mode == "HTML" for _, parse_mode in message.sent))
        self.assertTrue(all(len(text) <= 4000 for text, _ in message.sent))
        self.assertTrue(any("<b>Laporan BBCA</b>" in text for text, _ in message.sent))
        self.assertTrue(any("<code>BBCA</code>" in text for text, _ in message.sent))
        self.assertTrue(all(text.count("<i>") == text.count("</i>") for text, _ in message.sent))

    async def test_png_photo_delivery_uses_buffered_bytes_without_file(self):
        message = FakeMessage()

        await send_png_photo(message, b"\x89PNG\r\n\x1a\nchart", filename="bbca.png")

        kind, photo = message.sent[0]
        self.assertEqual(kind, "photo")
        self.assertIsInstance(photo, BufferedInputFile)
        self.assertEqual(photo.data, b"\x89PNG\r\n\x1a\nchart")
        self.assertEqual(photo.filename, "bbca.png")


if __name__ == "__main__":
    unittest.main()
