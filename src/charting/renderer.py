"""Deterministic, dependency-free PNG rendering for :mod:`src.charting.data`."""

from __future__ import annotations

import struct
import zlib
from io import BytesIO
from math import isfinite
from typing import Iterable, Optional, Sequence, Tuple

from src.charting.data import ChartData


Color = Tuple[int, int, int]


class _Canvas:
    def __init__(self, width: int, height: int, background: Color) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray(background * (width * height))

    def pixel(self, x: int, y: int, color: Color) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            offset = (y * self.width + x) * 3
            self.pixels[offset:offset + 3] = bytes(color)

    def line(self, x0: int, y0: int, x1: int, y1: int, color: Color) -> None:
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        error = dx + dy
        while True:
            self.pixel(x0, y0, color)
            if x0 == x1 and y0 == y1:
                return
            twice_error = 2 * error
            if twice_error >= dy:
                error += dy
                x0 += sx
            if twice_error <= dx:
                error += dx
                y0 += sy

    def rectangle(self, left: int, top: int, right: int, bottom: int, color: Color) -> None:
        for y in range(max(0, top), min(self.height, bottom + 1)):
            for x in range(max(0, left), min(self.width, right + 1)):
                self.pixel(x, y, color)

    def text(self, x: int, y: int, value: str, color: Color) -> None:
        for character in value.upper():
            for row, bits in enumerate(_FONT.get(character, _FONT["?"])):
                for column, bit in enumerate(bits):
                    if bit == "1":
                        self.rectangle(x + column * 2, y + row * 2, x + column * 2 + 1, y + row * 2 + 1, color)
            x += 8


_FONT = {
    " ": ("000", "000", "000", "000", "000"), "?": ("110", "001", "010", "000", "010"),
    "A": ("010", "101", "111", "101", "101"), "B": ("110", "101", "110", "101", "110"),
    "C": ("011", "100", "100", "100", "011"), "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"), "F": ("111", "100", "110", "100", "100"),
    "G": ("011", "100", "101", "101", "011"), "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"), "J": ("001", "001", "001", "101", "010"),
    "K": ("101", "101", "110", "101", "101"), "L": ("100", "100", "100", "100", "111"),
    "M": ("101", "111", "111", "101", "101"), "N": ("101", "111", "111", "111", "101"),
    "O": ("010", "101", "101", "101", "010"), "P": ("110", "101", "110", "100", "100"),
    "Q": ("010", "101", "101", "111", "011"), "R": ("110", "101", "110", "101", "101"),
    "S": ("011", "100", "010", "001", "110"), "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"), "V": ("101", "101", "101", "101", "010"),
    "W": ("101", "101", "111", "111", "101"), "X": ("101", "101", "010", "101", "101"),
    "Y": ("101", "101", "010", "010", "010"), "Z": ("111", "001", "010", "100", "111"),
    "0": ("111", "101", "101", "101", "111"), "1": ("010", "110", "010", "010", "111"),
    "2": ("110", "001", "010", "100", "111"), "3": ("110", "001", "010", "001", "110"),
    "4": ("101", "101", "111", "001", "001"), "5": ("111", "100", "110", "001", "110"),
    "6": ("011", "100", "110", "101", "010"), "7": ("111", "001", "010", "010", "010"),
    "8": ("010", "101", "010", "101", "010"), "9": ("010", "101", "011", "001", "110"),
    ".": ("000", "000", "000", "000", "010"), ":": ("000", "010", "000", "010", "000"),
    "-": ("000", "000", "111", "000", "000"), "_": ("000", "000", "000", "000", "111"),
}


class ChartRenderer:
    """Render prepared :class:`ChartData` into deterministic PNG bytes."""

    WIDTH = 1000
    HEIGHT = 720
    _BACKGROUND = (15, 23, 42)
    _GRID = (51, 65, 85)
    _TEXT = (226, 232, 240)

    @staticmethod
    def _finite(values: Iterable[Optional[float]]) -> list[float]:
        return [float(value) for value in values if value is not None and isfinite(float(value))]

    @staticmethod
    def _scale(value: float, minimum: float, maximum: float, top: int, bottom: int) -> int:
        if maximum == minimum:
            return (top + bottom) // 2
        return round(bottom - (value - minimum) * (bottom - top) / (maximum - minimum))

    @classmethod
    def _series(cls, canvas: _Canvas, values: Sequence[Optional[float]], left: int, right: int,
                top: int, bottom: int, minimum: float, maximum: float, color: Color) -> None:
        previous = None
        total = max(1, len(values) - 1)
        for index, value in enumerate(values):
            if value is None or not isfinite(float(value)):
                previous = None
                continue
            point = (round(left + (right - left) * index / total), cls._scale(float(value), minimum, maximum, top, bottom))
            if previous is not None:
                canvas.line(previous[0], previous[1], point[0], point[1], color)
            previous = point

    @staticmethod
    def _chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    @classmethod
    def _png(cls, canvas: _Canvas, metadata: str) -> bytes:
        rows = b"".join(b"\x00" + canvas.pixels[y * canvas.width * 3:(y + 1) * canvas.width * 3] for y in range(canvas.height))
        return b"\x89PNG\r\n\x1a\n" + cls._chunk(b"IHDR", struct.pack(">IIBBBBB", canvas.width, canvas.height, 8, 2, 0, 0, 0)) + cls._chunk(b"tEXt", metadata.encode("latin-1")) + cls._chunk(b"IDAT", zlib.compress(rows, level=9)) + cls._chunk(b"IEND", b"")

    @classmethod
    def render(cls, chart_data: ChartData) -> bytes:
        """Return an in-memory PNG; no data preparation or market access occurs."""
        canvas = _Canvas(cls.WIDTH, cls.HEIGHT, cls._BACKGROUND)
        left, right, price_top, price_bottom = 60, 950, 70, 440
        canvas.text(20, 18, f"{chart_data.ticker} {chart_data.timeframe or 'NA'}", cls._TEXT)
        if chart_data.data_quality_score is not None:
            canvas.text(20, 38, f"DQ {chart_data.data_quality_score:.0f}", cls._TEXT)
        if chart_data.signal.verdict:
            canvas.text(220, 38, f"SIG {chart_data.signal.verdict}", cls._TEXT)
        if chart_data.mtf_context and chart_data.mtf_context.get("direction"):
            canvas.text(480, 38, f"MTF {chart_data.mtf_context['direction']}", cls._TEXT)
        if chart_data.regime_context and chart_data.regime_context.get("regime"):
            canvas.text(700, 38, f"REG {chart_data.regime_context['regime']}", cls._TEXT)
        for y in range(price_top, price_bottom + 1, 74):
            canvas.line(left, y, right, y, cls._GRID)

        price_values = [value for candle in chart_data.candles for value in (candle.low, candle.high)]
        for name in ("ema_20", "ema_50", "ema_200"):
            price_values.extend(cls._finite(chart_data.indicators.get(name, ())))
        for level in (chart_data.signal.entry, chart_data.signal.stop_loss, chart_data.signal.target_1, chart_data.signal.target_2):
            if level is not None:
                price_values.append(level)
        minimum, maximum = (min(price_values), max(price_values)) if price_values else (0.0, 1.0)
        padding = max((maximum - minimum) * 0.05, 1.0)
        minimum, maximum = minimum - padding, maximum + padding

        count = len(chart_data.candles)
        step = (right - left) / max(count, 1)
        half_width = max(1, min(8, round(step * 0.3)))
        for index, candle in enumerate(chart_data.candles):
            x = round(left + step * (index + 0.5))
            high = cls._scale(candle.high, minimum, maximum, price_top, price_bottom)
            low = cls._scale(candle.low, minimum, maximum, price_top, price_bottom)
            opening = cls._scale(candle.open, minimum, maximum, price_top, price_bottom)
            closing = cls._scale(candle.close, minimum, maximum, price_top, price_bottom)
            color = (34, 197, 94) if candle.close >= candle.open else (239, 68, 68)
            canvas.line(x, high, x, low, color)
            canvas.rectangle(x - half_width, min(opening, closing), x + half_width, max(opening, closing), color)

        for name, color in (("ema_20", (250, 204, 21)), ("ema_50", (56, 189, 248)), ("ema_200", (168, 85, 247))):
            cls._series(canvas, chart_data.indicators.get(name, ()), left, right, price_top, price_bottom, minimum, maximum, color)
        for level, color in ((chart_data.signal.entry, (255, 255, 255)), (chart_data.signal.stop_loss, (239, 68, 68)), (chart_data.signal.target_1, (34, 197, 94)), (chart_data.signal.target_2, (74, 222, 128))):
            if level is not None:
                y = cls._scale(level, minimum, maximum, price_top, price_bottom)
                canvas.line(left, y, right, y, color)

        rsi_top, rsi_bottom = 500, 590
        canvas.line(left, rsi_top, right, rsi_top, cls._GRID)
        canvas.line(left, rsi_bottom, right, rsi_bottom, cls._GRID)
        cls._series(canvas, chart_data.indicators.get("rsi_14", ()), left, right, rsi_top, rsi_bottom, 0.0, 100.0, (251, 146, 60))
        canvas.text(20, 505, "RSI", cls._TEXT)
        latest = []
        for name in ("macd_line", "macd_signal", "atr_14", "roc_10", "rvol"):
            values = cls._finite(chart_data.indicators.get(name, ()))
            if values:
                latest.append(f"{name[:3]} {values[-1]:.2f}")
        canvas.text(20, 630, " ".join(latest) or "NO INDICATORS", cls._TEXT)
        metadata = f"ChartData|ticker={chart_data.ticker}|timeframe={chart_data.timeframe}|candles={count}"
        return cls._png(canvas, metadata)
