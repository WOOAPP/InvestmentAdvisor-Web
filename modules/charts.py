import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.ticker import FuncFormatter
import tkinter as tk
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

COLORS = {
    "bg":     "#1e1e2e",
    "bg2":    "#181825",
    "fg":     "#cdd6f4",
    "green":  "#a6e3a1",
    "red":    "#f38ba8",
    "blue":   "#89b4fa",
    "yellow": "#f9e2af",
    "purple": "#cba6f7",
    "grid":   "#313244",
}

PERIOD_MAP = {
    "1T": "1d",
    "5T": "5d",
    "1M": "1mo",
    "3M": "3mo",
    "6M": "6mo",
    "1R": "1y",
    "2R": "2y",
}


def create_price_chart(parent_frame, symbol, period="1M",
                       compare_symbols=None, show_ma=True):
    """Creates an enhanced price chart embedded in parent_frame.

    Includes MA20/MA50 overlays, volume subplot (when no comparison),
    and a dark-themed NavigationToolbar for zooming/panning.
    Packs the canvas and toolbar into parent_frame internally.
    Returns (canvas, fig).
    """
    show_volume = (compare_symbols is None)

    if show_volume:
        fig = plt.figure(figsize=(10, 5.5))
        gs = fig.add_gridspec(4, 1, hspace=0.06)
        ax = fig.add_subplot(gs[:3, 0])
        ax_vol = fig.add_subplot(gs[3, 0], sharex=ax)
    else:
        fig, ax = plt.subplots(figsize=(10, 4.5))
        ax_vol = None

    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])

    yf_period = PERIOD_MAP.get(period, "1mo")
    hist = None

    # ── Main instrument ──
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=yf_period)
        if not hist.empty:
            closes = hist["Close"]
            if compare_symbols:
                closes = (closes / closes.iloc[0] - 1) * 100
            ax.plot(hist.index, closes, color=COLORS["blue"],
                    linewidth=2, label=symbol, zorder=3)
            ax.fill_between(hist.index, closes, alpha=0.08,
                            color=COLORS["blue"])

            # MA20
            if show_ma and not compare_symbols and len(closes) >= 20:
                ma20 = closes.rolling(20).mean()
                ax.plot(hist.index, ma20, color=COLORS["yellow"],
                        linewidth=1.3, label="MA20", alpha=0.9,
                        linestyle="--", zorder=2)

            # MA50
            if show_ma and not compare_symbols and len(closes) >= 50:
                ma50 = closes.rolling(50).mean()
                ax.plot(hist.index, ma50, color=COLORS["purple"],
                        linewidth=1.3, label="MA50", alpha=0.9,
                        linestyle=":", zorder=2)
    except Exception as exc:
        ax.text(0.5, 0.5, f"Błąd danych:\n{exc}",
                transform=ax.transAxes, ha="center", va="center",
                color=COLORS["red"], fontsize=9)

    # ── Comparison instruments ──
    if compare_symbols:
        cmp_colors = [COLORS["green"], COLORS["yellow"], COLORS["red"]]
        for i, sym in enumerate(compare_symbols[:3]):
            if not sym:
                continue
            try:
                h = yf.Ticker(sym).history(period=yf_period)
                if not h.empty:
                    c = h["Close"]
                    c = (c / c.iloc[0] - 1) * 100
                    ax.plot(h.index, c, color=cmp_colors[i % 3],
                            linewidth=1.5, label=sym, linestyle="--")
            except Exception:
                pass
        ax.set_ylabel("Zmiana %", color=COLORS["fg"])
        ax.axhline(y=0, color=COLORS["fg"], linewidth=0.5, linestyle=":")
    else:
        ax.set_ylabel("Cena (USD)", color=COLORS["fg"])

    # ── Volume subplot ──
    if ax_vol is not None and hist is not None and not hist.empty:
        ax_vol.set_facecolor(COLORS["bg"])
        if "Volume" in hist.columns and hist["Volume"].max() > 0:
            vol_colors = []
            for i in range(len(hist)):
                if "Open" in hist.columns:
                    up = hist["Close"].iloc[i] >= hist["Open"].iloc[i]
                else:
                    up = (i == 0 or
                          hist["Close"].iloc[i] >= hist["Close"].iloc[i - 1])
                vol_colors.append(COLORS["green"] if up else COLORS["red"])

            ax_vol.bar(hist.index, hist["Volume"],
                       color=vol_colors, alpha=0.55, width=0.8)

            def _vol_fmt(x, _):
                if x >= 1e9: return f"{x/1e9:.1f}B"
                if x >= 1e6: return f"{x/1e6:.1f}M"
                if x >= 1e3: return f"{x/1e3:.0f}K"
                return str(int(x))

            ax_vol.yaxis.set_major_formatter(FuncFormatter(_vol_fmt))
            ax_vol.set_ylabel("Vol", color=COLORS["fg"], fontsize=7)
            ax_vol.tick_params(colors=COLORS["fg"], labelsize=7)
            for sp in ["top", "right"]:
                ax_vol.spines[sp].set_visible(False)
            for sp in ["bottom", "left"]:
                ax_vol.spines[sp].set_color(COLORS["grid"])
            ax_vol.grid(True, color=COLORS["grid"], linewidth=0.3, alpha=0.5)
            ax_vol.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
            ax_vol.tick_params(axis="x", colors=COLORS["fg"], labelsize=7)
            plt.setp(ax.get_xticklabels(), visible=False)

    # ── Main axis styling ──
    ax.tick_params(colors=COLORS["fg"], labelsize=8)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    for sp in ["bottom", "left"]:
        ax.spines[sp].set_color(COLORS["grid"])
    ax.grid(True, color=COLORS["grid"], linewidth=0.5, alpha=0.7)

    if compare_symbols or ax_vol is None:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))

    ax.legend(facecolor=COLORS["bg"], edgecolor=COLORS["grid"],
              labelcolor=COLORS["fg"], fontsize=8, loc="upper left")
    ax.set_title(f"{symbol}  ·  {period}", color=COLORS["fg"],
                 fontsize=10, pad=8)

    fig.tight_layout(pad=1.5)

    # ── Embed in Tkinter ──
    canvas = FigureCanvasTkAgg(fig, master=parent_frame)
    canvas.draw()

    toolbar = NavigationToolbar2Tk(canvas, parent_frame)
    toolbar.update()
    _style_toolbar(toolbar)

    canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

    return canvas, fig


def _style_toolbar(toolbar):
    """Apply dark theme to the matplotlib NavigationToolbar."""
    try:
        toolbar.configure(bg=COLORS["bg"])
        for child in toolbar.winfo_children():
            try:
                child.configure(bg=COLORS["bg"], fg=COLORS["fg"])
            except Exception:
                try:
                    child.configure(bg=COLORS["bg"])
                except Exception:
                    pass
    except Exception:
        pass


def create_risk_gauge(parent_frame, risk_level=5):
    """Creates a half-circle risk gauge (1–10)."""
    import numpy as np
    fig, ax = plt.subplots(figsize=(3, 2.2))
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])
    ax.set_aspect("equal")
    ax.axis("off")

    for start_deg, end_deg, color in [
        (0,   60,  COLORS["red"]),
        (60,  120, COLORS["yellow"]),
        (120, 180, COLORS["green"]),
    ]:
        theta = np.linspace(np.radians(start_deg), np.radians(end_deg), 50)
        x_out = np.cos(theta)
        y_out = np.sin(theta)
        x_in  = 0.6 * np.cos(theta)
        y_in  = 0.6 * np.sin(theta)
        ax.fill(
            np.concatenate([x_out, x_in[::-1]]),
            np.concatenate([y_out, y_in[::-1]]),
            color=color, alpha=0.75
        )

    needle_rad = np.radians((risk_level - 1) / 9 * 180)
    ax.annotate("",
        xy=(0.75 * np.cos(needle_rad), 0.75 * np.sin(needle_rad)),
        xytext=(0, 0),
        arrowprops=dict(arrowstyle="-|>", color=COLORS["fg"],
                        lw=2.5, mutation_scale=15))
    ax.plot(0, 0, "o", color=COLORS["fg"], markersize=6)

    color = (COLORS["green"] if risk_level <= 3
             else COLORS["yellow"] if risk_level <= 6
             else COLORS["red"])
    label = ("NISKIE" if risk_level <= 3
             else "UMIARKOWANE" if risk_level <= 6
             else "WYSOKIE")
    ax.text(0, -0.25, f"{risk_level}/10  {label}",
            ha="center", va="center", color=color,
            fontsize=10, fontweight="bold")

    ax.set_xlim(-1.1, 1.1)
    ax.set_ylim(-0.4, 1.1)
    fig.tight_layout(pad=0.5)

    canvas = FigureCanvasTkAgg(fig, master=parent_frame)
    canvas.draw()
    return canvas, fig


def extract_risk_level(analysis_text):
    """Extracts risk level (1–10) from AI analysis text."""
    import re
    patterns = [
        r"\*{0,2}(\d+)\*{0,2}/10",
        r"ryzyko[^\d]*\*{0,2}(\d+)\*{0,2}",
        r"poziom ryzyka[^\d]*\*{0,2}(\d+)\*{0,2}",
        r"poziomie\s+\*{0,2}(\d+)\*{0,2}",
        r"wynosi\s+\*{0,2}(\d+)\*{0,2}",
    ]
    for pattern in patterns:
        match = re.search(pattern, analysis_text.lower())
        if match:
            val = int(match.group(1))
            if 1 <= val <= 10:
                return val
    return 5
