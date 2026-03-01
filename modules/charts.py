import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.ticker import FuncFormatter, MaxNLocator
import tkinter as tk
import yfinance as yf
import pandas as pd
import logging
from datetime import datetime, timedelta
from modules.http_client import safe_get

logger = logging.getLogger(__name__)

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

COINGECKO_DAYS = {
    "1T": 1,
    "5T": 5,
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "1R": 365,
    "2R": 730,
}


def _fetch_coingecko_chart(coin_id, days):
    """Fetch historical chart data from CoinGecko API."""
    url = (f"https://api.coingecko.com/api/v3/coins/{coin_id}"
           f"/market_chart?vs_currency=usd&days={days}")
    r = safe_get(url)
    data = r.json()

    prices = data.get("prices", [])
    volumes = data.get("total_volumes", [])

    if not prices:
        return pd.DataFrame()

    df = pd.DataFrame(prices, columns=["timestamp", "Close"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)

    if volumes:
        vol_df = pd.DataFrame(volumes, columns=["timestamp", "Volume"])
        vol_df["timestamp"] = pd.to_datetime(vol_df["timestamp"], unit="ms")
        vol_df.set_index("timestamp", inplace=True)
        df = df.join(vol_df, how="left")

    df["Open"] = df["Close"].shift(1)
    df.loc[df.index[0], "Open"] = df["Close"].iloc[0]

    return df


def fetch_chart_data(symbol, period, source="yfinance"):
    """Fetch chart data from the appropriate source."""
    if source == "coingecko":
        days = COINGECKO_DAYS.get(period, 30)
        return _fetch_coingecko_chart(symbol, days)
    else:
        yf_period = PERIOD_MAP.get(period, "1mo")
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=yf_period)
        # Strip timezone info for consistent handling
        if hist.index.tz is not None:
            hist.index = hist.index.tz_localize(None)
        return hist


# ── Adaptive helpers ────────────────────────────────────────────────

def _bar_width(hist):
    """Compute a bar width in days appropriate for the data density."""
    if len(hist) < 2:
        return 0.8
    diffs = pd.Series(hist.index).diff().dropna().dt.total_seconds()
    if diffs.empty:
        return 0.8
    median_gap_days = diffs.median() / 86400
    return max(median_gap_days * 0.7, 0.0005)


def _compute_vol_colors(hist):
    """Vectorised volume bar coloring — avoids slow row-by-row loop."""
    if "Open" in hist.columns:
        up = pd.to_numeric(hist["Close"], errors="coerce").fillna(0) >= \
             pd.to_numeric(hist["Open"], errors="coerce").fillna(0)
    else:
        close = pd.to_numeric(hist["Close"], errors="coerce").fillna(0)
        up = close >= close.shift(1).fillna(close)
    return [COLORS["green"] if v else COLORS["red"] for v in up]


def _setup_xaxis(ax, period, n_points):
    """Configure x-axis date formatting and tick density for readability."""
    if period == "1T":
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=max(1, n_points // 8)))
    elif period == "5T":
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m\n%a"))
        ax.xaxis.set_major_locator(mdates.DayLocator())
    elif period in ("1M", "3M"):
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
        if period == "1M":
            ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=0))
        else:
            ax.xaxis.set_major_locator(mdates.MonthLocator())
    elif period == "6M":
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator())
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3 if period == "2R" else 2))


def _add_markers_sparse(ax, closes, color):
    """For very sparse data (≤10 points) add dot markers for visibility."""
    if len(closes) <= 10:
        ax.plot(closes.index, closes, "o", color=color, markersize=5,
                zorder=4)


# ── Main chart function ─────────────────────────────────────────────

def create_price_chart(parent_frame, symbol, period="1M",
                       compare_symbols=None, show_ma=True,
                       sources_map=None):
    """Creates an enhanced price chart embedded in parent_frame.

    sources_map: dict mapping symbol -> source ("yfinance" or "coingecko").
    If None, defaults to yfinance for all symbols.
    """
    if sources_map is None:
        sources_map = {}

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

    hist = None
    source = sources_map.get(symbol, "yfinance")
    n_points = 0

    # ── Main instrument ──
    try:
        hist = fetch_chart_data(symbol, period, source)
        if hist is not None and not hist.empty:
            closes = pd.to_numeric(hist["Close"], errors="coerce").dropna()
            n_points = len(closes)
            if not closes.empty:
                plot_data = closes
                if compare_symbols:
                    plot_data = (closes / closes.iloc[0] - 1) * 100
                ax.plot(plot_data.index, plot_data, color=COLORS["blue"],
                        linewidth=2, label=symbol, zorder=3)
                ax.fill_between(plot_data.index, plot_data, alpha=0.08,
                                color=COLORS["blue"])
                _add_markers_sparse(ax, plot_data, COLORS["blue"])

                # MA20
                if show_ma and not compare_symbols and len(closes) >= 20:
                    ma20 = closes.rolling(20).mean()
                    ax.plot(closes.index, ma20, color=COLORS["yellow"],
                            linewidth=1.3, label="MA20", alpha=0.9,
                            linestyle="--", zorder=2)

                # MA50
                if show_ma and not compare_symbols and len(closes) >= 50:
                    ma50 = closes.rolling(50).mean()
                    ax.plot(closes.index, ma50, color=COLORS["purple"],
                            linewidth=1.3, label="MA50", alpha=0.9,
                            linestyle=":", zorder=2)
            else:
                ax.text(0.5, 0.5, f"Brak danych cenowych dla {symbol}",
                        transform=ax.transAxes, ha="center", va="center",
                        color=COLORS["red"], fontsize=9)
        else:
            ax.text(0.5, 0.5, f"Brak danych dla {symbol}",
                    transform=ax.transAxes, ha="center", va="center",
                    color=COLORS["red"], fontsize=9)
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
                cmp_source = sources_map.get(sym, "yfinance")
                h = fetch_chart_data(sym, period, cmp_source)
                if h is not None and not h.empty:
                    c = pd.to_numeric(h["Close"], errors="coerce").dropna()
                    if not c.empty:
                        c = (c / c.iloc[0] - 1) * 100
                        ax.plot(c.index, c, color=cmp_colors[i % 3],
                                linewidth=1.5, label=sym, linestyle="--")
            except Exception:
                pass
        ax.set_ylabel("Zmiana %", color=COLORS["fg"], fontsize=10)
        ax.axhline(y=0, color=COLORS["fg"], linewidth=0.5, linestyle=":")
    else:
        ax.set_ylabel("Cena (USD)", color=COLORS["fg"], fontsize=10)

    # ── Volume subplot ──
    has_volume = False
    if ax_vol is not None and hist is not None and not hist.empty:
        ax_vol.set_facecolor(COLORS["bg"])
        vol_ok = ("Volume" in hist.columns
                  and pd.to_numeric(hist["Volume"], errors="coerce")
                  .fillna(0).max() > 0)
        if vol_ok:
            has_volume = True
            vol_colors = _compute_vol_colors(hist)
            bw = _bar_width(hist)
            ax_vol.bar(hist.index, hist["Volume"],
                       color=vol_colors, alpha=0.55, width=bw)

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

    # ── X-axis formatting (applied consistently to the bottom-most visible axis) ──
    bottom_ax = ax_vol if (has_volume and ax_vol is not None) else ax
    _setup_xaxis(bottom_ax, period, n_points)
    bottom_ax.tick_params(axis="x", colors=COLORS["fg"], labelsize=8)

    # Rotate labels only for longer date strings; short periods stay horizontal
    if period in ("1T", "5T"):
        for label in bottom_ax.get_xticklabels():
            label.set_rotation(0)
            label.set_ha("center")
    else:
        for label in bottom_ax.get_xticklabels():
            label.set_rotation(30)
            label.set_ha("right")

    # Hide price-axis x-labels when volume subplot is the bottom axis
    if has_volume and ax_vol is not None:
        plt.setp(ax.get_xticklabels(), visible=False)

    # ── Main axis styling ──
    ax.tick_params(colors=COLORS["fg"], labelsize=9)
    for sp in ["top", "right"]:
        ax.spines[sp].set_visible(False)
    for sp in ["bottom", "left"]:
        ax.spines[sp].set_color(COLORS["grid"])
    ax.grid(True, color=COLORS["grid"], linewidth=0.5, alpha=0.7)

    # Y-axis number formatting (e.g. 80,000 instead of 80000)
    if not compare_symbols:
        def _price_fmt(x, _):
            if abs(x) >= 1e6:
                return f"{x:,.0f}"
            elif abs(x) >= 100:
                return f"{x:,.2f}"
            elif abs(x) >= 1:
                return f"{x:.4f}"
            else:
                return f"{x:.6f}"
        ax.yaxis.set_major_formatter(FuncFormatter(_price_fmt))

    ax.legend(facecolor=COLORS["bg"], edgecolor=COLORS["grid"],
              labelcolor=COLORS["fg"], fontsize=9, loc="upper left")

    # Title with instrument name and current price
    title_text = f"{symbol}  ·  {period}"
    if hist is not None and not hist.empty and not compare_symbols:
        last_close = pd.to_numeric(hist["Close"], errors="coerce").dropna()
        if not last_close.empty:
            price_val = last_close.iloc[-1]
            if price_val >= 100:
                title_text = f"{symbol}  ·  {price_val:,.2f}  ·  {period}"
            else:
                title_text = f"{symbol}  ·  {price_val:.4f}  ·  {period}"
    ax.set_title(title_text, color=COLORS["fg"],
                 fontsize=12, fontweight="bold", pad=12)

    fig.tight_layout(pad=2.0)

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
