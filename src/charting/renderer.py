"""High-quality PNG chart renderer using matplotlib.

Replaces the legacy dependency-free pixel renderer with a full matplotlib
implementation that produces anti-aliased, HD-quality charts suitable for
delivery via Telegram photo messages.
"""

from __future__ import annotations

from io import BytesIO
from math import isfinite
from typing import Any, Iterable, Optional

import matplotlib
matplotlib.use("Agg")  # non-interactive backend — no display required
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

from src.charting.data import ChartData

# ---------------------------------------------------------------------------
# Palette — dark theme matching the original renderer
# ---------------------------------------------------------------------------
_BG       = "#0F172A"   # canvas background
_PANEL_BG = "#0F172A"   # subplot background
_GRID     = "#334155"   # subtle grid lines
_TEXT     = "#E2E8F0"   # primary labels
_EMA20    = "#FACC15"   # yellow
_EMA50    = "#38BDF8"   # sky blue
_EMA200   = "#A855F7"   # purple
_BULL     = "#22C55E"   # green candle
_BEAR     = "#EF4444"   # red candle
_ENTRY_C  = "#FFFFFF"   # entry level
_SL_C     = "#EF4444"   # stop-loss
_TP1_C    = "#22C55E"   # target 1
_TP2_C    = "#4ADE80"   # target 2
_RSI_C    = "#FB923C"   # orange RSI line


def _finite(values: Iterable[Optional[float]]) -> list[float]:
    return [float(v) for v in values if v is not None and isfinite(float(v))]


def _price_label(value: float) -> str:
    """Format a price value — comma-separated integer, or 3 decimals if < 10."""
    if value < 10:
        return f"{value:,.3f}"
    return f"{value:,.0f}"


class ChartRenderer:
    """Render a :class:`ChartData` object into high-quality PNG bytes."""

    # Output image size and resolution
    _FIG_W   = 14      # inches wide
    _FIG_H   = 9       # inches tall
    _DPI     = 120     # dots-per-inch → effective 1680 × 1080 px

    @classmethod
    def render(cls, chart_data: ChartData) -> bytes:
        """Return PNG bytes; never performs market data access."""

        candles   = chart_data.candles
        inds      = chart_data.indicators
        signal    = chart_data.signal
        n         = len(candles)

        # ── Figure & subplots ────────────────────────────────────────────────
        fig = plt.figure(figsize=(cls._FIG_W, cls._FIG_H), facecolor=_BG, dpi=cls._DPI,
                         layout="constrained")

        # Price panel occupies ~68 % of height, RSI ~22 %, stat bar ~10 %
        gs = fig.add_gridspec(
            3, 1,
            height_ratios=[0.68, 0.22, 0.10],
            hspace=0.04,
        )
        ax_price = fig.add_subplot(gs[0])
        ax_rsi   = fig.add_subplot(gs[1], sharex=ax_price)
        ax_stat  = fig.add_subplot(gs[2])

        for ax in (ax_price, ax_rsi, ax_stat):
            ax.set_facecolor(_PANEL_BG)
            for spine in ax.spines.values():
                spine.set_color(_GRID)

        # ── Price range with padding ─────────────────────────────────────────
        price_vals: list[float] = []
        for c in candles:
            price_vals.extend([c.low, c.high])
        for name in ("ema_20", "ema_50", "ema_200"):
            price_vals.extend(_finite(inds.get(name, ())))
        for lvl in (signal.entry, signal.stop_loss, signal.target_1, signal.target_2):
            if lvl is not None:
                price_vals.append(lvl)
        if price_vals:
            lo, hi = min(price_vals), max(price_vals)
            pad = max((hi - lo) * 0.05, 1.0)
            y_min, y_max = lo - pad, hi + pad
        else:
            y_min, y_max = 0.0, 1.0

        ax_price.set_ylim(y_min, y_max)
        ax_price.set_xlim(-0.5, n - 0.5)

        # ── Candlesticks ─────────────────────────────────────────────────────
        bar_w  = max(0.3, min(0.8, 60 / max(n, 1)))
        wick_w = 0.8  # line width for wicks

        for i, c in enumerate(candles):
            color = _BULL if c.close >= c.open else _BEAR
            # wick
            ax_price.plot([i, i], [c.low, c.high], color=color, linewidth=wick_w, zorder=2)
            # body
            body_lo = min(c.open, c.close)
            body_hi = max(c.open, c.close)
            body_h  = max(body_hi - body_lo, (y_max - y_min) * 0.001)
            rect = mpatches.FancyBboxPatch(
                (i - bar_w / 2, body_lo), bar_w, body_h,
                linewidth=0,
                facecolor=color,
                zorder=3,
                boxstyle=mpatches.BoxStyle("Square", pad=0),
            )
            ax_price.add_patch(rect)

        # ── EMA lines ────────────────────────────────────────────────────────
        xs = list(range(n))
        for name, color, lbl in (
            ("ema_20",  _EMA20,  "EMA 20"),
            ("ema_50",  _EMA50,  "EMA 50"),
            ("ema_200", _EMA200, "EMA 200"),
        ):
            raw = inds.get(name, ())
            ys = [float(v) if v is not None and isfinite(float(v)) else None for v in raw]
            # draw contiguous segments
            seg_x, seg_y = [], []
            for xi, yi in zip(xs, ys):
                if yi is None:
                    if seg_x:
                        ax_price.plot(seg_x, seg_y, color=color, linewidth=1.2,
                                      alpha=0.85, label=lbl, zorder=4)
                        seg_x, seg_y = [], []
                else:
                    seg_x.append(xi)
                    seg_y.append(yi)
            if seg_x:
                ax_price.plot(seg_x, seg_y, color=color, linewidth=1.2,
                              alpha=0.85, label=lbl, zorder=4)

        # ── Signal levels ─────────────────────────────────────────────────────
        levels = [
            ("ENTRY", signal.entry,     _ENTRY_C, "--"),
            ("SL",    signal.stop_loss, _SL_C,    "--"),
            ("TP1",   signal.target_1,  _TP1_C,   "--"),
            ("TP2",   signal.target_2,  _TP2_C,   "--"),
        ]
        for label, level, color, ls in levels:
            if level is None:
                continue
            # horizontal dashed line
            ax_price.axhline(level, color=color, linewidth=1.0,
                             linestyle=ls, alpha=0.9, zorder=5)
            # label on the LEFT inside the axes (x in axes fraction)
            ax_price.text(
                0.002, level,
                label,
                transform=ax_price.get_yaxis_transform(),
                color=color,
                fontsize=8.5,
                fontweight="bold",
                va="center",
                ha="left",
                zorder=6,
                bbox=dict(boxstyle="round,pad=0.15", facecolor=_BG,
                          edgecolor="none", alpha=0.7),
            )
            # price value on the RIGHT y-axis
            ax_price.text(
                1.002, level,
                _price_label(level),
                transform=ax_price.get_yaxis_transform(),
                color=color,
                fontsize=8.5,
                fontweight="bold",
                va="center",
                ha="left",
                zorder=6,
            )

        # ── Price axis styling ────────────────────────────────────────────────
        ax_price.yaxis.set_label_position("right")
        ax_price.yaxis.tick_right()
        ax_price.tick_params(axis="y", colors=_TEXT, labelsize=8)
        ax_price.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
        ax_price.yaxis.set_major_formatter(
            plt.FuncFormatter(lambda v, _: _price_label(v))
        )
        ax_price.grid(axis="y", color=_GRID, linewidth=0.5, alpha=0.6)
        ax_price.grid(axis="x", color=_GRID, linewidth=0.3, alpha=0.4)
        ax_price.set_xlim(-0.5, n - 0.5)

        # ── Header text ───────────────────────────────────────────────────────
        header_parts = [
            f"{chart_data.ticker}  {chart_data.timeframe or 'NA'}",
        ]
        if chart_data.data_quality_score is not None:
            header_parts.append(f"DQ {chart_data.data_quality_score:.0f}")
        if signal.verdict:
            header_parts.append(f"SIG {signal.verdict}")
        if chart_data.mtf_context and chart_data.mtf_context.get("direction"):
            header_parts.append(f"MTF {chart_data.mtf_context['direction']}")
        if chart_data.regime_context and chart_data.regime_context.get("regime"):
            header_parts.append(f"REG {chart_data.regime_context['regime']}")
        ax_price.set_title(
            "    ".join(header_parts),
            color=_TEXT, fontsize=10, fontweight="bold",
            loc="left", pad=8,
        )

        # EMA legend elements — rendered later in the stats bar
        legend_elements = [
            Line2D([0], [0], color=_EMA20,  linewidth=2.0, label="EMA 20"),
            Line2D([0], [0], color=_EMA50,  linewidth=2.0, label="EMA 50"),
            Line2D([0], [0], color=_EMA200, linewidth=2.0, label="EMA 200"),
        ]

        # ── RSI panel ─────────────────────────────────────────────────────────
        rsi_raw = inds.get("rsi_14", ())
        rsi_ys  = [float(v) if v is not None and isfinite(float(v)) else None for v in rsi_raw]
        seg_x, seg_y = [], []
        for xi, yi in zip(xs, rsi_ys):
            if yi is None:
                if seg_x:
                    ax_rsi.plot(seg_x, seg_y, color=_RSI_C, linewidth=1.2)
                    seg_x, seg_y = [], []
            else:
                seg_x.append(xi)
                seg_y.append(yi)
        if seg_x:
            ax_rsi.plot(seg_x, seg_y, color=_RSI_C, linewidth=1.2)

        ax_rsi.axhline(70, color=_GRID, linewidth=0.7, linestyle="--", alpha=0.6)
        ax_rsi.axhline(30, color=_GRID, linewidth=0.7, linestyle="--", alpha=0.6)
        ax_rsi.set_ylim(0, 100)
        ax_rsi.set_xlim(-0.5, n - 0.5)
        ax_rsi.yaxis.set_label_position("right")
        ax_rsi.yaxis.tick_right()
        ax_rsi.tick_params(axis="y", colors=_TEXT, labelsize=7)
        ax_rsi.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
        ax_rsi.grid(axis="y", color=_GRID, linewidth=0.4, alpha=0.5)
        ax_rsi.text(0.005, 0.88, "RSI 14", transform=ax_rsi.transAxes,
                    color=_TEXT, fontsize=7.5, va="top")

        # ── Date labels on X axis (shown via RSI axis) ───────────────────────
        if candles:
            date_indices = sorted({0, n // 4, n // 2, 3 * n // 4, n - 1})
            ax_rsi.set_xticks(date_indices)
            ax_rsi.set_xticklabels(
                [str(candles[i].timestamp)[:10] for i in date_indices],
                color=_TEXT, fontsize=7, rotation=0,
            )
            ax_rsi.tick_params(axis="x", bottom=True, labelbottom=True)

        # ── Stats bar ─────────────────────────────────────────────────────────
        ax_stat.set_facecolor(_BG)
        for spine in ax_stat.spines.values():
            spine.set_visible(False)
        ax_stat.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)

        stat_parts = []
        for name, fmt in (
            ("macd_line",   "MAC {:.2f}"),
            ("macd_signal", "SIG {:.2f}"),
            ("atr_14",      "ATR {:.2f}"),
            ("roc_10",      "ROC {:.2f}"),
            ("rvol",        "RVOL {:.2f}"),
        ):
            vals = _finite(inds.get(name, ()))
            if vals:
                stat_parts.append(fmt.format(vals[-1]))
        ax_stat.text(
            0.01, 0.5,
            "   ".join(stat_parts) or "NO INDICATORS",
            transform=ax_stat.transAxes,
            color=_TEXT, fontsize=8, va="center",
        )
        # EMA legend — horizontal, right side of the stats bar
        ax_stat.legend(
            handles=legend_elements,
            loc="center right",
            ncol=3,
            fontsize=8,
            framealpha=0.0,
            facecolor=_BG,
            edgecolor="none",
            labelcolor=_TEXT,
            handlelength=1.5,
            columnspacing=1.0,
        )

        # ── Render to bytes ───────────────────────────────────────────────────
        buf = BytesIO()
        fig.savefig(buf, format="png", dpi=cls._DPI, facecolor=_BG,
                    bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf.read()
