import re
import unittest

from src.telegram.messages import split_telegram_message


class TestTelegramMessageSplitting(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
