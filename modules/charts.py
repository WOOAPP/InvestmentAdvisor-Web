import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

COLORS = {
    "bg": "#1e1e2e",
    "fg": "#cdd6f4",
    "green": "#a6e3a1",
    "red": "#f38ba8",
    "blue": "#89b4fa",
    "yellow": "#f9e2af",
    "grid": "#313244"
}

PERIOD_MAP = {
    "1T": "1d",
    "5T": "5d",
    "1M": "1mo",
    "3M": "3mo",
    "6M": "6mo",
    "1R": "1y",
    "2R": "2y"
}

def create_price_chart(parent_frame, symbol, period="1M", compare_symbols=None):
    """Tworzy wykres cen w podanym frame Tkinter."""
    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])

    yf_period = PERIOD_MAP.get(period, "1mo")

    # Główny instrument
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=yf_period)
        if not hist.empty:
            closes = hist["Close"]
            # Normalizuj do % zmiany jeśli jest porównanie
            if compare_symbols:
                base = closes.iloc[0]
                closes = (closes / base - 1) * 100
            ax.plot(hist.index, closes, color=COLORS["blue"], linewidth=2, label=symbol)
            # Wypełnienie pod wykresem
            ax.fill_between(hist.index, closes, alpha=0.1, color=COLORS["blue"])
    except Exception as e:
        ax.text(0.5, 0.5, f"Błąd: {e}", transform=ax.transAxes,
                ha="center", color=COLORS["red"])

    # Instrumenty do porównania
    if compare_symbols:
        compare_colors = [COLORS["green"], COLORS["yellow"], COLORS["red"]]
        for i, sym in enumerate(compare_symbols[:3]):
            try:
                t = yf.Ticker(sym)
                h = t.history(period=yf_period)
                if not h.empty:
                    c = h["Close"]
                    base = c.iloc[0]
                    c = (c / base - 1) * 100
                    ax.plot(h.index, c, color=compare_colors[i % 3],
                            linewidth=1.5, label=sym, linestyle="--")
            except:
                pass
        ax.set_ylabel("Zmiana %", color=COLORS["fg"])
        ax.axhline(y=0, color=COLORS["fg"], linewidth=0.5, linestyle=":")
    else:
        ax.set_ylabel("Cena", color=COLORS["fg"])

    # Stylizacja
    ax.tick_params(colors=COLORS["fg"], labelsize=8)
    ax.spines["bottom"].set_color(COLORS["grid"])
    ax.spines["left"].set_color(COLORS["grid"])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(True, color=COLORS["grid"], linewidth=0.5, alpha=0.7)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax.legend(facecolor=COLORS["bg"], edgecolor=COLORS["grid"],
              labelcolor=COLORS["fg"], fontsize=8)
    ax.set_title(f"{symbol} – {period}", color=COLORS["fg"], fontsize=10, pad=8)
    fig.tight_layout(pad=1.5)

    canvas = FigureCanvasTkAgg(fig, master=parent_frame)
    canvas.draw()
    return canvas, fig

def create_risk_gauge(parent_frame, risk_level=5):
    """Tworzy termometr ryzyka (1-10)."""
    import numpy as np
    fig, ax = plt.subplots(figsize=(3, 2.2))
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])
    ax.set_aspect("equal")
    ax.axis("off")

    # Rysuj półkole w 3 strefach
    for i, (start_deg, end_deg, color) in enumerate([
        (0, 60, COLORS["red"]),
        (60, 120, COLORS["yellow"]),
        (120, 180, COLORS["green"])
    ]):
        theta = np.linspace(np.radians(start_deg), np.radians(end_deg), 50)
        x_out = np.cos(theta)
        y_out = np.sin(theta)
        x_in = 0.6 * np.cos(theta)
        y_in = 0.6 * np.sin(theta)
        ax.fill(
            np.concatenate([x_out, x_in[::-1]]),
            np.concatenate([y_out, y_in[::-1]]),
            color=color, alpha=0.75
        )

    # Wskazówka – risk_level 1 = prawo (0°), 10 = lewo (180°)
    needle_deg = (risk_level - 1) / 9 * 180
    needle_rad = np.radians(needle_deg)
    ax.annotate("",
        xy=(0.75 * np.cos(needle_rad), 0.75 * np.sin(needle_rad)),
        xytext=(0, 0),
        arrowprops=dict(arrowstyle="-|>", color=COLORS["fg"], lw=2.5, mutation_scale=15)
    )
    ax.plot(0, 0, "o", color=COLORS["fg"], markersize=6)

    # Etykieta
    color = COLORS["green"] if risk_level <= 3 else (COLORS["yellow"] if risk_level <= 6 else COLORS["red"])
    label = "NISKIE" if risk_level <= 3 else ("UMIARKOWANE" if risk_level <= 6 else "WYSOKIE")
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
    """Wyciąga poziom ryzyka z tekstu analizy AI."""
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