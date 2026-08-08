import unittest

from src.data.ticker_resolver import TickerResolver


class TestTickerResolver(unittest.TestCase):
    def setUp(self):
        # An injected universe makes these unit tests deterministic and offline.
        self.resolver = TickerResolver(["BBCA", "CUAN", "DSSA", "TLKM"])

    def test_extracts_two_valid_tickers(self):
        self.assertEqual(
            self.resolver.extract("bandingkan cuan dan dssa"),
            ["CUAN.JK", "DSSA.JK"],
        )

    def test_ignores_four_letter_regular_words(self):
        self.assertEqual(
            self.resolver.extract("coba bandingkan saham cuan dan dssa"),
            ["CUAN.JK", "DSSA.JK"],
        )
        self.assertEqual(self.resolver.extract("coba"), [])

    def test_normalizes_lowercase_and_jk_suffix(self):
        self.assertEqual(self.resolver.extract("analisis bbca"), ["BBCA.JK"])
        self.assertEqual(self.resolver.extract("analisis BBCA.JK"), ["BBCA.JK"])

    def test_preserves_order_and_deduplicates_multiple_tickers(self):
        self.assertEqual(
            self.resolver.extract("TLKM, bbca, TLKM.JK, dssa"),
            ["TLKM.JK", "BBCA.JK", "DSSA.JK"],
        )

    def test_invalid_candidate_is_ignored(self):
        self.assertIsNone(self.resolver.resolve_candidate("COBA"))
        self.assertEqual(self.resolver.extract("COBA dan XXXX"), [])


if __name__ == "__main__":
    unittest.main()
