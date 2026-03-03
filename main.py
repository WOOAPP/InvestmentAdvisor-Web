import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import logging
import threading
import schedule
import time
import sys
import os
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(__file__))
from config import load_config, save_config, mask_key, get_api_key
from modules.market_data import get_all_instruments, get_news, format_market_summary, get_fx_to_usd
from modules.openai_pricing import get_model_cost, refresh_pricing
from modules.ai_engine import (run_analysis, run_chat, get_available_models,
                               generate_instrument_profile,
                               generate_calendar_event_analysis,
                               _build_instrument_list)
from modules.database import (
    save_report, get_reports, get_report_by_id, get_latest_report,
    save_market_snapshot, get_unseen_alerts, mark_alerts_seen, delete_report,
    add_portfolio_position, get_portfolio_positions, delete_portfolio_position,
    get_instrument_profile, save_instrument_profile,
)
from modules.charts import (create_price_chart, create_risk_gauge,
                            extract_risk_level, fetch_chart_data)
from modules.scraper import scrape_all
from modules.calendar_data import fetch_calendar, get_event_significance
from modules.macro_trend import build_macro_payload, format_macro_payload_for_llm
from modules.ui_helpers import (
    setup_markdown_tags, insert_markdown,
    bind_chat_focus, BusySpinner,
)

BG     = "#1e1e2e"
BG2    = "#181825"
FG     = "#cdd6f4"
ACCENT = "#89b4fa"
GREEN  = "#a6e3a1"
RED    = "#f38ba8"
YELLOW = "#f9e2af"
GRAY    = "#313244"
BTN_BG  = "#313244"
SUBTEXT = "#7f849c"   # Catppuccin overlay1 – czytelny tekst pomocniczy


class InvestmentAdvisor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Investment Advisor")
        self.geometry("1280x800")
        self.minsize(1024, 700)
        self.configure(bg=BG)
        self.config_data = load_config()
        self.current_analysis = ""
        self.current_market_data = {}
        self._fx_cache = {}         # currency→USD rate cache for portfolio
        self._chat_history = []     # list of {"role": ..., "content": ...}
        self.inst_entries = []
        self.source_entries = []
        self._tile_widgets = {}
        self._current_chart_fig = None
        self._chart_chat_history = []
        self._cal_events = []
        self._cal_request_id = 0
        self._cal_analysis_cache = {}   # {event_key: analysis_text}
        self._period_buttons = {}
        self._click_pending = None   # after-id for single/double click
        self._click_symbol = None
        self._shutting_down = False
        self._analysis_overlay_msg = ""
        self._analysis_overlay_step = 0
        self._busy_buttons = []   # buttons to lock during analysis/fetch
        self._spinner = None      # BusySpinner instance (created after UI build)
        self._chat_extra_displays = []   # extra chat display widgets (popups)
        self._market_popup_tile_widgets = {}  # tile widgets in market popup
        self._prev_prices = {}               # {symbol: last_known_price} dla efektu flash
        self._build_ui()
        threading.Thread(target=refresh_pricing, daemon=True).start()
        self._autoload_last_report()
        self._start_scheduler()
        self._check_alerts()
        self._start_price_autorefresh()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Mousewheel scrolling helper ───────────────────────────
    def _bind_mousewheel(self, area_widget, scroll_target):
        """Bind mousewheel scrolling when cursor enters area_widget."""
        def _on_mousewheel(event):
            if event.delta:
                scroll_target.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif event.num == 4:
                scroll_target.yview_scroll(-3, "units")
            elif event.num == 5:
                scroll_target.yview_scroll(3, "units")

        def _on_enter(event):
            area_widget.bind_all("<MouseWheel>", _on_mousewheel)
            area_widget.bind_all("<Button-4>", _on_mousewheel)
            area_widget.bind_all("<Button-5>", _on_mousewheel)

        def _on_leave(event):
            area_widget.unbind_all("<MouseWheel>")
            area_widget.unbind_all("<Button-4>")
            area_widget.unbind_all("<Button-5>")

        area_widget.bind("<Enter>", _on_enter)
        area_widget.bind("<Leave>", _on_leave)

    # ── UI scaffold ─────────────────────────────────────────
    def _build_ui(self):
        top = tk.Frame(self, bg=BG2, height=50)
        top.pack(fill="x")
        tk.Label(top, text="📈 Investment Advisor", bg=BG2, fg=ACCENT,
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=16, pady=8)
        self.alert_btn = tk.Button(
            top, text="🔔 Alerty", bg=BTN_BG, fg=YELLOW,
            font=("Segoe UI", 10), relief="flat", cursor="hand2",
            command=self._show_alerts)
        self.alert_btn.pack(side="right", padx=8, pady=8)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BTN_BG, foreground=FG,
                        padding=[12, 6], font=("Segoe UI", 10))
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", BG)])
        style.configure("Treeview", background=BG2, foreground=FG,
                        fieldbackground=BG2, rowheight=24)
        style.configure("Treeview.Heading", background=BTN_BG, foreground=ACCENT)
        style.map("Treeview",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", BG)])

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_dashboard = tk.Frame(self.notebook, bg=BG)
        self.tab_portfolio  = tk.Frame(self.notebook, bg=BG)
        self.tab_calendar   = tk.Frame(self.notebook, bg=BG)
        self.tab_charts     = tk.Frame(self.notebook, bg=BG)
        self.tab_history    = tk.Frame(self.notebook, bg=BG)
        self.tab_settings   = tk.Frame(self.notebook, bg=BG)

        self.notebook.add(self.tab_dashboard, text="  🏠  Dashboard  ")
        self.notebook.add(self.tab_portfolio,  text="  💼  Portfel  ")
        self.notebook.add(self.tab_calendar,   text="  🗓  Kalendarz  ")
        self.notebook.add(self.tab_charts,     text="  📈  Wykresy  ")
        self.notebook.add(self.tab_history,    text="  📜  Historia  ")
        self.notebook.add(self.tab_settings,   text="  ⚙  Ustawienia  ")

        self._build_dashboard()
        self._build_portfolio_tab()
        self._build_calendar_tab()
        self._build_charts_tab()
        self._build_history_tab()
        self._build_settings_tab()

    # ═══════════════════════════════════════
    # OCHRONA HASŁEM – PROMPTY
    # ═══════════════════════════════════════
    _SETTINGS_PASSWORD = "666"

    def _on_prompts_tab_change(self, event):
        if self._prompts_tab_locked:
            return
        nb = self._settings_nb
        selected = nb.index(nb.select())
        prompts_idx = nb.index(self._tab_prompts)
        if selected == prompts_idx:
            if not self._verify_settings_password():
                self._prompts_tab_locked = True
                nb.select(self._prompts_prev_idx)
                self._prompts_tab_locked = False
                return
        self._prompts_prev_idx = selected

    def _verify_settings_password(self):
        dlg = tk.Toplevel(self)
        dlg.title("Hasło")
        dlg.resizable(False, False)
        dlg.configure(bg=BG)
        dlg.grab_set()

        # Wyśrodkowanie względem okna głównego
        self.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - 300) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 140) // 2
        dlg.geometry(f"300x140+{x}+{y}")

        tk.Label(dlg, text="🔒 Podaj hasło do ustawień:", bg=BG, fg=FG,
                 font=("Segoe UI", 10)).pack(pady=(18, 6))

        var = tk.StringVar()
        entry = tk.Entry(dlg, textvariable=var, show="●", bg=GRAY, fg=FG,
                         insertbackground=FG, relief="flat",
                         font=("Segoe UI", 12), width=18)
        entry.pack(pady=4)
        entry.focus_set()

        result = [False]

        def _confirm(event=None):
            result[0] = (var.get() == self._SETTINGS_PASSWORD)
            if not result[0]:
                entry.config(fg=RED)
                var.set("")
                entry.after(600, dlg.destroy)
            else:
                dlg.destroy()

        entry.bind("<Return>", _confirm)
        tk.Button(dlg, text="OK", bg=ACCENT, fg=BG,
                  font=("Segoe UI", 10, "bold"), relief="flat",
                  cursor="hand2", padx=20, pady=4,
                  command=_confirm).pack(pady=(8, 0))

        dlg.wait_window()
        return result[0]

    # ═══════════════════════════════════════
    # DASHBOARD
    # ═══════════════════════════════════════
    def _build_dashboard(self):
        left = tk.Frame(self.tab_dashboard, bg=BG, width=330)
        left.pack(side="left", fill="y", padx=(8, 4), pady=8)
        left.pack_propagate(False)

        risk_frame = tk.LabelFrame(
            left, text=" Ryzyko Rynkowe ", bg=BG, fg=ACCENT,
            font=("Segoe UI", 10, "bold"), relief="flat",
            highlightbackground=GRAY, highlightthickness=1)
        risk_frame.pack(fill="x", pady=(0, 8))
        self.gauge_frame = tk.Frame(risk_frame, bg=BG)
        self.gauge_frame.pack()

        tiles_lf = tk.LabelFrame(
            left, text=" Kursy Rynkowe ", bg=BG, fg=ACCENT,
            font=("Segoe UI", 10, "bold"), relief="flat",
            highlightbackground=GRAY, highlightthickness=1)
        tiles_lf.pack(fill="both", expand=True)
        self._build_price_tiles(tiles_lf)
        tiles_lf.bind("<Double-Button-1>", lambda e: self._open_market_popup())

        right = tk.Frame(self.tab_dashboard, bg=BG)
        right.pack(side="right", fill="both", expand=True, padx=(4, 8), pady=8)

        btn_bar = tk.Frame(right, bg=BG)
        btn_bar.pack(fill="x", pady=(0, 6))

        self.analyze_btn = tk.Button(
            btn_bar, text="▶  Uruchom Analizę", bg=ACCENT, fg=BG,
            font=("Segoe UI", 11, "bold"), relief="flat",
            cursor="hand2", padx=16, pady=6,
            command=self._run_analysis_thread)
        self.analyze_btn.pack(side="left")

        self.fetch_btn = tk.Button(
            btn_bar, text="🔄 Pobierz ceny", bg=BTN_BG, fg=FG,
            font=("Segoe UI", 10), relief="flat", cursor="hand2",
            padx=12, pady=6, command=self._quick_fetch_prices)
        self.fetch_btn.pack(side="left", padx=8)

        self.export_btn = tk.Button(
            btn_bar, text="📄 Eksport PDF", bg=BTN_BG, fg=FG,
            font=("Segoe UI", 10), relief="flat", cursor="hand2",
            padx=12, pady=6, command=self._export_pdf)
        self.export_btn.pack(side="left", padx=8)

        self.status_label = tk.Label(
            btn_bar, text="Gotowy", bg=BG, fg=SUBTEXT, font=("Segoe UI", 9))
        self.status_label.pack(side="right", padx=8)

        # Task 2: register buttons for busy-lock
        self._busy_buttons = [self.analyze_btn, self.fetch_btn, self.export_btn]
        self._spinner = BusySpinner(self, self.status_label)

        # ── Token / model info bar – always visible, outside PanedWindow ──
        self.token_info_frame = tk.Frame(right, bg="#16161e",
                                         highlightbackground=GRAY,
                                         highlightthickness=1)
        self.token_info_frame.pack(fill="x", pady=(0, 4))
        self.token_line_label = tk.Label(
            self.token_info_frame, text="", bg="#16161e", fg="#FFD54F",
            font=("Segoe UI", 8, "bold"), anchor="w")
        self.token_line_label.pack(fill="x", padx=6, pady=4)

        # ── PanedWindow: analysis (top) + chat (bottom) ──
        paned = tk.PanedWindow(right, orient="vertical", bg=BG,
                                sashwidth=5, sashrelief="flat")
        paned.pack(fill="both", expand=True)
        self._dash_paned = paned
        paned.bind("<Map>", self._set_dash_sash, add="+")

        # — Analysis panel —
        analysis_frame = tk.LabelFrame(
            paned, text=" Analiza AI ", bg=BG, fg=ACCENT,
            font=("Segoe UI", 10, "bold"), relief="flat",
            highlightbackground=GRAY, highlightthickness=1)
        paned.add(analysis_frame, minsize=120)
        analysis_frame.bind("<Double-Button-1>",
                            lambda e: self._open_analysis_popup())
        # Container with overlay support
        self._analysis_container = tk.Frame(analysis_frame, bg=BG2)
        self._analysis_container.pack(fill="both", expand=True, padx=4, pady=4)
        self.analysis_text = scrolledtext.ScrolledText(
            self._analysis_container, bg=BG2, fg=FG, font=("Segoe UI", 10),
            relief="flat", wrap="word", state="disabled",
            insertbackground=FG, selectbackground=ACCENT)
        self.analysis_text.pack(fill="both", expand=True)
        self.analysis_text.bind("<Double-Button-1>",
                                lambda e: self._open_analysis_popup())
        setup_markdown_tags(self.analysis_text)
        # Loading overlay (hidden by default)
        self._analysis_overlay = tk.Label(
            self._analysis_container, bg="#181825", fg=ACCENT,
            font=("Segoe UI", 16, "bold"), anchor="center")
        self._analysis_overlay_visible = False
        self._analysis_overlay_after = None

        # Report date label (CEL 3)
        self.report_date_label = tk.Label(
            analysis_frame, text="", bg=BG, fg=GREEN,
            font=("Segoe UI", 8), anchor="w")
        self.report_date_label.pack(fill="x", padx=8, pady=(2, 0))

        # — Chat panel —
        self.chat_frame = tk.LabelFrame(
            paned, text=" Czat z AI ", bg=BG, fg=ACCENT,
            font=("Segoe UI", 10, "bold"), relief="flat",
            highlightbackground=GRAY, highlightthickness=1)
        paned.add(self.chat_frame, minsize=120)
        self.chat_frame.bind("<Double-Button-1>",
                             lambda e: self._open_chat_popup())

        self.chat_display = scrolledtext.ScrolledText(
            self.chat_frame, bg=BG2, fg=FG, font=("Segoe UI", 10),
            relief="flat", wrap="word", state="disabled",
            insertbackground=FG, selectbackground=ACCENT, height=8)
        self.chat_display.pack(fill="both", expand=True, padx=4, pady=(4, 2))
        self.chat_display.bind("<Double-Button-1>",
                               lambda e: self._open_chat_popup())
        self.chat_display.tag_configure("user", foreground=ACCENT)
        self.chat_display.tag_configure("assistant", foreground=GREEN)
        self.chat_display.tag_configure("label", foreground=YELLOW,
                                         font=("Segoe UI", 9, "bold"))
        self.chat_display.tag_configure("error", foreground=RED)

        input_bar = tk.Frame(self.chat_frame, bg=BG)
        input_bar.pack(fill="x", padx=4, pady=(0, 6))

        # Pack buttons right-to-left first so they always stay visible
        tk.Button(
            input_bar, text="Wyczyść", bg=BTN_BG, fg=SUBTEXT,
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            padx=8, command=self._clear_chat
        ).pack(side="right", padx=(4, 0))

        self.chat_send_btn = tk.Button(
            input_bar, text="Wyślij", bg=ACCENT, fg=BG,
            font=("Segoe UI", 10, "bold"), relief="flat",
            cursor="hand2", padx=12, command=self._send_chat_message)
        self.chat_send_btn.pack(side="right", padx=(4, 0))

        self.chat_entry = tk.Entry(
            input_bar, bg=BG2, fg=FG, insertbackground=FG,
            relief="flat", font=("Segoe UI", 10),
            highlightbackground=GRAY, highlightthickness=1)
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.chat_entry.bind("<Return>", lambda e: self._send_chat_message())

        # Task 1 + 3: markdown tags + click-to-focus for dashboard chat
        setup_markdown_tags(self.chat_display)
        bind_chat_focus(self.chat_frame, self.chat_entry)

    # ── Kafelki Bloomberg ────────────────────────────────────
    def _build_price_tiles(self, parent):
        container = tk.Frame(parent, bg=BG)
        container.pack(fill="both", expand=True)

        self._tiles_canvas = tk.Canvas(container, bg=BG, highlightthickness=0)
        tiles_sb = ttk.Scrollbar(container, orient="vertical",
                                  command=self._tiles_canvas.yview)
        self._tiles_canvas.configure(yscrollcommand=tiles_sb.set)
        tiles_sb.pack(side="right", fill="y")
        self._tiles_canvas.pack(side="left", fill="both", expand=True)

        self._tiles_frame = tk.Frame(self._tiles_canvas, bg=BG)
        self._tiles_win = self._tiles_canvas.create_window(
            (0, 0), window=self._tiles_frame, anchor="nw")

        self._tiles_frame.bind(
            "<Configure>",
            lambda e: self._tiles_canvas.configure(
                scrollregion=self._tiles_canvas.bbox("all")))
        self._tiles_canvas.bind(
            "<Configure>",
            lambda e: self._tiles_canvas.itemconfig(
                self._tiles_win, width=e.width))

        # Mousewheel scrolling for tiles area
        self._bind_mousewheel(self._tiles_canvas, self._tiles_canvas)

        self._populate_tile_placeholders(self.config_data.get("instruments", []))

    def _populate_tile_placeholders(self, instruments):
        for w in self._tiles_frame.winfo_children():
            w.destroy()
        self._tile_widgets = {}

        COLS = 2
        for col in range(COLS):
            self._tiles_frame.columnconfigure(col, weight=1)

        for idx, inst in enumerate(instruments):
            symbol = inst["symbol"]
            name   = inst.get("name", symbol)
            row    = idx // COLS
            col    = idx % COLS

            tile = tk.Frame(self._tiles_frame, bg=BG2,
                            highlightbackground=GRAY, highlightthickness=1,
                            padx=6, pady=5)
            tile.grid(row=row, column=col, padx=3, pady=3, sticky="nsew")

            name_lbl = tk.Label(tile, text=name, bg=BG2, fg=FG,
                                font=("Segoe UI", 8, "bold"),
                                anchor="w", wraplength=130)
            name_lbl.pack(fill="x")
            tk.Label(tile, text=symbol, bg=BG2, fg=GRAY,
                     font=("Segoe UI", 7), anchor="w").pack(fill="x")

            price_lbl = tk.Label(tile, text="—", bg=BG2, fg=FG,
                                  font=("Segoe UI", 11, "bold"), anchor="w")
            price_lbl.pack(fill="x")

            change_lbl = tk.Label(tile, text="—", bg=BG2, fg=GRAY,
                                   font=("Segoe UI", 8), anchor="w")
            change_lbl.pack(fill="x")

            spark = tk.Canvas(tile, bg=BG2, height=26, width=130,
                               highlightthickness=0)
            spark.pack(fill="x", pady=(3, 0))

            self._tile_widgets[symbol] = {
                "frame":      tile,
                "name_lbl":   name_lbl,
                "price_lbl":  price_lbl,
                "change_lbl": change_lbl,
                "spark":      spark,
            }
            self._bind_tile_events(tile, symbol)

    def _update_price_tiles(self, market_data):
        all_tile_dicts = [self._tile_widgets]
        if self._market_popup_tile_widgets:
            all_tile_dicts.append(self._market_popup_tile_widgets)

        for tile_dict in all_tile_dicts:
            for symbol, w in tile_dict.items():
                d = market_data.get(symbol, {})
                if "error" in d:
                    w["price_lbl"].configure(text="N/A", fg=GRAY)
                    w["change_lbl"].configure(text=d["error"][:22], fg=GRAY)
                    w["frame"].configure(highlightbackground=GRAY)
                    continue

                price      = d.get("price", 0)
                change_pct = d.get("change_pct", 0)
                sparkline  = d.get("sparkline", [])
                is_up      = change_pct >= 0
                color      = GREEN if is_up else RED
                arrow      = "▲" if is_up else "▼"

                if price >= 10000:
                    price_str = f"{price:,.0f}"
                elif price >= 100:
                    price_str = f"{price:,.2f}"
                elif price >= 1:
                    price_str = f"{price:.4f}"
                else:
                    price_str = f"{price:.6f}"

                w["price_lbl"].configure(text=price_str, fg=FG)
                w["change_lbl"].configure(
                    text=f"{arrow} {change_pct:+.2f}%", fg=color)
                w["frame"].configure(
                    highlightbackground=color if abs(change_pct) > 0.3 else GRAY)

                # Efekt flash na nazwie gdy cena się zmieniła
                prev = self._prev_prices.get(symbol)
                if prev is not None and prev != price and "name_lbl" in w:
                    flash_col = "#1e3028" if price > prev else "#30181e"
                    self._flash_name_lbl(w["name_lbl"], flash_col)
                self._prev_prices[symbol] = price

                if sparkline:
                    self._draw_sparkline(w["spark"], sparkline, color)

    def _flash_name_lbl(self, lbl, color):
        """Podświetla etykietę nazwy na chwilę, potem przywraca tło BG2."""
        try:
            lbl.configure(bg=color)
            lbl.after(500, lambda: lbl.configure(bg=BG2))
        except tk.TclError:
            pass

    def _draw_sparkline(self, canvas_w, data, color):
        canvas_w.update_idletasks()
        w = canvas_w.winfo_width() or 130
        h = canvas_w.winfo_height() or 26
        canvas_w.delete("all")
        if len(data) < 2:
            return
        mn, mx = min(data), max(data)
        rng = mx - mn
        if rng == 0:
            canvas_w.create_line(2, h // 2, w - 2, h // 2,
                                  fill=color, width=1.5)
            return
        margin = 2
        pts = []
        for i, v in enumerate(data):
            x = margin + int(i / (len(data) - 1) * (w - 2 * margin))
            y = (h - margin) - int((v - mn) / rng * (h - 2 * margin))
            pts.extend([x, y])
        canvas_w.create_line(pts, fill=color, width=1.5, smooth=True)

    # ── Tile click handling (single → profile, double → charts) ──

    def _bind_tile_events(self, widget, symbol):
        """Bind click + cursor on tile and all its children."""
        handler = lambda e, s=symbol: self._on_tile_click(s)
        widget.bind("<Button-1>", handler)
        right_handler = lambda e, s=symbol: self._on_tile_right_click(s, e)
        widget.bind("<Button-3>", right_handler)
        try:
            widget.configure(cursor="hand2")
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._bind_tile_events(child, symbol)

    def _on_tile_right_click(self, symbol, event):
        """Show context menu on right-click over an instrument tile."""
        instruments = self.config_data.get("instruments", [])
        inst_cfg = next((i for i in instruments if i["symbol"] == symbol), None)
        name = inst_cfg["name"] if inst_cfg else symbol

        menu = tk.Menu(self, tearoff=0, bg=BG2, fg=FG,
                       activebackground=ACCENT, activeforeground=BG,
                       font=("Segoe UI", 10), relief="flat", bd=0)
        menu.add_command(
            label=f"💼  Dodaj do portfela — {name}",
            command=lambda: self._open_add_to_portfolio_dialog(symbol)
        )
        menu.tk_popup(event.x_root, event.y_root)

    def _show_toast(self, message, color=None, duration=2500):
        """Show a subtle auto-disappearing notification in the bottom-right corner."""
        if color is None:
            color = GREEN

        # Destroy previous toast if still visible
        existing = getattr(self, "_toast_frame", None)
        if existing:
            try:
                existing.destroy()
            except tk.TclError:
                pass

        toast = tk.Frame(self, bg=BG2,
                         highlightbackground=color, highlightthickness=1,
                         padx=14, pady=10)

        inner = tk.Frame(toast, bg=BG2)
        inner.pack()
        tk.Label(inner, text="✓", bg=BG2, fg=color,
                 font=("Segoe UI", 13, "bold")).pack(side="left", padx=(0, 10))
        tk.Label(inner, text=message, bg=BG2, fg=FG,
                 font=("Segoe UI", 10), wraplength=300,
                 justify="left").pack(side="left")

        toast.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=-20)
        self._toast_frame = toast

        def _hide():
            try:
                toast.destroy()
            except tk.TclError:
                pass
        self.after(duration, _hide)

    def _on_tile_click(self, symbol):
        """Differentiate single-click (profile) from double-click (chart)."""
        if self._click_pending and self._click_symbol == symbol:
            # Second click on same tile → double-click
            self.after_cancel(self._click_pending)
            self._click_pending = None
            self._click_symbol = None
            self._navigate_to_chart(symbol)
        else:
            if self._click_pending:
                self.after_cancel(self._click_pending)
            self._click_symbol = symbol
            self._click_pending = self.after(
                300, lambda: self._on_tile_single_click(symbol))

    def _on_tile_single_click(self, symbol):
        self._click_pending = None
        self._click_symbol = None
        self._open_instrument_profile(symbol)

    def _navigate_to_chart(self, symbol):
        """CEL 3: Switch to Charts tab, set instrument and draw 6M chart."""
        self.notebook.select(self.tab_charts)
        self.chart_symbol_var.set(symbol)
        self._select_period("6M")
        self._draw_chart()

    # ── Instrument profile window (CEL 2) ────────────────────

    def _open_instrument_profile(self, symbol):
        """Open a Toplevel with static AI profile + dynamic trend analysis."""
        inst = None
        for i in self.config_data.get("instruments", []):
            if i["symbol"] == symbol:
                inst = i
                break
        if not inst:
            return

        name = inst.get("name", symbol)
        category = inst.get("category", "Inne")
        source = inst.get("source", "yfinance")

        win = tk.Toplevel(self)
        win.title(f"Profil: {name} ({symbol})")
        win.geometry("760x720")
        win.minsize(520, 480)
        win.configure(bg=BG)
        win.transient(self)

        # Header
        tk.Label(win, text=name, bg=BG, fg=ACCENT,
                 font=("Segoe UI", 14, "bold")
                 ).pack(padx=16, pady=(12, 0), anchor="w")
        tk.Label(win, text=f"{symbol}  •  {category}  •  {source}",
                 bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)
                 ).pack(padx=16, pady=(0, 8), anchor="w")

        # ── PanedWindow: resizable split between profile and trend ──
        profile_paned = tk.PanedWindow(
            win, orient="vertical", bg=BG,
            sashwidth=6, sashrelief="raised", sashpad=2)
        profile_paned.pack(fill="both", expand=True, padx=16, pady=(8, 16))

        # ── Section A: AI Profile (persistent cache) ──
        profile_section = tk.Frame(profile_paned, bg=BG)
        profile_paned.add(profile_section, minsize=120)

        tk.Label(profile_section, text="Profil instrumentu (AI)", bg=BG,
                 fg=ACCENT, font=("Segoe UI", 11, "bold")
                 ).pack(pady=(0, 2), anchor="w")
        tk.Frame(profile_section, bg=GRAY, height=1
                 ).pack(fill="x", pady=(0, 4))

        # btn_frame PRZED display — dzięki temu expand=True na display
        # nie wyciska przycisku poza widoczny obszar
        btn_frame = tk.Frame(profile_section, bg=BG)
        btn_frame.pack(side="bottom", fill="x", pady=(4, 0))

        profile_status = tk.Label(btn_frame, text="", bg=BG, fg=YELLOW,
                                  font=("Segoe UI", 8))
        profile_status.pack(side="right")

        refresh_btn = tk.Button(
            btn_frame, text="🔄 Odśwież opis (AI)", bg=BTN_BG, fg=YELLOW,
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            padx=8, pady=2)
        refresh_btn.pack(side="left")

        profile_display = scrolledtext.ScrolledText(
            profile_section, bg=BG2, fg=FG, font=("Segoe UI", 10),
            relief="flat", wrap="word", state="disabled")
        profile_display.pack(fill="both", expand=True)
        setup_markdown_tags(profile_display)

        # ── Section B: Dynamic trend (no AI) ──
        trend_section = tk.Frame(profile_paned, bg=BG)
        profile_paned.add(trend_section, minsize=120)

        tk.Label(trend_section, text="Aktualna sytuacja", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 11, "bold")
                 ).pack(pady=(0, 2), anchor="w")
        tk.Frame(trend_section, bg=GRAY, height=1
                 ).pack(fill="x", pady=(0, 4))

        trend_display = scrolledtext.ScrolledText(
            trend_section, bg=BG2, fg=FG, font=("Segoe UI", 10),
            relief="flat", wrap="word", state="disabled")
        trend_display.pack(fill="both", expand=True)

        # Ustaw sash po wyrenderowaniu: profil ~65%, trend ~35%
        def _set_sash():
            h = profile_paned.winfo_height()
            if h > 10:
                profile_paned.sash_place(0, 0, int(h * 0.62))
        win.after(80, _set_sash)

        # ── Helpers ──
        def _set_text(widget, text, use_markdown=False):
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            if use_markdown:
                insert_markdown(widget, text)
            else:
                widget.insert("end", text)
            widget.configure(state="disabled")

        # ── Background loader ──
        def _load():
            # A) cached AI profile
            cached = get_instrument_profile(symbol)
            if cached:
                self.after(0, lambda: _set_text(
                    profile_display, cached[0], use_markdown=True))
                self.after(0, lambda: profile_status.configure(
                    text=f"Wygenerowano: {cached[1]}"))
            else:
                self.after(0, lambda: _set_text(
                    profile_display,
                    "Brak profilu. Kliknij \"Odśwież opis (AI)\" "
                    "aby wygenerować."))

            # B) dynamic trend (no AI tokens)
            trend = self._compute_trend_summary(symbol, source)
            self.after(0, lambda: _set_text(trend_display, trend))

        # ── AI refresh ──
        def _refresh_ai():
            refresh_btn.configure(state="disabled", text="⏳ Generuję…")

            def _gen():
                try:
                    text = generate_instrument_profile(
                        self.config_data, symbol, name, category)
                    save_instrument_profile(symbol, text)
                    self.after(0, lambda: _set_text(
                        profile_display, text, use_markdown=True))
                    self.after(0, lambda: profile_status.configure(
                        text="Właśnie wygenerowano"))
                except Exception as exc:
                    self.after(0, lambda: _set_text(
                        profile_display, f"Błąd generowania: {exc}"))
                finally:
                    self.after(0, lambda: refresh_btn.configure(
                        state="normal", text="🔄 Odśwież opis (AI)"))

            threading.Thread(target=_gen, daemon=True).start()

        refresh_btn.configure(command=_refresh_ai)
        threading.Thread(target=_load, daemon=True).start()

    def _compute_trend_summary(self, symbol, source):
        """Compute trend summary using heuristics — no AI tokens."""
        import pandas as pd
        lines = ["Zmiana ceny:\n"]

        for period, label in [("1T", "1 dzień"), ("5T", "5 dni"),
                               ("1M", "1 miesiąc")]:
            try:
                hist = fetch_chart_data(symbol, period, source)
                if hist is None or hist.empty:
                    lines.append(f"  {label}: brak danych")
                    continue
                closes = pd.to_numeric(
                    hist["Close"], errors="coerce").dropna()
                if len(closes) < 2:
                    lines.append(f"  {label}: za mało danych")
                    continue

                first = float(closes.iloc[0])
                last = float(closes.iloc[-1])
                change_pct = ((last - first) / first * 100) if first else 0

                if change_pct > 0.1:
                    direction = "↑"
                elif change_pct < -0.1:
                    direction = "↓"
                else:
                    direction = "→"

                mean = float(closes.mean())
                vol = float(closes.std() / mean * 100) if mean else 0
                vol_label = ("niska" if vol < 1
                             else "średnia" if vol < 3
                             else "wysoka")

                high = float(closes.max())
                low = float(closes.min())

                lines.append(
                    f"  {label}:  {direction} {change_pct:+.2f}%  |  "
                    f"zmienność: {vol_label} ({vol:.1f}%)  |  "
                    f"zakres: {low:.2f} – {high:.2f}")
            except (ValueError, TypeError, KeyError, IndexError):
                lines.append(f"  {label}: błąd pobierania danych")

        # Momentum from 1M data
        try:
            hist = fetch_chart_data(symbol, "1M", source)
            if hist is not None and not hist.empty:
                import pandas as pd
                closes = pd.to_numeric(
                    hist["Close"], errors="coerce").dropna()
                if len(closes) >= 10:
                    recent = float(closes.iloc[-5:].mean())
                    earlier = float(closes.iloc[-10:-5].mean())
                    if recent > earlier * 1.005:
                        mom = "rosnące"
                    elif recent < earlier * 0.995:
                        mom = "malejące"
                    else:
                        mom = "neutralne"
                    lines.append(f"\n  Momentum (1M): {mom}")
        except (ValueError, TypeError, KeyError, IndexError):
            pass

        return "\n".join(lines) if lines else "Brak danych do analizy trendu."

    # ═══════════════════════════════════════
    # PORTFOLIO TAB
    # ═══════════════════════════════════════
    def _build_portfolio_tab(self):
        self._port_widgets = {}   # {tab_type: {tree, status, summary, ...}}

        port_nb = ttk.Notebook(self.tab_portfolio)
        port_nb.pack(fill="both", expand=True, padx=8, pady=8)
        self._port_sub_nb = port_nb   # used by _get_active_port_type()

        # (tab_type, label, add_btn_label, price_field_label, is_sell)
        # is_sell=True → "Cena sprzedaży" label; P&L shows locked gain (buy→sell)
        tabs = [
            ("obserwowane", "  👁  Obserwowane  ", "➕ Obserwuj",     "Cena zakupu:", False),
            ("zakupione",   "  📈 Gra na wzrosty  ",  "➕ Dodaj zakup",  "Cena zakupu:", False),
            ("sprzedane",   "  📉 Gra na spadki  ",  "➕ Dodaj sprzedaż", "Cena sprzedaży:", True),
        ]
        self._port_tab_types = [t[0] for t in tabs]
        for tab_type, label, btn_lbl, price_lbl, is_sell in tabs:
            frame = tk.Frame(port_nb, bg=BG)
            port_nb.add(frame, text=label)
            self._build_portfolio_subtab(frame, tab_type, btn_lbl, price_lbl, is_sell)

    def _get_active_port_type(self):
        """Returns tab_type of the currently visible portfolio sub-tab."""
        idx = self._port_sub_nb.index(self._port_sub_nb.select())
        return self._port_tab_types[idx]

    def _build_portfolio_subtab(self, parent, tab_type, btn_label, price_field_lbl, is_sell):
        """Builds one portfolio sub-tab (form + treeview + bottom bar)."""
        w = {"is_sell": is_sell}
        self._port_widgets[tab_type] = w

        # ── Add form ──
        form_frame = tk.LabelFrame(
            parent, text=" Dodaj pozycję ", bg=BG, fg=ACCENT,
            font=("Segoe UI", 10, "bold"), relief="flat",
            highlightbackground=GRAY, highlightthickness=1)
        form_frame.pack(fill="x", padx=12, pady=(10, 4))

        inner = tk.Frame(form_frame, bg=BG)
        inner.pack(fill="x", padx=8, pady=6)

        def lbl(text):
            tk.Label(inner, text=text, bg=BG, fg=FG,
                     font=("Segoe UI", 9)).pack(side="left", padx=(8, 2))

        lbl("Instrument:")
        all_inst = self.config_data.get("instruments", [])
        inst_names = [f"{i['name']} ({i['symbol']})" for i in all_inst]
        w["v_inst"] = tk.StringVar(value=inst_names[0] if inst_names else "")
        w["inst_cb"] = ttk.Combobox(
            inner, textvariable=w["v_inst"],
            values=inst_names, width=24, state="readonly")
        w["inst_cb"].pack(side="left", padx=(0, 8))

        lbl("Ilość:")
        w["v_qty"] = tk.StringVar()
        tk.Entry(inner, textvariable=w["v_qty"], bg=BG2, fg=FG,
                 insertbackground=FG, relief="flat", width=10,
                 font=("Segoe UI", 10),
                 highlightbackground=GRAY, highlightthickness=1
                 ).pack(side="left", padx=(0, 8))

        lbl(price_field_lbl)
        w["v_price"] = tk.StringVar()
        tk.Entry(inner, textvariable=w["v_price"], bg=BG2, fg=FG,
                 insertbackground=FG, relief="flat", width=12,
                 font=("Segoe UI", 10),
                 highlightbackground=GRAY, highlightthickness=1
                 ).pack(side="left", padx=(0, 4))

        w["v_currency"] = tk.StringVar(value="USD")
        ttk.Combobox(
            inner, textvariable=w["v_currency"],
            values=["USD", "PLN", "EUR"], width=5, state="readonly"
        ).pack(side="left", padx=(0, 4))

        w["btn_price"] = tk.Button(
            inner, text="Aktualna", bg=BTN_BG, fg=ACCENT,
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            padx=6, pady=2,
            command=lambda t=tab_type: self._fill_current_price(t))
        w["btn_price"].pack(side="left", padx=(0, 8))

        tk.Button(
            inner, text=btn_label, bg=GREEN, fg=BG,
            font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
            padx=10, pady=3,
            command=lambda t=tab_type: self._add_portfolio_position(t)
        ).pack(side="left", padx=4)

        # ── Treeview ──
        tree_frame = tk.Frame(parent, bg=BG)
        tree_frame.pack(fill="both", expand=True, padx=12, pady=4)

        entry_col = "Sprzed." if is_sell else "Kup."
        cols = ("Instrument", "Symbol", "Ilość", "Waluta",
                entry_col, f"{entry_col} ($)", "Akt.",
                "Wartość", "Zysk", "Zysk %")
        w["tree"] = ttk.Treeview(
            tree_frame, columns=cols, show="headings", height=16)

        widths  = [120, 70, 55, 45, 85, 85, 150, 155, 155, 65]
        anchors = ["w", "center", "e", "center", "e", "e", "e", "e", "e", "e"]
        for col, cw, anc in zip(cols, widths, anchors):
            w["tree"].heading(col, text=col)
            w["tree"].column(col, width=cw, anchor=anc)

        w["tree"].tag_configure("profit", foreground=GREEN)
        w["tree"].tag_configure("loss",   foreground=RED)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                             command=w["tree"].yview)
        w["tree"].configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        w["tree"].pack(fill="both", expand=True)
        self._bind_mousewheel(w["tree"], w["tree"])

        # ── Bottom bar ──
        bot = tk.Frame(parent, bg=BG2,
                       highlightbackground=GRAY, highlightthickness=1)
        bot.pack(fill="x", padx=12, pady=(0, 8))

        tk.Button(
            bot, text="🗑️ Usuń zaznaczony", bg=BTN_BG, fg=RED,
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            padx=8, pady=4,
            command=lambda t=tab_type: self._remove_portfolio_position(t)
        ).pack(side="left", padx=8, pady=6)

        tk.Button(
            bot, text="🔄 Odśwież ceny", bg=BTN_BG, fg=ACCENT,
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            padx=8, pady=4,
            command=lambda t=tab_type: self._quick_fetch_prices(t)
        ).pack(side="left", padx=4, pady=6)

        w["status"] = tk.Label(
            bot, text="", bg=BG2, fg=SUBTEXT, font=("Segoe UI", 9))
        w["status"].pack(side="left", padx=12)

        w["summary"] = tk.Label(
            bot, text="", bg=BG2, fg=FG,
            font=("Segoe UI", 10, "bold"), anchor="e")
        w["summary"].pack(side="right", padx=16, pady=6)

        self._refresh_portfolio(tab_type)

    def _add_portfolio_position(self, tab_type):
        pw        = self._port_widgets[tab_type]
        inst_str  = pw["v_inst"].get()
        qty_str   = pw["v_qty"].get().strip()
        price_str = pw["v_price"].get().strip()
        currency  = pw["v_currency"].get()

        if not inst_str or not qty_str or not price_str:
            messagebox.showwarning(
                "Brak danych", "Wypełnij wszystkie pola przed dodaniem pozycji.")
            return
        try:
            qty   = float(qty_str.replace(",", "."))
            price = float(price_str.replace(",", "."))
            assert qty > 0 and price > 0
        except (ValueError, AssertionError):
            messagebox.showerror(
                "Błąd", "Ilość i cena zakupu muszą być liczbami > 0.")
            return

        fx_rate = get_fx_to_usd(currency)
        if fx_rate is None:
            messagebox.showwarning(
                "Brak kursu FX",
                f"Nie udało się pobrać kursu {currency}→USD.\n"
                "Sprawdź połączenie z internetem i spróbuj ponownie.")
            return

        symbol = inst_str.split("(")[-1].rstrip(")")
        name   = inst_str.split("(")[0].strip()
        add_portfolio_position(symbol, name, qty, price,
                               buy_currency=currency,
                               buy_fx_to_usd=fx_rate,
                               tab_type=tab_type)
        pw["v_qty"].set("")
        pw["v_price"].set("")
        self._refresh_portfolio(tab_type)

    def _fill_current_price(self, tab_type):
        """Fetch current price for selected instrument and fill the buy-price field."""
        pw       = self._port_widgets[tab_type]
        inst_str = pw["v_inst"].get()
        if not inst_str:
            messagebox.showwarning("Brak instrumentu",
                                   "Wybierz instrument z listy.")
            return

        symbol   = inst_str.split("(")[-1].rstrip(")")
        currency = pw["v_currency"].get()

        d = self.current_market_data.get(symbol, {})
        price_usd = d.get("price") if d and "error" not in d else None

        if price_usd is None:
            pw["btn_price"].configure(state="disabled", text="…")

            def _fetch():
                try:
                    instruments = self.config_data.get("instruments", [])
                    inst_cfg = next(
                        (i for i in instruments if i["symbol"] == symbol), None)
                    if inst_cfg:
                        source = inst_cfg.get("source", "yfinance")
                        name   = inst_cfg.get("name", symbol)
                        from modules.market_data import (
                            get_yfinance_data, get_coingecko_data, get_stooq_data)
                        if source == "coingecko":
                            result = get_coingecko_data(symbol.lower(), name)
                        elif source == "stooq":
                            result = get_stooq_data(symbol, name)
                        else:
                            result = get_yfinance_data(symbol, name)
                        if "error" not in result and result.get("price"):
                            self.current_market_data[symbol] = result
                            self.after(0, lambda: self._apply_current_price(
                                result["price"], currency, tab_type))
                            return
                    self.after(0, lambda: messagebox.showwarning(
                        "Brak ceny", "Brak aktualnej ceny dla instrumentu."))
                except (KeyError, ValueError, TypeError, ConnectionError) as e:
                    logging.getLogger(__name__).debug("Price fetch failed: %s", e)
                    self.after(0, lambda: messagebox.showwarning(
                        "Brak ceny", "Brak aktualnej ceny dla instrumentu."))
                finally:
                    self.after(0, lambda: pw["btn_price"].configure(
                        state="normal", text="Aktualna"))

            threading.Thread(target=_fetch, daemon=True).start()
            return

        self._apply_current_price(price_usd, currency, tab_type)

    def _apply_current_price(self, price_usd, currency, tab_type):
        """Set buy-price field, converting from USD if needed."""
        pw = self._port_widgets[tab_type]
        if currency == "USD":
            pw["v_price"].set(f"{price_usd:.4f}")
            return
        fx = get_fx_to_usd(currency)
        if fx is None or fx == 0:
            messagebox.showwarning(
                "Brak kursu FX",
                f"Brak kursu FX, nie można przeliczyć na {currency}.")
            return
        pw["v_price"].set(f"{price_usd / fx:.4f}")

    def _remove_portfolio_position(self, tab_type):
        tree = self._port_widgets[tab_type]["tree"]
        sel  = tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Usuń pozycję",
                                "Usunąć wybraną pozycję z portfela?"):
            for iid in sel:
                delete_portfolio_position(int(iid))
            self._refresh_portfolio(tab_type)

    def _refresh_portfolio(self, tab_type=None):
        if tab_type is None:
            for t in list(self._port_widgets.keys()):
                self._refresh_portfolio(t)
            return

        pw = self._port_widgets.get(tab_type)
        if not pw:
            return
        tree     = pw["tree"]
        is_sell  = pw.get("is_sell", False)   # Sprzedane: P&L locked (sell-buy)

        for row in tree.get_children():
            tree.delete(row)

        positions      = get_portfolio_positions(tab_type)
        total_invested = 0.0
        total_current  = 0.0

        # Re-use cached FX rates across refreshes (instance-level cache)
        fx_cache = self._fx_cache

        # Per-currency accumulators (non-USD) for summary line
        currency_invested = {}   # {currency: total_invested_local}
        currency_current  = {}   # {currency: total_current_local}

        for pos in positions:
            # Tuple: id, symbol, name, qty, buy_price, created_at,
            #        buy_currency, buy_fx_to_usd, buy_price_usd
            pid        = pos[0]
            symbol     = pos[1]
            name       = pos[2]
            qty        = pos[3]
            buy_price  = pos[4]
            currency   = pos[6] if len(pos) > 6 and pos[6] else "USD"
            fx_rate    = pos[7] if len(pos) > 7 and pos[7] else 1.0
            price_usd  = pos[8] if len(pos) > 8 and pos[8] else (buy_price * fx_rate)

            d = self.current_market_data.get(symbol, {})
            current_price = d.get("price") if d and "error" not in d else None

            invested_usd = qty * price_usd
            total_invested += invested_usd

            # Accumulate invested in original currency for non-USD
            if currency != "USD":
                currency_invested[currency] = (
                    currency_invested.get(currency, 0.0) + qty * buy_price)

            # Format buy price in original currency
            buy_display = f"{buy_price:,.4f}"
            if currency != "USD":
                buy_display += f" {currency}"

            # Get current FX for non-USD positions (for dual display)
            cur_fx = None
            if currency != "USD":
                if currency not in fx_cache:
                    fx_cache[currency] = get_fx_to_usd(currency)
                cur_fx = fx_cache[currency]  # currency→USD rate (or None)

            if current_price is not None:
                current_val = qty * current_price
                # Sprzedane: P&L = sell_price - current (zysk gdy cena spada)
                # Pozostałe: P&L = current - buy_price (zysk gdy cena rośnie)
                pnl_usd = (invested_usd - current_val) if is_sell \
                          else (current_val - invested_usd)
                pnl_pct = (pnl_usd / invested_usd * 100) if invested_usd else 0
                total_current += current_val
                tag = "profit" if pnl_usd >= 0 else "loss"

                # Accumulate current value in local currency
                if currency != "USD" and cur_fx and cur_fx > 0:
                    currency_current[currency] = (
                        currency_current.get(currency, 0.0)
                        + current_val / cur_fx)

                # Format Akt., Wartość, Zysk — dual if non-USD
                if currency != "USD" and cur_fx and cur_fx > 0:
                    price_local = current_price / cur_fx
                    val_local   = current_val / cur_fx
                    pnl_local   = (qty * buy_price - val_local) if is_sell \
                                  else (val_local - qty * buy_price)
                    akt_display = (f"$ {current_price:,.2f} | "
                                   f"{currency} {price_local:,.2f}")
                    val_display = (f"$ {current_val:,.2f} | "
                                   f"{currency} {val_local:,.2f}")
                    pnl_display = (f"$ {pnl_usd:+,.2f} | "
                                   f"{currency} {pnl_local:+,.2f}")
                elif currency != "USD":
                    # FX unavailable — show USD only
                    akt_display = f"$ {current_price:,.2f} | {currency} —"
                    val_display = f"$ {current_val:,.2f} | {currency} —"
                    pnl_display = f"$ {pnl_usd:+,.2f} | {currency} —"
                else:
                    akt_display = f"$ {current_price:,.2f}"
                    val_display = f"$ {current_val:,.2f}"
                    pnl_display = f"$ {pnl_usd:+,.2f}"

                tree.insert(
                    "", "end", iid=str(pid), tags=(tag,),
                    values=(
                        name or symbol, symbol,
                        f"{qty:g}",
                        currency,
                        buy_display,
                        f"{price_usd:,.4f}",
                        akt_display,
                        val_display,
                        pnl_display,
                        f"{pnl_pct:+.2f}%",
                    ))
            else:
                total_current += invested_usd
                tree.insert(
                    "", "end", iid=str(pid),
                    values=(name or symbol, symbol,
                            f"{qty:g}", currency,
                            buy_display, f"{price_usd:,.4f}",
                            "N/A", "—", "—", "—"))

        # P&L w podsumowaniu też odwrócony dla Sprzedane
        total_pnl = (total_invested - total_current) if is_sell \
                    else (total_current - total_invested)
        total_pct = (total_pnl / total_invested * 100) if total_invested else 0
        clr = GREEN if total_pnl >= 0 else RED

        entry_lbl = "Sprzedano" if is_sell else "Zainwestowano"
        inv_parts = f"$ {total_invested:,.2f}"
        val_parts = f"$ {total_current:,.2f}"
        pnl_parts = f"{total_pnl:+,.2f} $"
        for cur in sorted(currency_invested):
            inv_local = currency_invested[cur]
            inv_parts += f" ({cur} {inv_local:,.2f})"
            if cur in currency_current:
                cur_val = currency_current[cur]
                cur_pnl = (inv_local - cur_val) if is_sell else (cur_val - inv_local)
                val_parts += f" ({cur} {cur_val:,.2f})"
                pnl_parts += f" ({cur} {cur_pnl:+,.2f})"

        pw["summary"].configure(fg=clr, text=(
            f"{entry_lbl}: {inv_parts}  |  "
            f"Wartość: {val_parts}  |  "
            f"P&L: {pnl_parts} ({total_pct:+.2f}%)"
        ))

    def _quick_fetch_prices(self, tab_type=None):
        # Use passed tab_type or detect active sub-tab
        active = tab_type or self._get_active_port_type()
        status_lbl = self._port_widgets.get(active, {}).get("status")
        if status_lbl:
            status_lbl.configure(text="Pobieranie cen…")
        self.set_busy(True, "Pobieranie cen…")

        def _fetch():
            try:
                data = get_all_instruments(self.config_data.get("instruments", []))
                self.current_market_data.update(data)
                self.after(0, self._refresh_portfolio)
                self.after(0, lambda: self._update_price_tiles(data))
                if status_lbl:
                    self.after(0, lambda: status_lbl.configure(
                        text="Ceny zaktualizowane"))
            except Exception as exc:
                if status_lbl:
                    self.after(0, lambda: status_lbl.configure(
                        text=f"Błąd: {exc}"))
            finally:
                self.set_busy(False, "Gotowy")

        threading.Thread(target=_fetch, daemon=True).start()

    # ── Auto-odświeżanie cen co 5 sekund ──────────────────────
    def _start_price_autorefresh(self):
        self._price_fetch_in_progress = False
        # Opóźniony start – czekamy aż mainloop ruszy
        self.after(2000, self._autorefresh_prices)

    def _autorefresh_prices(self):
        if self._shutting_down:
            return
        if not self._price_fetch_in_progress:
            self._price_fetch_in_progress = True
            threading.Thread(target=self._autorefresh_worker, daemon=True).start()
        self.after(5000, self._autorefresh_prices)

    def _autorefresh_worker(self):
        try:
            data = get_all_instruments(self.config_data.get("instruments", []))
            self.current_market_data.update(data)
            if not self._shutting_down:
                try:
                    self.after(0, lambda: self._update_price_tiles(data))
                    self.after(0, self._refresh_portfolio)
                except RuntimeError:
                    pass
        except Exception:
            pass
        finally:
            self._price_fetch_in_progress = False

    # ═══════════════════════════════════════
    # CALENDAR TAB
    # ═══════════════════════════════════════
    def _build_calendar_tab(self):
        ctrl = tk.Frame(self.tab_calendar, bg=BG)
        ctrl.pack(fill="x", padx=12, pady=8)

        tk.Button(
            ctrl, text="🔄 Odśwież", bg=BTN_BG, fg=FG,
            font=("Segoe UI", 10), relief="flat", cursor="hand2",
            padx=10, pady=4, command=self._load_calendar
        ).pack(side="left")

        tk.Label(ctrl, text="Tydzień:", bg=BG, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left", padx=(16, 4))
        self.cal_week_var = tk.StringVar(value="this")
        for val, lbl in [("this", "Bieżący"), ("next", "Następny")]:
            tk.Radiobutton(
                ctrl, text=lbl, variable=self.cal_week_var, value=val,
                bg=BG, fg=FG, selectcolor=ACCENT, activebackground=BG,
                font=("Segoe UI", 10), command=self._load_calendar
            ).pack(side="left", padx=4)

        tk.Label(ctrl, text="Filtruj:", bg=BG, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left", padx=(16, 4))
        self.cal_filter_var = tk.StringVar(value="Wszystkie")
        filter_cb = ttk.Combobox(
            ctrl, textvariable=self.cal_filter_var, width=12, state="readonly",
            values=["Wszystkie", "🔴 Wysoki", "🟡 Średni", "⚪ Niski"])
        filter_cb.pack(side="left", padx=4)
        filter_cb.bind("<<ComboboxSelected>>",
                       lambda e: self._apply_cal_filter())

        self.cal_status = tk.Label(ctrl, text="", bg=BG, fg=SUBTEXT,
                                   font=("Segoe UI", 9))
        self.cal_status.pack(side="right", padx=8)

        tree_cont = tk.Frame(self.tab_calendar, bg=BG)
        tree_cont.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        cols = ("Data", "Godz.", "Kraj", "Wydarzenie",
                "Znaczenie", "Wpływ", "Prognoza", "Poprz.")
        self.cal_tree = ttk.Treeview(tree_cont, columns=cols, show="headings")

        col_cfg = [
            ("Data",       90,  "center"),
            ("Godz.",      55,  "center"),
            ("Kraj",       55,  "center"),
            ("Wydarzenie", 250, "w"),
            ("Znaczenie",  280, "w"),
            ("Wpływ",      105, "center"),
            ("Prognoza",   80,  "center"),
            ("Poprz.",     80,  "center"),
        ]
        for col, w, anc in col_cfg:
            self.cal_tree.heading(col, text=col)
            self.cal_tree.column(col, width=w, anchor=anc)

        self.cal_tree.tag_configure("high",   foreground=RED)
        self.cal_tree.tag_configure("medium", foreground=YELLOW)
        self.cal_tree.tag_configure("low",    foreground=FG)

        vsb = ttk.Scrollbar(tree_cont, orient="vertical",
                             command=self.cal_tree.yview)
        hsb = ttk.Scrollbar(tree_cont, orient="horizontal",
                             command=self.cal_tree.xview)
        self.cal_tree.configure(yscrollcommand=vsb.set,
                                xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.cal_tree.pack(fill="both", expand=True)

        # Mousewheel scrolling for calendar tree
        self._bind_mousewheel(self.cal_tree, self.cal_tree)

        self.cal_tree.bind("<Double-Button-1>", self._on_cal_event_dblclick)

        self._load_calendar()

    def _load_calendar(self):
        self.cal_status.configure(text="Pobieranie…")
        week_offset = self.cal_week_var.get()   # odczyt w głównym wątku
        self._cal_request_id += 1
        req_id = self._cal_request_id           # kopia dla domknięcia wątku

        def _fetch():
            events, err = fetch_calendar(week_offset)
            # Odrzuć wynik jeśli zdążył przyjść nowszy request
            if req_id != self._cal_request_id:
                return
            self._cal_events = events
            if err:
                self.after(0, lambda: self.cal_status.configure(
                    text=f"Błąd: {err[:60]}"))
            else:
                self.after(0, lambda: self.cal_status.configure(
                    text=f"{len(events)} wydarzeń — "
                         f"{'bieżący' if week_offset == 'this' else 'następny'} tydzień"))
            self.after(0, self._apply_cal_filter)

        threading.Thread(target=_fetch, daemon=True).start()

    def _apply_cal_filter(self):
        for row in self.cal_tree.get_children():
            self.cal_tree.delete(row)

        raw_map = {
            "🔴 Wysoki": "High",
            "🟡 Średni": "Medium",
            "⚪ Niski":  "Low",
        }
        raw_filter = raw_map.get(self.cal_filter_var.get())
        tag_map    = {"High": "high", "Medium": "medium", "Low": "low"}

        for e in self._cal_events:
            if raw_filter and e["impact_raw"] != raw_filter:
                continue
            tag = tag_map.get(e["impact_raw"], "low")
            self.cal_tree.insert("", "end", tags=(tag,), values=(
                e["date"],
                e["time"],
                f"{e['flag']} {e['country']}",
                e["event"],
                e.get("significance", get_event_significance(e["event"])),
                f"{e['impact_icon']} {e['impact_label']}",
                e["forecast"],
                e["previous"],
            ))

    def _on_cal_event_dblclick(self, _event):
        sel = self.cal_tree.selection()
        if not sel:
            return
        iid = sel[0]
        values = self.cal_tree.item(iid, "values")
        # values = (Date, Time, Country, Event, Significance, Impact, Forecast, Previous)
        if not values or len(values) < 4:
            return
        # Odszukaj pełny dict wydarzenie w _cal_events (po dacie + nazwie)
        ev_date = values[0]
        ev_name = values[3]
        event_data = next(
            (e for e in self._cal_events
             if e["date"] == ev_date and e["event"] == ev_name),
            None
        )
        if event_data is None:
            event_data = {
                "date": ev_date, "time": values[1],
                "country": values[2], "event": ev_name,
                "significance": values[4], "impact_label": values[5],
                "impact_icon": "", "impact_raw": "Low",
                "forecast": values[6], "previous": values[7],
                "flag": "",
            }
        self._open_cal_event_popup(event_data)

    def _open_cal_event_popup(self, event_data):
        """Popup z detalami wydarzenia i generowaną na żądanie analizą AI."""
        win = tk.Toplevel(self)
        win.title("Szczegóły wydarzenia")
        win.geometry("780x560")
        win.configure(bg=BG)
        win.transient(self)

        # ── Nagłówek ──
        hdr = tk.Frame(win, bg=BG2, pady=8)
        hdr.pack(fill="x")
        impact_icon = event_data.get("impact_icon", "")
        impact_lbl  = event_data.get("impact_label", "")
        tk.Label(
            hdr,
            text=f"{impact_icon}  {event_data.get('flag', '')} {event_data.get('country', '')}  "
                 f"·  {event_data.get('date', '')}  {event_data.get('time', '')}",
            bg=BG2, fg=SUBTEXT, font=("Segoe UI", 9)
        ).pack(side="left", padx=16)
        tk.Label(
            hdr, text=impact_lbl,
            bg=BG2, fg=(RED if "Wysoki" in impact_lbl else
                        YELLOW if "Średni" in impact_lbl else FG),
            font=("Segoe UI", 9, "bold")
        ).pack(side="right", padx=16)

        # ── Nazwa + znaczenie ──
        info = tk.Frame(win, bg=BG, pady=6)
        info.pack(fill="x", padx=16)
        tk.Label(
            info, text=event_data.get("event", ""),
            bg=BG, fg=FG, font=("Segoe UI", 12, "bold"), wraplength=720, justify="left"
        ).pack(anchor="w")
        sig = event_data.get("significance", "")
        if sig:
            tk.Label(
                info, text=sig,
                bg=BG, fg=SUBTEXT, font=("Segoe UI", 9), wraplength=720, justify="left"
            ).pack(anchor="w", pady=(2, 0))

        # ── Prognoza / poprzedni ──
        meta = tk.Frame(win, bg=BG, pady=4)
        meta.pack(fill="x", padx=16)
        for label, val in [("Prognoza:", event_data.get("forecast", "—")),
                           ("Poprzedni:", event_data.get("previous", "—"))]:
            if val and val != "—":
                tk.Label(meta, text=label, bg=BG, fg=SUBTEXT,
                         font=("Segoe UI", 9)).pack(side="left")
                tk.Label(meta, text=f"  {val}  ", bg=BG, fg=FG,
                         font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 16))

        tk.Frame(win, bg=GRAY, height=1).pack(fill="x", padx=16, pady=6)

        # ── Panel analizy AI ──
        ai_frame = tk.Frame(win, bg=BG)
        ai_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        ai_header = tk.Frame(ai_frame, bg=BG)
        ai_header.pack(fill="x")
        tk.Label(ai_header, text="Analiza AI", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(side="left")

        event_key = f"{event_data.get('date')}|{event_data.get('event', '')}"
        cached = self._cal_analysis_cache.get(event_key)

        ai_text = scrolledtext.ScrolledText(
            ai_frame, bg=BG2, fg=FG, font=("Segoe UI", 10),
            relief="flat", wrap="word", state="disabled",
            insertbackground=FG, height=14
        )
        ai_text.pack(fill="both", expand=True, pady=(6, 0))
        setup_markdown_tags(ai_text)

        def _set_text(content):
            ai_text.configure(state="normal")
            ai_text.delete("1.0", "end")
            insert_markdown(ai_text, content)
            ai_text.configure(state="disabled")

        if cached:
            _set_text(cached)

        def _generate():
            gen_btn.configure(state="disabled", text="Generowanie…")
            ai_text.configure(state="normal")
            ai_text.delete("1.0", "end")
            ai_text.insert("end", "Generowanie analizy…")
            ai_text.configure(state="disabled")

            def _run():
                result = generate_calendar_event_analysis(
                    self.config_data, event_data)
                self._cal_analysis_cache[event_key] = result
                self.after(0, lambda: (
                    _set_text(result),
                    gen_btn.configure(state="normal", text="🔄 Generuj ponownie")
                ))

            threading.Thread(target=_run, daemon=True).start()

        gen_btn = tk.Button(
            ai_header,
            text="Generuj analizę AI" if not cached else "🔄 Generuj ponownie",
            bg=BTN_BG, fg=ACCENT,
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            padx=10, pady=2, command=_generate
        )
        gen_btn.pack(side="right")

        # ── Stopka ──
        tk.Button(
            win, text="Zamknij", bg=BTN_BG, fg=FG,
            font=("Segoe UI", 10), relief="flat", cursor="hand2",
            padx=14, pady=5, command=win.destroy
        ).pack(side="bottom", pady=8)

    # ═══════════════════════════════════════
    # CHARTS TAB
    # ═══════════════════════════════════════
    def _build_charts_tab(self):
        ctrl = tk.Frame(self.tab_charts, bg=BG)
        ctrl.pack(fill="x", padx=12, pady=8)

        tk.Label(ctrl, text="Instrument:", bg=BG, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left")
        all_symbols = [i["symbol"] for i in self.config_data.get("instruments", [])]
        self.chart_symbol_var = tk.StringVar(
            value=all_symbols[0] if all_symbols else "SPY")
        self.chart_sym_cb = ttk.Combobox(
            ctrl, textvariable=self.chart_symbol_var,
            values=all_symbols, width=14, state="readonly")
        self.chart_sym_cb.pack(side="left", padx=6)

        tk.Label(ctrl, text="Okres:", bg=BG, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left", padx=(12, 0))

        self.chart_period_var = tk.StringVar(value="1M")
        self._period_buttons = {}
        for p in ["1T", "5T", "1M", "3M", "6M", "1R", "2R"]:
            btn = tk.Button(
                ctrl, text=p, bg=BTN_BG, fg=FG,
                font=("Segoe UI", 9, "bold"), relief="flat",
                cursor="hand2", padx=8, pady=2,
                command=lambda period=p: self._select_period(period))
            btn.pack(side="left", padx=2)
            self._period_buttons[p] = btn
        # Highlight default
        self._select_period("1M")

        tk.Label(ctrl, text="Porównaj:", bg=BG, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left", padx=(12, 0))
        self.compare_var = tk.StringVar()
        self.compare_cb = ttk.Combobox(
            ctrl, textvariable=self.compare_var,
            values=[""] + all_symbols, width=14, state="readonly")
        self.compare_cb.pack(side="left", padx=6)

        self.show_ma_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            ctrl, text="MA20/50", variable=self.show_ma_var,
            bg=BG, fg=FG, selectcolor=ACCENT, activebackground=BG,
            font=("Segoe UI", 9)
        ).pack(side="left", padx=(12, 0))

        tk.Button(
            ctrl, text="📊 Rysuj", bg=ACCENT, fg=BG,
            font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
            padx=12, pady=4, command=self._draw_chart
        ).pack(side="left", padx=8)

        tk.Button(
            ctrl, text="💼 Do portfela", bg=BTN_BG, fg=GREEN,
            font=("Segoe UI", 9, "bold"), relief="flat", cursor="hand2",
            padx=10, pady=4, command=self._chart_add_to_portfolio
        ).pack(side="left", padx=4)

        # ── PanedWindow: chart (top) + chat (bottom) ──
        self._chart_paned = tk.PanedWindow(
            self.tab_charts, orient="vertical", bg=BG,
            sashwidth=5, sashrelief="flat")
        self._chart_paned.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self.chart_container = tk.Frame(self._chart_paned, bg=BG)
        self._chart_paned.add(self.chart_container, minsize=200)

        # ── Chart chat panel ──
        self.chart_chat_frame = tk.LabelFrame(
            self._chart_paned, text=" Czat o wykresie ", bg=BG, fg=ACCENT,
            font=("Segoe UI", 10, "bold"), relief="flat",
            highlightbackground=GRAY, highlightthickness=1)
        self._chart_paned.add(self.chart_chat_frame, minsize=100)

        # Set initial sash to ~2/3 chart, 1/3 chat after layout is realized
        self._chart_paned.bind("<Map>", self._set_chart_sash, add="+")

        self.chart_chat_display = scrolledtext.ScrolledText(
            self.chart_chat_frame, bg=BG2, fg=FG, font=("Segoe UI", 10),
            relief="flat", wrap="word", state="disabled",
            insertbackground=FG, selectbackground=ACCENT, height=6)
        self.chart_chat_display.pack(fill="both", expand=True, padx=4, pady=(4, 2))
        self.chart_chat_display.tag_configure("user", foreground=ACCENT)
        self.chart_chat_display.tag_configure("assistant", foreground=GREEN)
        self.chart_chat_display.tag_configure("label", foreground=YELLOW,
                                               font=("Segoe UI", 9, "bold"))
        self.chart_chat_display.tag_configure("error", foreground=RED)

        chart_input_bar = tk.Frame(self.chart_chat_frame, bg=BG)
        chart_input_bar.pack(fill="x", padx=4, pady=(0, 6))

        # Pack buttons right-to-left first so they always stay visible
        tk.Button(
            chart_input_bar, text="Wyczyść", bg=BTN_BG, fg=SUBTEXT,
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            padx=8, command=self._clear_chart_chat
        ).pack(side="right", padx=(4, 0))

        self.chart_chat_send_btn = tk.Button(
            chart_input_bar, text="Wyślij", bg=ACCENT, fg=BG,
            font=("Segoe UI", 10, "bold"), relief="flat",
            cursor="hand2", padx=12, command=self._send_chart_chat_message)
        self.chart_chat_send_btn.pack(side="right", padx=(4, 0))

        self.chart_chat_entry = tk.Entry(
            chart_input_bar, bg=BG2, fg=FG, insertbackground=FG,
            relief="flat", font=("Segoe UI", 10),
            highlightbackground=GRAY, highlightthickness=1)
        self.chart_chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.chart_chat_entry.bind("<Return>",
                                    lambda e: self._send_chart_chat_message())

        # Task 1 + 3: markdown tags + click-to-focus for chart chat
        setup_markdown_tags(self.chart_chat_display)
        bind_chat_focus(self.chart_chat_frame, self.chart_chat_entry)

    def _set_dash_sash(self, event=None):
        """Set dashboard PanedWindow sash: analysis ~70%, chat ~30% (min 220px)."""
        self._dash_paned.unbind("<Map>")
        self._dash_paned.update_idletasks()
        h = self._dash_paned.winfo_height()
        if h > 50:
            chat_h = max(220, int(h * 0.30))
            self._dash_paned.sash_place(0, 0, h - chat_h)

    def _set_chart_sash(self, event=None):
        """Set PanedWindow sash so chart gets ~2/3, chat ~1/3."""
        self._chart_paned.unbind("<Map>")
        self._chart_paned.update_idletasks()
        h = self._chart_paned.winfo_height()
        if h > 50:
            self._chart_paned.sash_place(0, 0, int(h * 0.67))

    def _select_period(self, period):
        """Select a time period and visually highlight the active button."""
        self.chart_period_var.set(period)
        for p, btn in self._period_buttons.items():
            if p == period:
                btn.configure(bg=ACCENT, fg=BG)
            else:
                btn.configure(bg=BTN_BG, fg=FG)

    def _draw_chart(self):
        # 1. Close the matplotlib figure FIRST (before destroying Tk widgets)
        fig = self._current_chart_fig
        self._current_chart_fig = None
        if fig is not None:
            try:
                plt.close(fig)
            except (ValueError, RuntimeError):
                pass

        # 2. Now safe to destroy Tk children (canvas, toolbar)
        for w in self.chart_container.winfo_children():
            try:
                w.destroy()
            except tk.TclError:
                pass

        symbol  = self.chart_symbol_var.get()
        period  = self.chart_period_var.get()
        compare = [self.compare_var.get()] if self.compare_var.get() else None

        # Build sources map from instruments config
        sources_map = {}
        for inst in self.config_data.get("instruments", []):
            sources_map[inst["symbol"]] = inst.get("source", "yfinance")

        try:
            canvas, fig = create_price_chart(
                self.chart_container, symbol, period, compare,
                show_ma=self.show_ma_var.get(),
                sources_map=sources_map)
            self._current_chart_fig = fig
        except Exception as exc:
            # Close any partially created figure
            plt.close("all")
            import traceback
            traceback.print_exc()
            tk.Label(self.chart_container, text=f"Błąd wykresu: {exc}",
                     bg=BG, fg=RED, font=("Segoe UI", 11)).pack(pady=20)

    def _refresh_chart_symbols(self):
        symbols = [i["symbol"] for i in self.config_data.get("instruments", [])]
        self.chart_sym_cb["values"] = symbols
        self.compare_cb["values"] = [""] + symbols

    # ── Add instrument to portfolio (shared dialog) ───────────
    def _open_add_to_portfolio_dialog(self, symbol):
        """Open a dialog to add any instrument to the portfolio."""
        instruments = self.config_data.get("instruments", [])
        inst_cfg = next((i for i in instruments if i["symbol"] == symbol), None)
        name = inst_cfg["name"] if inst_cfg else symbol

        popup = tk.Toplevel(self)
        popup.title(f"Dodaj do portfela – {symbol}")
        popup.configure(bg=BG)
        popup.geometry("420x310")
        popup.resizable(False, False)
        popup.transient(self)
        popup.grab_set()

        tk.Label(popup, text=f"📈 {name} ({symbol})", bg=BG, fg=ACCENT,
                 font=("Segoe UI", 12, "bold")).pack(pady=(16, 12))

        form = tk.Frame(popup, bg=BG)
        form.pack(fill="x", padx=24)

        # Target tab selection
        _tab_label_to_type = {
            "Obserwowane":    "obserwowane",
            "Gra na wzrosty": "zakupione",
            "Gra na spadki":  "sprzedane",
        }
        tk.Label(form, text="Dodaj do:", bg=BG, fg=FG,
                 font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", pady=4)
        v_tab = tk.StringVar(value="Gra na wzrosty")
        tab_cb = ttk.Combobox(form, textvariable=v_tab, width=20, state="readonly",
                              values=list(_tab_label_to_type.keys()))
        tab_cb.grid(row=0, column=1, padx=(8, 0), pady=4, sticky="w")

        # Quantity
        tk.Label(form, text="Ilość:", bg=BG, fg=FG,
                 font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", pady=4)
        v_qty = tk.StringVar(value="1")
        tk.Entry(form, textvariable=v_qty, bg=BG2, fg=FG,
                 insertbackground=FG, relief="flat", width=14,
                 font=("Segoe UI", 10),
                 highlightbackground=GRAY, highlightthickness=1
                 ).grid(row=1, column=1, padx=(8, 0), pady=4, sticky="w")

        # Price
        tk.Label(form, text="Cena:", bg=BG, fg=FG,
                 font=("Segoe UI", 10)).grid(row=2, column=0, sticky="w", pady=4)
        v_price = tk.StringVar()
        price_entry = tk.Entry(form, textvariable=v_price, bg=BG2, fg=FG,
                 insertbackground=FG, relief="flat", width=14,
                 font=("Segoe UI", 10),
                 highlightbackground=GRAY, highlightthickness=1)
        price_entry.grid(row=2, column=1, padx=(8, 0), pady=4, sticky="w")
        btn_price = tk.Button(
            form, text="Aktualna", bg=BTN_BG, fg=ACCENT,
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            padx=6, pady=2)
        btn_price.grid(row=2, column=2, padx=(6, 0), pady=4, sticky="w")

        # Currency
        tk.Label(form, text="Waluta:", bg=BG, fg=FG,
                 font=("Segoe UI", 10)).grid(row=3, column=0, sticky="w", pady=4)
        v_currency = tk.StringVar(value="USD")
        ttk.Combobox(form, textvariable=v_currency,
                     values=["USD", "PLN", "EUR"], width=8, state="readonly"
                     ).grid(row=3, column=1, padx=(8, 0), pady=4, sticky="w")

        # Pre-fill current price if available
        d = self.current_market_data.get(symbol, {})
        if d and "error" not in d and d.get("price"):
            v_price.set(str(round(d["price"], 4)))

        btn_bar = tk.Frame(popup, bg=BG)
        btn_bar.pack(fill="x", padx=24, pady=(16, 12))

        def _apply_price(price_usd):
            currency = v_currency.get()
            if currency == "USD":
                v_price.set(f"{price_usd:.4f}")
                return
            fx = get_fx_to_usd(currency)
            if fx is None or fx == 0:
                messagebox.showwarning(
                    "Brak kursu FX",
                    f"Brak kursu FX, nie można przeliczyć na {currency}.",
                    parent=popup)
                return
            v_price.set(f"{price_usd / fx:.4f}")

        def _fetch_price():
            d = self.current_market_data.get(symbol, {})
            price_usd = d.get("price") if d and "error" not in d else None
            if price_usd is not None:
                _apply_price(price_usd)
                return
            btn_price.configure(state="disabled", text="…")

            def _fetch():
                try:
                    if inst_cfg:
                        source = inst_cfg.get("source", "yfinance")
                        iname  = inst_cfg.get("name", symbol)
                        from modules.market_data import (
                            get_yfinance_data, get_coingecko_data, get_stooq_data)
                        if source == "coingecko":
                            result = get_coingecko_data(symbol.lower(), iname)
                        elif source == "stooq":
                            result = get_stooq_data(symbol, iname)
                        else:
                            result = get_yfinance_data(symbol, iname)
                        if "error" not in result and result.get("price"):
                            self.current_market_data[symbol] = result
                            self.after(0, lambda: _apply_price(result["price"]))
                            return
                    self.after(0, lambda: messagebox.showwarning(
                        "Brak ceny", "Brak aktualnej ceny dla instrumentu.",
                        parent=popup))
                except (KeyError, ValueError, TypeError, ConnectionError) as e:
                    logging.getLogger(__name__).debug("Price fetch failed: %s", e)
                    self.after(0, lambda: messagebox.showwarning(
                        "Brak ceny", "Brak aktualnej ceny dla instrumentu.",
                        parent=popup))
                finally:
                    self.after(0, lambda: btn_price.configure(
                        state="normal", text="Aktualna"))

            threading.Thread(target=_fetch, daemon=True).start()

        btn_price.configure(command=_fetch_price)

        def _do_add():
            tab_type = _tab_label_to_type[v_tab.get()]
            qty_str = v_qty.get().strip()
            price_str = v_price.get().strip()
            currency = v_currency.get()

            if not qty_str or not price_str:
                messagebox.showwarning("Brak danych", "Wypełnij ilość i cenę.",
                                       parent=popup)
                return
            try:
                qty = float(qty_str.replace(",", "."))
                price = float(price_str.replace(",", "."))
                assert qty > 0 and price > 0
            except (ValueError, AssertionError):
                messagebox.showerror("Błąd", "Ilość i cena muszą być liczbami > 0.",
                                     parent=popup)
                return

            fx_rate = get_fx_to_usd(currency)
            if fx_rate is None:
                messagebox.showwarning(
                    "Brak kursu FX",
                    f"Nie udało się pobrać kursu {currency}→USD.",
                    parent=popup)
                return

            add_portfolio_position(symbol, name, qty, price,
                                   buy_currency=currency,
                                   buy_fx_to_usd=fx_rate,
                                   tab_type=tab_type)
            self._refresh_portfolio(tab_type)
            popup.destroy()
            self._show_toast(f"{name} ({symbol})\ndodano do zakładki '{v_tab.get()}'.")

        tk.Button(btn_bar, text="✅ Dodaj", bg=GREEN, fg=BG,
                  font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
                  padx=14, pady=6, command=_do_add).pack(side="left")
        tk.Button(btn_bar, text="Anuluj", bg=BTN_BG, fg=FG,
                  font=("Segoe UI", 10), relief="flat", cursor="hand2",
                  padx=14, pady=6, command=popup.destroy).pack(side="right")

    def _chart_add_to_portfolio(self):
        """Open add-to-portfolio dialog for the instrument currently shown in the chart."""
        symbol = self.chart_symbol_var.get()
        if not symbol:
            messagebox.showwarning("Brak instrumentu", "Najpierw wybierz instrument na wykresie.")
            return
        self._open_add_to_portfolio_dialog(symbol)

    # ── Chart chat helpers ─────────────────────────────────────
    def _append_chart_chat(self, label, text, tag):
        self.chart_chat_display.configure(state="normal")
        self.chart_chat_display.insert("end", f"{label}\n", "label")
        if tag == "assistant":
            insert_markdown(self.chart_chat_display, text, base_tag=tag)
        else:
            self.chart_chat_display.insert("end", text, tag)
        self.chart_chat_display.insert("end", "\n\n", tag)
        self.chart_chat_display.configure(state="disabled")
        self.chart_chat_display.see("end")

    def _clear_chart_chat(self):
        self._chart_chat_history.clear()
        self.chart_chat_display.configure(state="normal")
        self.chart_chat_display.delete("1.0", "end")
        self.chart_chat_display.configure(state="disabled")

    def _get_chart_context(self):
        """Build a text summary of the currently displayed chart."""
        symbol = self.chart_symbol_var.get()
        period = self.chart_period_var.get()
        compare = self.compare_var.get()

        # Find instrument name from config
        inst_name = symbol
        source = "yfinance"
        for inst in self.config_data.get("instruments", []):
            if inst["symbol"] == symbol:
                inst_name = inst.get("name", symbol)
                source = inst.get("source", "yfinance")
                break

        period_names = {
            "1T": "1 dzień", "5T": "5 dni", "1M": "1 miesiąc",
            "3M": "3 miesiące", "6M": "6 miesięcy",
            "1R": "1 rok", "2R": "2 lata",
        }
        period_label = period_names.get(period, period)

        lines = [
            f"Instrument: {inst_name} ({symbol})",
            f"Okres wykresu: {period_label}",
            f"Średnie kroczące: {'MA20/MA50 włączone' if self.show_ma_var.get() else 'wyłączone'}",
        ]
        if compare:
            lines.append(f"Porównanie z: {compare}")

        # Fetch latest price data for context
        try:
            hist = fetch_chart_data(symbol, period, source)
            if hist is not None and not hist.empty:
                closes = hist["Close"].dropna()
                if not closes.empty:
                    last = closes.iloc[-1]
                    first = closes.iloc[0]
                    change_pct = ((last - first) / first) * 100
                    high = closes.max()
                    low = closes.min()
                    lines.append(f"Cena aktualna: {last:.2f}")
                    lines.append(f"Cena na początku okresu: {first:.2f}")
                    lines.append(f"Zmiana w okresie: {change_pct:+.2f}%")
                    lines.append(f"Najwyższa cena: {high:.2f}")
                    lines.append(f"Najniższa cena: {low:.2f}")
                    if len(closes) >= 20:
                        ma20 = closes.rolling(20).mean().iloc[-1]
                        lines.append(f"MA20: {ma20:.2f}")
                    if len(closes) >= 50:
                        ma50 = closes.rolling(50).mean().iloc[-1]
                        lines.append(f"MA50: {ma50:.2f}")
                    if "Volume" in hist.columns:
                        avg_vol = hist["Volume"].mean()
                        if avg_vol > 0:
                            lines.append(f"Średni wolumen: {avg_vol:,.0f}")
        except (ValueError, TypeError, KeyError, IndexError) as e:
            logging.getLogger(__name__).debug("Chart stats fetch failed: %s", e)
            lines.append("(Nie udało się pobrać danych cenowych)")

        return "\n".join(lines)

    def _send_chart_chat_message(self):
        msg = self.chart_chat_entry.get().strip()
        if not msg:
            return
        self.chart_chat_entry.delete(0, "end")
        self._append_chart_chat("Ty:", msg, "user")

        self._chart_chat_history.append({"role": "user", "content": msg})
        self.chart_chat_send_btn.configure(state="disabled", text="…")

        def _worker():
            system = self.config_data.get("chart_chat_prompt", "")
            if not system:
                system = "Jesteś asystentem analizy technicznej. Odpowiadaj po polsku."
            system += "\n"

            chart_ctx = self._get_chart_context()
            system += (
                "\nPoniżej znajdują się dane aktualnie wyświetlanego wykresu.\n\n"
                f"--- WYKRES ---\n{chart_ctx}\n--- KONIEC ---"
            )

            # Dołącz raport analizy (bieżący lub ostatni z bazy)
            report_text = self.current_analysis
            if not report_text:
                try:
                    rows = get_reports(limit=1)
                    if rows:
                        full = get_report_by_id(rows[0][0])
                        if full:
                            # kolumna 5 = analysis
                            report_text = full[5] or ""
                except (IndexError, TypeError):
                    pass
            if report_text:
                system += (
                    "\n\nPoniżej znajduje się ostatni raport analizy rynkowej. "
                    "Wykorzystaj go jako dodatkowy kontekst.\n\n"
                    f"--- RAPORT ---\n{report_text}\n--- KONIEC RAPORTU ---"
                )

            try:
                reply = run_chat(
                    self.config_data, list(self._chart_chat_history), system)
            except Exception as exc:
                reply = f"Błąd połączenia: {exc}"
            self._chart_chat_history.append(
                {"role": "assistant", "content": reply})

            self.after(0, lambda: self._append_chart_chat(
                "AI:", reply, "assistant"))
            self.after(0, lambda: self.chart_chat_send_btn.configure(
                state="normal", text="Wyślij"))
            self.after(0, lambda: self.chart_chat_entry.focus_set())

        threading.Thread(target=_worker, daemon=True).start()

    # ═══════════════════════════════════════
    # HISTORY TAB
    # ═══════════════════════════════════════
    def _build_history_tab(self):
        top = tk.Frame(self.tab_history, bg=BG)
        top.pack(fill="x", padx=12, pady=8)
        tk.Button(top, text="🔄 Odśwież", bg=BTN_BG, fg=FG,
                  font=("Segoe UI", 10), relief="flat", cursor="hand2",
                  padx=10, pady=4, command=self._load_history
                  ).pack(side="left")
        tk.Button(top, text="🗑️ Usuń zaznaczony", bg=BTN_BG, fg=RED,
                  font=("Segoe UI", 10), relief="flat", cursor="hand2",
                  padx=10, pady=4, command=self._delete_selected_report
                  ).pack(side="left", padx=8)
        tk.Button(top, text="📄 Eksportuj PDF", bg=BTN_BG, fg=FG,
                  font=("Segoe UI", 10), relief="flat", cursor="hand2",
                  padx=10, pady=4, command=self._export_history_pdf
                  ).pack(side="left", padx=8)

        paned = tk.PanedWindow(self.tab_history, orient="horizontal",
                                bg=BG, sashwidth=4)
        paned.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        list_frame = tk.Frame(paned, bg=BG)
        paned.add(list_frame, minsize=280)

        cols = ("Data", "Model", "Ryzyko")
        self.history_tree = ttk.Treeview(
            list_frame, columns=cols, show="headings", height=20)
        for col in cols:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(
                col, width=140 if col == "Data" else 90)

        hist_vsb = ttk.Scrollbar(list_frame, orient="vertical",
                                  command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=hist_vsb.set)
        hist_vsb.pack(side="right", fill="y")
        self.history_tree.pack(fill="both", expand=True)
        self.history_tree.bind("<<TreeviewSelect>>", self._on_report_select)

        # Mousewheel scrolling for history tree
        self._bind_mousewheel(self.history_tree, self.history_tree)

        preview_frame = tk.Frame(paned, bg=BG)
        paned.add(preview_frame, minsize=400)
        self.report_preview = scrolledtext.ScrolledText(
            preview_frame, bg=BG2, fg=FG, font=("Segoe UI", 10),
            relief="flat", wrap="word", state="disabled")
        self.report_preview.pack(fill="both", expand=True)

        self.history_token_label = tk.Label(
            preview_frame, text="", bg="#16161e", fg="#FFD54F",
            font=("Segoe UI", 8, "bold"), anchor="w")
        self.history_token_label.pack(fill="x", padx=8, pady=(0, 2))

        self._load_history()

    def _load_history(self):
        for row in self.history_tree.get_children():
            self.history_tree.delete(row)
        for r in get_reports(50):
            rid, created, provider, model, risk, _ = r
            self.history_tree.insert(
                "", "end", iid=str(rid),
                values=(created[:16], f"{provider}/{model}", f"{risk}/10"))

    def _on_report_select(self, event):
        sel = self.history_tree.selection()
        if not sel:
            return
        report = get_report_by_id(int(sel[0]))
        if report:
            self.report_preview.configure(state="normal")
            self.report_preview.delete("1.0", "end")
            self.report_preview.insert("end", report[5])
            self.report_preview.configure(state="disabled")
            # Show token info for this report
            created_at = report[1] or ""
            provider = report[2] or ""
            model = report[3] or ""
            inp = report[7] if len(report) > 7 else 0
            out = report[8] if len(report) > 8 else 0
            usage_info = {
                "provider": provider, "model": model,
                "input_tokens": inp or 0, "output_tokens": out or 0,
            }
            self.history_token_label.configure(
                text=self._build_token_cost_line(usage_info))
            # Update dashboard date + token display for selected report
            self._update_token_info(usage_info, report_date=created_at)

    def _delete_selected_report(self):
        sel = self.history_tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Usuń raport",
                                "Czy na pewno usunąć wybrany raport?"):
            delete_report(int(sel[0]))
            self._load_history()

    # ═══════════════════════════════════════
    # SETTINGS TAB
    # ═══════════════════════════════════════
    def _make_scrollable_inner(self, parent):
        """Tworzy przewijalny canvas wewnątrz parent i zwraca ramkę inner."""
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=BG)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")))
        self._bind_mousewheel(canvas, canvas)
        return inner

    def _build_settings_tab(self):
        # Przycisk zapisu na dole (poza notebookiem, zawsze widoczny)
        tk.Button(
            self.tab_settings, text="💾 Zapisz ustawienia", bg=GREEN, fg=BG,
            font=("Segoe UI", 11, "bold"), relief="flat", cursor="hand2",
            padx=20, pady=8, command=self._save_settings
        ).pack(side="bottom", pady=8)

        # Wewnętrzny notebook z podzakładkami
        settings_nb = ttk.Notebook(self.tab_settings)
        settings_nb.pack(fill="both", expand=True, padx=2, pady=(4, 0))

        tab_general     = tk.Frame(settings_nb, bg=BG)
        tab_instruments = tk.Frame(settings_nb, bg=BG)
        tab_prompts     = tk.Frame(settings_nb, bg=BG)

        settings_nb.add(tab_general,     text="  ⚙  Ogólne  ")
        settings_nb.add(tab_instruments, text="  📊  Instrumenty  ")
        settings_nb.add(tab_prompts,     text="  📝  Prompty  ")

        self._settings_nb       = settings_nb
        self._tab_prompts       = tab_prompts
        self._prompts_prev_idx  = 0
        self._prompts_tab_locked = False
        settings_nb.bind("<<NotebookTabChanged>>", self._on_prompts_tab_change)

        inner_general     = self._make_scrollable_inner(tab_general)
        inner_instruments = self._make_scrollable_inner(tab_instruments)
        inner_prompts     = self._make_scrollable_inner(tab_prompts)

        self._settings_inner = inner_general  # compat

        self._build_settings_api_keys(inner_general)
        self._build_settings_ai_model(inner_general)
        self._build_settings_chat_model(inner_general)
        self._build_settings_schedule(inner_general)

        self._build_settings_instruments(inner_instruments)
        self._build_settings_sources(inner_instruments)

        self._build_settings_prompts(inner_prompts)

    # ── Settings sub-builders ─────────────────────────────────────
    @staticmethod
    def _settings_section(parent, text):
        tk.Label(parent, text=text, bg=BG, fg=ACCENT,
                 font=("Segoe UI", 12, "bold")
                 ).pack(anchor="w", padx=16, pady=(16, 4))
        tk.Frame(parent, bg=GRAY, height=1).pack(
            fill="x", padx=16, pady=(0, 8))

    @staticmethod
    def _settings_entry_row(parent, label, var, show=""):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill="x", padx=16, pady=3)
        tk.Label(f, text=label, bg=BG, fg=FG, font=("Segoe UI", 10),
                 width=22, anchor="w").pack(side="left")
        tk.Entry(f, textvariable=var, bg=BG2, fg=FG,
                 insertbackground=FG, relief="flat",
                 font=("Segoe UI", 10), show=show,
                 highlightbackground=GRAY, highlightthickness=1
                 ).pack(side="left", fill="x", expand=True, padx=4)

    def _build_settings_api_keys(self, inner):
        self._settings_section(inner, "🔑 Klucze API")
        self._key_from_env = {}
        for kn in ("newsdata", "openai", "anthropic", "openrouter"):
            from config import ENV_KEY_MAP
            env_name = ENV_KEY_MAP.get(kn, "")
            self._key_from_env[kn] = bool(
                env_name and os.environ.get(env_name, "").strip())

        def _key_display(name):
            val = self.config_data["api_keys"].get(name, "")
            if self._key_from_env[name]:
                return mask_key(val) + " (ENV)"
            return val

        self.v_newsdata  = tk.StringVar(value=_key_display("newsdata"))
        self.v_openai    = tk.StringVar(value=_key_display("openai"))
        self.v_anthropic = tk.StringVar(value=_key_display("anthropic"))
        self.v_openrouter = tk.StringVar(value=_key_display("openrouter"))
        self._settings_entry_row(inner, "Newsdata.io:", self.v_newsdata, show="*")
        self._settings_entry_row(inner, "OpenAI API Key:", self.v_openai, show="*")
        self._settings_entry_row(inner, "Anthropic API Key:", self.v_anthropic, show="*")
        self._settings_entry_row(inner, "OpenRouter API Key:", self.v_openrouter, show="*")

    def _build_settings_ai_model(self, inner):
        self._settings_section(inner, "🤖 Model AI")
        prov_frame = tk.Frame(inner, bg=BG)
        prov_frame.pack(fill="x", padx=16, pady=3)
        tk.Label(prov_frame, text="Dostawca:", bg=BG, fg=FG,
                 font=("Segoe UI", 10), width=22, anchor="w"
                 ).pack(side="left")
        self.v_provider = tk.StringVar(
            value=self.config_data.get("ai_provider", "anthropic"))
        self._provider_buttons = {}
        for p in ["anthropic", "openai", "openrouter"]:
            label = p.capitalize() if p != "openrouter" else "OpenRouter"
            btn = tk.Button(
                prov_frame, text=label,
                font=("Segoe UI", 10, "bold"), relief="flat",
                cursor="hand2", padx=12, pady=4,
                command=lambda pv=p: self._select_provider(pv))
            btn.pack(side="left", padx=4)
            self._provider_buttons[p] = btn
        self._highlight_provider_buttons()

        model_frame = tk.Frame(inner, bg=BG)
        model_frame.pack(fill="x", padx=16, pady=3)
        tk.Label(model_frame, text="Model:", bg=BG, fg=FG,
                 font=("Segoe UI", 10), width=22, anchor="w"
                 ).pack(side="left")
        self.v_model = tk.StringVar(
            value=self.config_data.get("ai_model", "claude-opus-4-6"))
        self.model_cb = ttk.Combobox(
            model_frame, textvariable=self.v_model,
            width=30)
        self.model_cb.pack(side="left", padx=4)

        tk.Label(model_frame, text="lub wpisz:", bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 4))
        self.v_custom_model = tk.StringVar()
        self._custom_model_entry = tk.Entry(
            model_frame, textvariable=self.v_custom_model,
            bg=BG2, fg=FG, insertbackground=FG, relief="flat",
            font=("Segoe UI", 10), width=24,
            highlightbackground=GRAY, highlightthickness=1)
        self._custom_model_entry.pack(side="left", padx=4)
        self._custom_model_entry.bind(
            "<KeyRelease>", lambda e: self._on_custom_model_change())

        self._update_model_list()

    def _build_settings_chat_model(self, inner):
        self._settings_section(inner, "💬 Model Czatu")
        tk.Label(
            inner,
            text="Model używany do dyskusji o raporcie (używa tych samych kluczy API).",
            bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)
        ).pack(anchor="w", padx=16, pady=(0, 4))

        chat_prov_frame = tk.Frame(inner, bg=BG)
        chat_prov_frame.pack(fill="x", padx=16, pady=3)
        tk.Label(chat_prov_frame, text="Dostawca czatu:", bg=BG, fg=FG,
                 font=("Segoe UI", 10), width=22, anchor="w"
                 ).pack(side="left")
        self.v_chat_provider = tk.StringVar(
            value=self.config_data.get("chat_provider", "anthropic"))
        self._chat_provider_buttons = {}
        for p in ["anthropic", "openai", "openrouter"]:
            label = p.capitalize() if p != "openrouter" else "OpenRouter"
            btn = tk.Button(
                chat_prov_frame, text=label,
                font=("Segoe UI", 10, "bold"), relief="flat",
                cursor="hand2", padx=12, pady=4,
                command=lambda pv=p: self._select_chat_provider(pv))
            btn.pack(side="left", padx=4)
            self._chat_provider_buttons[p] = btn
        self._highlight_chat_provider_buttons()

        chat_model_frame = tk.Frame(inner, bg=BG)
        chat_model_frame.pack(fill="x", padx=16, pady=3)
        tk.Label(chat_model_frame, text="Model czatu:", bg=BG, fg=FG,
                 font=("Segoe UI", 10), width=22, anchor="w"
                 ).pack(side="left")
        self.v_chat_model = tk.StringVar(
            value=self.config_data.get("chat_model", "claude-sonnet-4-6"))
        self.chat_model_cb = ttk.Combobox(
            chat_model_frame, textvariable=self.v_chat_model,
            width=30)
        self.chat_model_cb.pack(side="left", padx=4)

        tk.Label(chat_model_frame, text="lub wpisz:", bg=BG, fg=SUBTEXT,
                 font=("Segoe UI", 9)).pack(side="left", padx=(8, 4))
        self.v_chat_custom_model = tk.StringVar()
        self._chat_custom_model_entry = tk.Entry(
            chat_model_frame, textvariable=self.v_chat_custom_model,
            bg=BG2, fg=FG, insertbackground=FG, relief="flat",
            font=("Segoe UI", 10), width=24,
            highlightbackground=GRAY, highlightthickness=1)
        self._chat_custom_model_entry.pack(side="left", padx=4)
        self._chat_custom_model_entry.bind(
            "<KeyRelease>", lambda e: self._on_chat_custom_model_change())

        self._update_chat_model_list()

    def _build_settings_schedule(self, inner):
        self._settings_section(inner, "⏰ Harmonogram")
        sched_frame = tk.Frame(inner, bg=BG)
        sched_frame.pack(fill="x", padx=16, pady=3)
        self.v_sched_enabled = tk.BooleanVar(
            value=self.config_data["schedule"].get("enabled", False))
        tk.Checkbutton(
            sched_frame, text="Włącz automatyczną analizę",
            variable=self.v_sched_enabled, bg=BG, fg=FG,
            selectcolor=ACCENT, activebackground=BG,
            font=("Segoe UI", 10)
        ).pack(side="left")

        times_frame = tk.Frame(inner, bg=BG)
        times_frame.pack(fill="x", padx=16, pady=3)
        tk.Label(times_frame, text="Godziny (HH:MM, przecinek):", bg=BG,
                 fg=FG, font=("Segoe UI", 10), width=28, anchor="w"
                 ).pack(side="left")
        self.v_times = tk.StringVar(
            value=", ".join(
                self.config_data["schedule"].get("times", ["08:00"])))
        tk.Entry(times_frame, textvariable=self.v_times, bg=BG2, fg=FG,
                 insertbackground=FG, relief="flat", font=("Segoe UI", 10),
                 highlightbackground=GRAY, highlightthickness=1
                 ).pack(side="left", fill="x", expand=True, padx=4)

    def _build_settings_instruments(self, inner):
        self._settings_section(inner, "📊 Instrumenty finansowe")
        tk.Label(
            inner,
            text="Symbol: ticker (np. AAPL) lub ID CoinGecko (np. bitcoin). "
                 "Źródło: yfinance / coingecko / stooq",
            bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)
        ).pack(anchor="w", padx=16, pady=(0, 6))

        hdr = tk.Frame(inner, bg=BG)
        hdr.pack(fill="x", padx=16)
        for txt, w in [("Symbol", 12), ("Nazwa", 18),
                       ("Kategoria", 14), ("Źródło", 12)]:
            tk.Label(hdr, text=txt, bg=BG, fg=ACCENT,
                     font=("Segoe UI", 9, "bold"), width=w, anchor="w"
                     ).pack(side="left")

        self.inst_frame = tk.Frame(inner, bg=BG)
        self.inst_frame.pack(fill="x", padx=16, pady=4)
        for inst in self.config_data.get("instruments", []):
            self._add_instrument_row(inst)

        inst_btn_frame = tk.Frame(inner, bg=BG)
        inst_btn_frame.pack(fill="x", padx=16, pady=6)

        tk.Button(
            inst_btn_frame, text="➕ Dodaj instrument", bg=BTN_BG, fg=GREEN,
            font=("Segoe UI", 10), relief="flat", cursor="hand2",
            padx=10, pady=4,
            command=lambda: self._add_instrument_row({})
        ).pack(side="left")

        self._gen_profiles_btn = tk.Button(
            inst_btn_frame, text="🤖 Generuj brakujące opisy AI",
            bg=BTN_BG, fg=YELLOW,
            font=("Segoe UI", 10), relief="flat", cursor="hand2",
            padx=10, pady=4,
            command=self._generate_missing_profiles)
        self._gen_profiles_btn.pack(side="left", padx=(8, 0))

        self._refresh_profiles_btn = tk.Button(
            inst_btn_frame, text="🔄 Odśwież opisy AI",
            bg=BTN_BG, fg=ACCENT,
            font=("Segoe UI", 10), relief="flat", cursor="hand2",
            padx=10, pady=4,
            command=self._refresh_all_profiles)
        self._refresh_profiles_btn.pack(side="left", padx=(8, 0))

        self._gen_profiles_status = tk.Label(
            inst_btn_frame, text="", bg=BG, fg=SUBTEXT,
            font=("Segoe UI", 9))
        self._gen_profiles_status.pack(side="left", padx=(8, 0))

    def _build_settings_sources(self, inner):
        self._settings_section(inner, "🌐 Źródła danych (strony www)")
        tk.Label(
            inner,
            text="Aplikacja pobierze treść z tych stron przed każdą analizą.",
            bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)
        ).pack(anchor="w", padx=16, pady=(0, 6))

        self.sources_frame = tk.Frame(inner, bg=BG)
        self.sources_frame.pack(fill="x", padx=16, pady=4)
        for url in self.config_data.get("sources", []):
            self._add_source_row(url)

        tk.Button(
            inner, text="➕ Dodaj źródło", bg=BTN_BG, fg=GREEN,
            font=("Segoe UI", 10), relief="flat", cursor="hand2",
            padx=10, pady=4, command=lambda: self._add_source_row("")
        ).pack(anchor="w", padx=16, pady=6)

    def _build_settings_prompts(self, inner):
        self._settings_section(inner, "📝 Prompt systemowy")
        _pf1 = tk.Frame(inner, bg=BG)
        _pf1.pack(fill="x", padx=16, pady=(0, 2))
        tk.Button(
            _pf1, text="⛶", bg=BTN_BG, fg=ACCENT,
            font=("Segoe UI", 11), relief="flat", cursor="hand2",
            width=3, command=lambda: self._open_prompt_popup(
                "Prompt systemowy", self.prompt_text)
        ).pack(side="right")
        self.prompt_text = scrolledtext.ScrolledText(
            inner, bg=BG2, fg=FG, font=("Segoe UI", 10), height=10,
            relief="flat", wrap="word", insertbackground=FG)
        self.prompt_text.pack(fill="x", padx=16, pady=4)
        self.prompt_text.insert("end", self.config_data.get("prompt", ""))

        tk.Button(
            inner, text="🔄 Przywróć domyślny prompt", bg=BTN_BG, fg=YELLOW,
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            command=self._reset_prompt
        ).pack(anchor="w", padx=16, pady=2)

        self._settings_section(inner, "💬 Prompt czatu")
        _pf2 = tk.Frame(inner, bg=BG)
        _pf2.pack(fill="x", padx=16, pady=(0, 2))
        tk.Label(
            _pf2,
            text="Instrukcja systemowa dla czatu. Raport z analizy jest "
                 "dołączany automatycznie.",
            bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)
        ).pack(side="left")
        tk.Button(
            _pf2, text="⛶", bg=BTN_BG, fg=ACCENT,
            font=("Segoe UI", 11), relief="flat", cursor="hand2",
            width=3, command=lambda: self._open_prompt_popup(
                "Prompt czatu", self.chat_prompt_text)
        ).pack(side="right")
        self.chat_prompt_text = scrolledtext.ScrolledText(
            inner, bg=BG2, fg=FG, font=("Segoe UI", 10), height=5,
            relief="flat", wrap="word", insertbackground=FG)
        self.chat_prompt_text.pack(fill="x", padx=16, pady=4)
        self.chat_prompt_text.insert(
            "end", self.config_data.get("chat_prompt", ""))

        tk.Button(
            inner, text="🔄 Przywróć domyślny prompt czatu",
            bg=BTN_BG, fg=YELLOW,
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            command=self._reset_chat_prompt
        ).pack(anchor="w", padx=16, pady=2)

        self._settings_section(inner, "📊 Prompt czatu wykresów")
        _pf3 = tk.Frame(inner, bg=BG)
        _pf3.pack(fill="x", padx=16, pady=(0, 2))
        tk.Label(
            _pf3,
            text="Instrukcja systemowa dla czatu na zakładce Wykresy. "
                 "Dane wykresu (symbol, okres, ceny) są dołączane automatycznie.",
            bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)
        ).pack(side="left")
        tk.Button(
            _pf3, text="⛶", bg=BTN_BG, fg=ACCENT,
            font=("Segoe UI", 11), relief="flat", cursor="hand2",
            width=3, command=lambda: self._open_prompt_popup(
                "Prompt czatu wykresów", self.chart_chat_prompt_text)
        ).pack(side="right")
        self.chart_chat_prompt_text = scrolledtext.ScrolledText(
            inner, bg=BG2, fg=FG, font=("Segoe UI", 10), height=5,
            relief="flat", wrap="word", insertbackground=FG)
        self.chart_chat_prompt_text.pack(fill="x", padx=16, pady=4)
        self.chart_chat_prompt_text.insert(
            "end", self.config_data.get("chart_chat_prompt", ""))

        tk.Button(
            inner, text="🔄 Przywróć domyślny prompt czatu wykresów",
            bg=BTN_BG, fg=YELLOW,
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            command=self._reset_chart_chat_prompt
        ).pack(anchor="w", padx=16, pady=2)

        self._settings_section(inner, "🧾 Prompt profilu instrumentu")
        _pf4 = tk.Frame(inner, bg=BG)
        _pf4.pack(fill="x", padx=16, pady=(0, 2))
        tk.Label(
            _pf4,
            text="Instrukcja dla AI przy generowaniu opisu instrumentu. "
                 "Nazwa, symbol i kategoria są dołączane automatycznie.",
            bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)
        ).pack(side="left")
        tk.Button(
            _pf4, text="⛶", bg=BTN_BG, fg=ACCENT,
            font=("Segoe UI", 11), relief="flat", cursor="hand2",
            width=3, command=lambda: self._open_prompt_popup(
                "Prompt profilu instrumentu", self.profile_prompt_text)
        ).pack(side="right")
        self.profile_prompt_text = scrolledtext.ScrolledText(
            inner, bg=BG2, fg=FG, font=("Segoe UI", 10), height=6,
            relief="flat", wrap="word", insertbackground=FG)
        self.profile_prompt_text.pack(fill="x", padx=16, pady=4)
        self.profile_prompt_text.insert(
            "end", self.config_data.get("profile_prompt", ""))

        tk.Button(
            inner, text="🔄 Przywróć domyślny prompt profilu",
            bg=BTN_BG, fg=YELLOW,
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            command=self._reset_profile_prompt
        ).pack(anchor="w", padx=16, pady=2)

        self._settings_section(inner, "📅 Prompt analizy wydarzeń kalendarza")
        _pf5 = tk.Frame(inner, bg=BG)
        _pf5.pack(fill="x", padx=16, pady=(0, 2))
        tk.Label(
            _pf5,
            text="Instrukcja dla AI przy analizie wydarzenia z kalendarza ekonomicznego "
                 "(wywołana przez dwuklik na wierszu w zakładce Kalendarz).",
            bg=BG, fg=SUBTEXT, font=("Segoe UI", 9)
        ).pack(side="left")
        tk.Button(
            _pf5, text="⛶", bg=BTN_BG, fg=ACCENT,
            font=("Segoe UI", 11), relief="flat", cursor="hand2",
            width=3, command=lambda: self._open_prompt_popup(
                "Prompt analizy wydarzeń kalendarza",
                self.calendar_event_prompt_text)
        ).pack(side="right")
        self.calendar_event_prompt_text = scrolledtext.ScrolledText(
            inner, bg=BG2, fg=FG, font=("Segoe UI", 10), height=6,
            relief="flat", wrap="word", insertbackground=FG)
        self.calendar_event_prompt_text.pack(fill="x", padx=16, pady=4)
        self.calendar_event_prompt_text.insert(
            "end", self.config_data.get("calendar_event_prompt", ""))

        tk.Button(
            inner, text="🔄 Przywróć domyślny prompt kalendarza",
            bg=BTN_BG, fg=YELLOW,
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            command=self._reset_calendar_event_prompt
        ).pack(anchor="w", padx=16, pady=2)

    def _add_instrument_row(self, inst=None):
        if inst is None:
            inst = {}
        row_frame = tk.Frame(self.inst_frame, bg=BG)
        row_frame.pack(fill="x", pady=2)

        v_sym  = tk.StringVar(value=inst.get("symbol", ""))
        v_name = tk.StringVar(value=inst.get("name", ""))
        v_cat  = tk.StringVar(value=inst.get("category", "Akcje"))
        v_src  = tk.StringVar(value=inst.get("source", "yfinance"))

        tk.Entry(row_frame, textvariable=v_sym, bg=BG2, fg=FG,
                 insertbackground=FG, relief="flat", font=("Segoe UI", 9),
                 highlightbackground=GRAY, highlightthickness=1,
                 width=12).pack(side="left", padx=(0, 4))
        tk.Entry(row_frame, textvariable=v_name, bg=BG2, fg=FG,
                 insertbackground=FG, relief="flat", font=("Segoe UI", 9),
                 highlightbackground=GRAY, highlightthickness=1,
                 width=18).pack(side="left", padx=(0, 4))
        ttk.Combobox(
            row_frame, textvariable=v_cat, width=12, state="readonly",
            values=["Akcje", "Krypto", "Forex", "Surowce", "Inne"]
        ).pack(side="left", padx=(0, 4))
        ttk.Combobox(
            row_frame, textvariable=v_src, width=10, state="readonly",
            values=["yfinance", "coingecko", "stooq"]
        ).pack(side="left", padx=(0, 4))

        tk.Button(row_frame, text="↑", bg=BTN_BG, fg=FG,
                  font=("Segoe UI", 9), relief="flat", cursor="hand2",
                  padx=4,
                  command=lambda rf=row_frame: self._move_instrument(rf, -1)
                  ).pack(side="left", padx=(4, 0))
        tk.Button(row_frame, text="↓", bg=BTN_BG, fg=FG,
                  font=("Segoe UI", 9), relief="flat", cursor="hand2",
                  padx=4,
                  command=lambda rf=row_frame: self._move_instrument(rf, 1)
                  ).pack(side="left", padx=(0, 2))

        def remove():
            self.inst_entries.remove((row_frame, v_sym, v_name, v_cat, v_src))
            row_frame.destroy()

        tk.Button(row_frame, text="✖", bg=BTN_BG, fg=RED,
                  font=("Segoe UI", 9), relief="flat", cursor="hand2",
                  padx=6, command=remove).pack(side="left")
        self.inst_entries.append((row_frame, v_sym, v_name, v_cat, v_src))

    def _move_instrument(self, row_frame, direction):
        """Move instrument row up (-1) or down (+1) in the list."""
        idx = None
        for i, entry in enumerate(self.inst_entries):
            if entry[0] is row_frame:
                idx = i
                break
        if idx is None:
            return
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self.inst_entries):
            return
        self.inst_entries[idx], self.inst_entries[new_idx] = \
            self.inst_entries[new_idx], self.inst_entries[idx]
        self._repack_instruments()

    def _repack_instruments(self):
        """Repack instrument rows in current list order."""
        for entry in self.inst_entries:
            entry[0].pack_forget()
        for entry in self.inst_entries:
            entry[0].pack(fill="x", pady=2)

    def _generate_missing_profiles(self):
        """Generate AI profiles for all instruments that don't have one yet."""
        instruments = self.config_data.get("instruments", [])
        missing = []
        for inst in instruments:
            sym = inst["symbol"]
            if not get_instrument_profile(sym):
                missing.append(inst)

        if not missing:
            self._gen_profiles_status.configure(
                text="Wszystkie instrumenty mają już opisy.", fg=GREEN)
            return

        total = len(missing)
        self._gen_profiles_btn.configure(state="disabled")
        self._gen_profiles_status.configure(
            text=f"0/{total} — rozpoczynam…", fg=YELLOW)

        def _worker():
            done = 0
            errors = 0
            for inst in missing:
                sym = inst["symbol"]
                name = inst.get("name", sym)
                cat = inst.get("category", "Inne")
                self.after(0, lambda d=done, s=sym: (
                    self._gen_profiles_status.configure(
                        text=f"{d}/{total} — generuję: {s}…")))
                try:
                    text = generate_instrument_profile(
                        self.config_data, sym, name, cat)
                    save_instrument_profile(sym, text)
                    done += 1
                except (ConnectionError, TimeoutError, ValueError, KeyError) as e:
                    logging.getLogger(__name__).debug("Profile gen %s failed: %s", sym, e)
                    errors += 1
                    done += 1

            msg = f"Gotowe: {total - errors}/{total}"
            if errors:
                msg += f"  ({errors} błędów)"
            self.after(0, lambda: self._gen_profiles_status.configure(
                text=msg, fg=GREEN if not errors else YELLOW))
            self.after(0, lambda: self._gen_profiles_btn.configure(
                state="normal"))

        threading.Thread(target=_worker, daemon=True).start()

    def _refresh_all_profiles(self):
        """Regenerate ALL AI instrument profiles (overwrite existing cache)."""
        if not messagebox.askyesno(
                "Odśwież opisy AI",
                "To spowoduje ponowne wygenerowanie wszystkich opisów AI "
                "i nadpisanie zapisanych danych. Kontynuować?"):
            return

        instruments = self.config_data.get("instruments", [])
        if not instruments:
            self._gen_profiles_status.configure(
                text="Brak instrumentów.", fg=YELLOW)
            return

        total = len(instruments)
        self._gen_profiles_btn.configure(state="disabled")
        self._refresh_profiles_btn.configure(state="disabled")
        self._gen_profiles_status.configure(
            text=f"0/{total} — rozpoczynam…", fg=YELLOW)

        def _worker():
            import logging
            _log = logging.getLogger(__name__)
            updated = 0
            errors = 0
            for inst in instruments:
                sym = inst["symbol"]
                name = inst.get("name", sym)
                cat = inst.get("category", "Inne")
                self.after(0, lambda d=updated + errors, s=sym: (
                    self._gen_profiles_status.configure(
                        text=f"{d}/{total} — generuję: {s}…")))
                try:
                    text = generate_instrument_profile(
                        self.config_data, sym, name, cat)
                    save_instrument_profile(sym, text)
                    updated += 1
                except (ConnectionError, TimeoutError, ValueError, KeyError) as exc:
                    _log.error("Profile refresh %s failed: %s", sym, exc)
                    errors += 1

            msg = f"Zaktualizowano {updated} opisów."
            if errors:
                msg += f"  ({errors} błędów)"
            self.after(0, lambda: self._gen_profiles_status.configure(
                text=msg, fg=GREEN if not errors else YELLOW))
            self.after(0, lambda: self._gen_profiles_btn.configure(
                state="normal"))
            self.after(0, lambda: self._refresh_profiles_btn.configure(
                state="normal"))

        threading.Thread(target=_worker, daemon=True).start()

    def _add_source_row(self, url=""):
        row_frame = tk.Frame(self.sources_frame, bg=BG)
        row_frame.pack(fill="x", pady=2)
        var = tk.StringVar(value=url)
        tk.Entry(row_frame, textvariable=var, bg=BG2, fg=FG,
                 insertbackground=FG, relief="flat", font=("Segoe UI", 10),
                 highlightbackground=GRAY, highlightthickness=1
                 ).pack(side="left", fill="x", expand=True, padx=(0, 6))

        def remove():
            self.source_entries.remove((row_frame, var))
            row_frame.destroy()

        tk.Button(row_frame, text="✖", bg=BTN_BG, fg=RED,
                  font=("Segoe UI", 10), relief="flat", cursor="hand2",
                  padx=6, command=remove).pack(side="left")
        self.source_entries.append((row_frame, var))

    def _select_provider(self, provider):
        self.v_provider.set(provider)
        self._highlight_provider_buttons()
        self._update_model_list()

    def _highlight_provider_buttons(self):
        active = self.v_provider.get()
        for p, btn in self._provider_buttons.items():
            if p == active:
                btn.configure(bg=ACCENT, fg=BG)
            else:
                btn.configure(bg=BTN_BG, fg=FG)

    def _on_custom_model_change(self):
        custom = self.v_custom_model.get().strip()
        if custom:
            self.v_model.set(custom)

    def _update_model_list(self):
        provider = self.v_provider.get()
        models = get_available_models(provider)
        self.model_cb["values"] = models
        self.v_custom_model.set("")
        if provider == "anthropic":
            self.model_cb.configure(state="readonly")
            self._custom_model_entry.configure(state="disabled")
            if models and self.v_model.get() not in models:
                self.v_model.set(models[0])
        else:
            self.model_cb.configure(state="readonly")
            self._custom_model_entry.configure(state="normal")
            current = self.v_model.get()
            if not current or current not in models:
                if models:
                    self.v_model.set(models[0])

    def _select_chat_provider(self, provider):
        self.v_chat_provider.set(provider)
        self._highlight_chat_provider_buttons()
        self._update_chat_model_list()

    def _highlight_chat_provider_buttons(self):
        active = self.v_chat_provider.get()
        for p, btn in self._chat_provider_buttons.items():
            if p == active:
                btn.configure(bg=ACCENT, fg=BG)
            else:
                btn.configure(bg=BTN_BG, fg=FG)

    def _on_chat_custom_model_change(self):
        custom = self.v_chat_custom_model.get().strip()
        if custom:
            self.v_chat_model.set(custom)

    def _update_chat_model_list(self):
        provider = self.v_chat_provider.get()
        models = get_available_models(provider)
        self.chat_model_cb["values"] = models
        self.v_chat_custom_model.set("")
        if provider == "anthropic":
            self.chat_model_cb.configure(state="readonly")
            self._chat_custom_model_entry.configure(state="disabled")
            if models and self.v_chat_model.get() not in models:
                self.v_chat_model.set(models[0])
        else:
            self.chat_model_cb.configure(state="readonly")
            self._chat_custom_model_entry.configure(state="normal")
            current = self.v_chat_model.get()
            if not current or current not in models:
                if models:
                    self.v_chat_model.set(models[0])

    def _reset_prompt(self):
        from config import DEFAULT_CONFIG
        self.prompt_text.delete("1.0", "end")
        self.prompt_text.insert("end", DEFAULT_CONFIG["prompt"])

    def _reset_chat_prompt(self):
        from config import DEFAULT_CONFIG
        self.chat_prompt_text.delete("1.0", "end")
        self.chat_prompt_text.insert("end", DEFAULT_CONFIG["chat_prompt"])

    def _reset_chart_chat_prompt(self):
        from config import DEFAULT_CONFIG
        self.chart_chat_prompt_text.delete("1.0", "end")
        self.chart_chat_prompt_text.insert("end", DEFAULT_CONFIG["chart_chat_prompt"])

    def _reset_profile_prompt(self):
        from config import DEFAULT_CONFIG
        self.profile_prompt_text.delete("1.0", "end")
        self.profile_prompt_text.insert("end", DEFAULT_CONFIG["profile_prompt"])

    def _reset_calendar_event_prompt(self):
        from config import DEFAULT_CONFIG
        self.calendar_event_prompt_text.delete("1.0", "end")
        self.calendar_event_prompt_text.insert(
            "end", DEFAULT_CONFIG["calendar_event_prompt"])

    def _open_prompt_popup(self, title, source_widget):
        """Open a larger popup window for editing a prompt, then sync back."""
        popup = tk.Toplevel(self)
        popup.title(title)
        popup.geometry("750x520")
        popup.minsize(500, 350)
        popup.configure(bg=BG)
        popup.transient(self)
        popup.grab_set()

        editor = scrolledtext.ScrolledText(
            popup, bg=BG2, fg=FG, font=("Segoe UI", 11),
            relief="flat", wrap="word", insertbackground=FG)
        editor.pack(fill="both", expand=True, padx=12, pady=(12, 6))
        editor.insert("end", source_widget.get("1.0", "end").strip())
        editor.focus_set()

        btn_bar = tk.Frame(popup, bg=BG)
        btn_bar.pack(fill="x", padx=12, pady=(0, 12))

        def _save_and_close():
            source_widget.delete("1.0", "end")
            source_widget.insert("end", editor.get("1.0", "end").strip())
            popup.destroy()

        tk.Button(
            btn_bar, text="💾 Zapisz i zamknij", bg=GREEN, fg=BG,
            font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
            padx=14, pady=6, command=_save_and_close
        ).pack(side="right")
        tk.Button(
            btn_bar, text="Anuluj", bg=BTN_BG, fg=FG,
            font=("Segoe UI", 10), relief="flat", cursor="hand2",
            padx=14, pady=6, command=popup.destroy
        ).pack(side="right", padx=(0, 8))

    def _save_settings(self):
        # Nie nadpisuj kluczy zarządzanych przez env
        for kn, var in (("newsdata", self.v_newsdata), ("openai", self.v_openai),
                        ("anthropic", self.v_anthropic), ("openrouter", self.v_openrouter)):
            if not self._key_from_env.get(kn):
                self.config_data["api_keys"][kn] = var.get().strip()
        self.config_data["ai_provider"] = self.v_provider.get()
        custom = self.v_custom_model.get().strip()
        self.config_data["ai_model"] = custom if custom else self.v_model.get()
        self.config_data["chat_provider"] = self.v_chat_provider.get()
        chat_custom = self.v_chat_custom_model.get().strip()
        self.config_data["chat_model"] = chat_custom if chat_custom else self.v_chat_model.get()
        self.config_data["schedule"]["enabled"] = self.v_sched_enabled.get()
        self.config_data["schedule"]["times"] = [
            t.strip() for t in self.v_times.get().split(",") if t.strip()]
        self.config_data["prompt"] = self.prompt_text.get("1.0", "end").strip()
        self.config_data["chat_prompt"] = self.chat_prompt_text.get("1.0", "end").strip()
        self.config_data["chart_chat_prompt"] = self.chart_chat_prompt_text.get("1.0", "end").strip()
        self.config_data["profile_prompt"] = self.profile_prompt_text.get("1.0", "end").strip()
        self.config_data["calendar_event_prompt"] = self.calendar_event_prompt_text.get("1.0", "end").strip()

        instruments = []
        for _, v_sym, v_name, v_cat, v_src in self.inst_entries:
            if v_sym.get().strip():
                instruments.append({
                    "symbol":   v_sym.get().strip(),
                    "name":     v_name.get().strip(),
                    "category": v_cat.get(),
                    "source":   v_src.get(),
                })
        self.config_data["instruments"] = instruments

        sources = [var.get().strip() for _, var in self.source_entries
                   if var.get().strip()]
        self.config_data["sources"] = sources

        save_config(self.config_data)
        self._refresh_chart_symbols()
        self._start_scheduler()
        self._populate_tile_placeholders(instruments)

        inst_names = [f"{i['name']} ({i['symbol']})" for i in instruments]
        for pw in self._port_widgets.values():
            cb = pw.get("inst_cb")
            vi = pw.get("v_inst")
            if cb:
                cb["values"] = inst_names
            if vi and inst_names:
                vi.set(inst_names[0])

        messagebox.showinfo("Zapisano", "Ustawienia zostały zapisane!")

    # ═══════════════════════════════════════
    # CHAT
    # ═══════════════════════════════════════
    def _append_chat(self, label, text, tag):
        """Append a message to the chat display widget and any open popup displays."""
        for w in [self.chat_display] + self._chat_extra_displays:
            w.configure(state="normal")
            w.insert("end", f"{label}\n", "label")
            if tag == "assistant":
                insert_markdown(w, text, base_tag=tag)
            else:
                w.insert("end", text, tag)
            w.insert("end", "\n\n", tag)
            w.configure(state="disabled")
            w.see("end")

    def _clear_chat(self):
        self._chat_history.clear()
        for w in [self.chat_display] + self._chat_extra_displays:
            w.configure(state="normal")
            w.delete("1.0", "end")
            w.configure(state="disabled")

    def _send_chat_message(self):
        self._send_chat_message_from(self.chat_entry, self.chat_send_btn)

    def _send_chat_message_from(self, entry_widget, send_btn):
        """Send a chat message from any entry/button pair (main window or popup)."""
        msg = entry_widget.get().strip()
        if not msg:
            return
        entry_widget.delete(0, "end")
        self._append_chat("Ty:", msg, "user")

        self._chat_history.append({"role": "user", "content": msg})
        send_btn.configure(state="disabled", text="…")

        def _worker():
            system = self.config_data.get("chat_prompt", "")
            if not system:
                system = "Jesteś asystentem inwestycyjnym. Odpowiadaj po polsku."
            system += "\n"
            if self.current_market_data:
                instrument_list = _build_instrument_list(
                    self.current_market_data,
                    self.config_data.get("instruments", []))
                system += (
                    "\nPoniżej znajdują się aktualne ceny instrumentów obserwowanych "
                    "przez użytkownika (dane z ostatniej analizy):\n\n"
                    f"--- INSTRUMENTY ---\n{instrument_list}\n--- KONIEC ---"
                )
            if self.current_analysis:
                system += (
                    "\n\nPoniżej znajduje się ostatni raport analizy rynkowej, "
                    "który przygotowałeś. Użytkownik chce o nim porozmawiać.\n\n"
                    f"--- RAPORT ---\n{self.current_analysis}\n--- KONIEC RAPORTU ---"
                )

            try:
                reply = run_chat(self.config_data, list(self._chat_history), system)
            except Exception as exc:
                reply = f"Błąd połączenia: {exc}"
            self._chat_history.append({"role": "assistant", "content": reply})

            self.after(0, lambda: self._append_chat("AI:", reply, "assistant"))
            self.after(0, lambda: send_btn.configure(state="normal", text="Wyślij"))
            self.after(0, lambda: entry_widget.focus_set())

        threading.Thread(target=_worker, daemon=True).start()

    # ═══════════════════════════════════════
    # AUTOLOAD LAST REPORT
    # ═══════════════════════════════════════
    def _autoload_last_report(self):
        """Load the most recent report from DB into the dashboard on startup."""
        try:
            report = get_latest_report()
            if not report:
                self.analysis_text.configure(state="normal")
                self.analysis_text.delete("1.0", "end")
                self.analysis_text.insert(
                    "end",
                    "Brak zapisanych raportów. Wygeneruj pierwszy raport.")
                self.analysis_text.configure(state="disabled")
                self._update_token_info(None)
                return
            # report tuple: id, created_at, provider, model, market_summary,
            #               analysis, risk_level, input_tokens, output_tokens
            rid          = report[0]
            created_at   = report[1] or ""
            provider     = report[2] or ""
            model        = report[3] or ""
            analysis     = report[5] or ""
            risk         = report[6] or 0
            input_tokens = report[7] if len(report) > 7 else 0
            output_tokens = report[8] if len(report) > 8 else 0

            self.current_analysis = analysis

            self.analysis_text.configure(state="normal")
            self.analysis_text.delete("1.0", "end")
            insert_markdown(self.analysis_text, analysis)
            self.analysis_text.configure(state="disabled")

            usage_info = {
                "provider": provider, "model": model,
                "input_tokens": input_tokens or 0,
                "output_tokens": output_tokens or 0,
            }
            self._update_token_info(usage_info, report_date=created_at)

            # Update risk gauge
            for w in self.gauge_frame.winfo_children():
                w.destroy()
            try:
                canvas, _ = create_risk_gauge(self.gauge_frame, risk)
                canvas.get_tk_widget().pack()
            except (tk.TclError, ValueError, RuntimeError):
                tk.Label(self.gauge_frame, text=f"Ryzyko: {risk}/10",
                         bg=BG, fg=YELLOW,
                         font=("Segoe UI", 14, "bold")).pack(pady=8)

            # Select this report in the history tree if present
            rid_str = str(rid)
            if self.history_tree.exists(rid_str):
                self.history_tree.selection_set(rid_str)
                self.history_tree.see(rid_str)

        except Exception as exc:
            self.analysis_text.configure(state="normal")
            self.analysis_text.delete("1.0", "end")
            self.analysis_text.insert(
                "end",
                f"Błąd wczytywania ostatniego raportu: {exc}\n"
                "Wygeneruj nowy raport.")
            self.analysis_text.configure(state="disabled")
            self._update_token_info(None)

    # ═══════════════════════════════════════
    # ANALYSIS
    # ═══════════════════════════════════════
    def _run_analysis_thread(self):
        self.analyze_btn.configure(text="⏳ Analizuję…")
        self.set_busy(True, "Pobieranie danych…")
        threading.Thread(target=self._run_analysis, daemon=True).start()

    def _run_analysis(self):
        try:
            cfg = self.config_data
            self.set_busy(True, "Pobieranie danych instrumentów…")
            market_data = get_all_instruments(cfg.get("instruments", []))

            self.set_busy(True, "Pobieranie newsów (macro-trend engine)…")
            newsdata_key = get_api_key(cfg, "newsdata")
            macro_text = ""
            news = []
            if newsdata_key:
                try:
                    macro_payload = build_macro_payload(newsdata_key)
                    macro_text = format_macro_payload_for_llm(macro_payload)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(
                        "Macro-trend fallback: %s", e)
            # Fallback: legacy news if macro engine fails
            if not macro_text:
                news = get_news(
                    newsdata_key,
                    query="geopolitics economy markets finance",
                    language="en")

            scraped_text = ""
            sources = cfg.get("sources", [])
            if sources:
                self.set_busy(True,
                    f"Pobieranie treści z {len(sources)} źródeł www…")
                scraped_text = scrape_all(
                    sources,
                    max_chars_per_site=2000,
                    trusted_domains=cfg.get("trusted_domains"))

            self.set_busy(True, "Generowanie analizy AI…")
            summary  = format_market_summary(market_data)
            result   = run_analysis(cfg, summary, news, scraped_text,
                                    macro_text=macro_text,
                                    market_data=market_data)
            # result is a dict: {text, input_tokens, output_tokens}
            analysis     = result.get("text", "")
            input_tokens = result.get("input_tokens", 0)
            output_tokens = result.get("output_tokens", 0)
            risk     = extract_risk_level(analysis)

            provider = cfg["ai_provider"]
            model    = cfg["ai_model"]

            self.current_analysis    = analysis
            self.current_market_data = market_data

            from zoneinfo import ZoneInfo as _ZI
            from datetime import datetime as _dt
            now_str = _dt.now(_ZI("Europe/Warsaw")).strftime("%Y-%m-%d %H:%M:%S")

            usage_info = {
                "provider": provider, "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
            # Schedule UI update BEFORE DB saves — display is never blocked by DB errors
            self.after(0, lambda: self._update_dashboard(
                analysis, risk, market_data, usage_info=usage_info,
                report_date=now_str))

            try:
                save_report(provider, model,
                            summary, analysis, risk,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens)
                save_market_snapshot(market_data)
            except Exception as db_exc:
                import logging as _log
                _log.getLogger(__name__).warning("Błąd zapisu do bazy: %s", db_exc)

        except Exception as exc:
            import traceback
            traceback.print_exc()
            err_msg = str(exc)
            self.after(0, lambda m=err_msg: self._show_analysis_error(m))
        finally:
            self.set_busy(False, "Gotowy")
            self.after(0, lambda: self.analyze_btn.configure(
                text="▶  Uruchom Analizę"))

    def _show_analysis_error(self, message):
        """Display a fatal analysis error in the analysis text area."""
        self.analysis_text.configure(state="normal")
        self.analysis_text.delete("1.0", "end")
        self.analysis_text.insert("end", f"Błąd generowania analizy:\n\n{message}")
        self.analysis_text.configure(state="disabled")
        self._set_status(f"Błąd: {message[:80]}")

    def _update_dashboard(self, analysis, risk, market_data, usage_info=None,
                          report_date=None):
        self.analysis_text.configure(state="normal")
        self.analysis_text.delete("1.0", "end")
        insert_markdown(self.analysis_text, analysis)
        self.analysis_text.configure(state="disabled")

        self._update_token_info(usage_info, report_date=report_date)
        self._update_price_tiles(market_data)
        self._refresh_portfolio()

        for w in self.gauge_frame.winfo_children():
            w.destroy()
        try:
            canvas, _ = create_risk_gauge(self.gauge_frame, risk)
            canvas.get_tk_widget().pack()
        except (tk.TclError, ValueError, RuntimeError):
            tk.Label(self.gauge_frame, text=f"Ryzyko: {risk}/10",
                     bg=BG, fg=YELLOW,
                     font=("Segoe UI", 14, "bold")).pack(pady=8)

        self._set_status(f"Analiza zakończona  •  {len(analysis)} znaków")
        self._load_history()

    @staticmethod
    def _fmt_cost(val):
        """Format a small dollar/PLN amount with adaptive precision."""
        if val < 0.01:
            return f"{val:.6f}"
        return f"{val:.4f}"

    def _build_token_cost_line(self, usage_info):
        """Return a formatted string: Model • Tokeny • Koszt."""
        provider = usage_info.get("provider", "")
        model = usage_info.get("model", "")
        inp = usage_info.get("input_tokens", 0)
        out = usage_info.get("output_tokens", 0)

        parts = [f"Model: {provider}/{model}"]

        if inp or out:
            parts.append(
                f"Tokeny: input {inp}, output {out}, razem {inp + out}")
        else:
            parts.append("Tokeny: brak danych")

        # Cost calculation
        if inp or out:
            model_key = f"{provider}/{model}" if provider else model
            cost_usd = get_model_cost(model_key, inp, out)
            if cost_usd is not None:
                cost_str = f"${self._fmt_cost(cost_usd)}"
                # PLN via existing FX mechanism
                fx = get_fx_to_usd("PLN")  # PLN→USD rate (~0.25)
                if fx and fx > 0:
                    cost_pln = cost_usd / fx
                    cost_str += f" | {self._fmt_cost(cost_pln)} PLN"
                else:
                    cost_str += " | PLN —"
                parts.append(f"Koszt: {cost_str}")
            else:
                parts.append("Koszt: brak danych")
        else:
            parts.append("Koszt: brak danych")

        return "  •  ".join(parts)

    def _update_token_info(self, usage_info=None, report_date=None):
        """Update the token/model info label and report date on the dashboard."""
        # Report date
        if report_date:
            self.report_date_label.configure(
                text=f"Data utworzenia raportu: {report_date[:16]}")
        else:
            self.report_date_label.configure(text="")

        # Token / model / cost info — single yellow line
        if not usage_info:
            self.token_line_label.configure(text="")
            return
        self.token_line_label.configure(
            text=self._build_token_cost_line(usage_info))

    # ═══════════════════════════════════════
    # PDF EXPORT
    # ═══════════════════════════════════════
    def _build_pdf(self, text, report_date=None):
        """Build a FPDF object from report text. Returns the FPDF instance.

        *report_date*: string shown as report date (defaults to now).
        """
        from fpdf import FPDF
        from datetime import datetime as _dt

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        effective_w = pdf.w - pdf.l_margin - pdf.r_margin

        # Try to register a UTF-8 capable font
        use_utf8 = False
        font_dirs = []
        windir = os.environ.get("WINDIR", "C:\\Windows")
        font_dirs.append(os.path.join(windir, "Fonts"))
        # Linux common paths
        for p in ("/usr/share/fonts/truetype/dejavu",
                  "/usr/share/fonts/truetype/liberation",
                  "/usr/share/fonts/TTF"):
            font_dirs.append(p)

        for fdir in font_dirs:
            if use_utf8:
                break
            try:
                candidates = [
                    ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"),
                    ("LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf"),
                    ("arial.ttf", "arialbd.ttf"),
                ]
                for regular, bold in candidates:
                    font_path = os.path.join(fdir, regular)
                    bold_path = os.path.join(fdir, bold)
                    if os.path.exists(font_path):
                        pdf.add_font("UTFFont", "", font_path, uni=True)
                        if os.path.exists(bold_path):
                            pdf.add_font("UTFFont", "B", bold_path, uni=True)
                        use_utf8 = True
                        break
            except (OSError, RuntimeError):
                continue

        from zoneinfo import ZoneInfo as _ZI
        date_str = report_date or _dt.now(
            _ZI("Europe/Warsaw")).strftime("%Y-%m-%d %H:%M")

        # Title
        if use_utf8:
            pdf.set_font("UTFFont", "B", 16)
        else:
            pdf.set_font("Helvetica", "B", 16)
        pdf.cell(effective_w, 10, "Investment Advisor - Raport",
                 ln=True, align="C")

        # Date
        if use_utf8:
            pdf.set_font("UTFFont", "", 9)
        else:
            pdf.set_font("Helvetica", size=9)
        pdf.cell(effective_w, 6, date_str, ln=True, align="C")
        pdf.ln(6)

        # Body — with basic markdown heading support
        for line in text.split("\n"):
            if not use_utf8:
                line = line.encode("latin-1", "replace").decode("latin-1")
            stripped = line.strip()
            pdf.set_x(pdf.l_margin)

            if not stripped:
                pdf.ln(4)
            elif stripped.startswith("### "):
                if use_utf8:
                    pdf.set_font("UTFFont", "B", 11)
                else:
                    pdf.set_font("Helvetica", "B", 11)
                pdf.multi_cell(effective_w, 5, stripped[4:])
                if use_utf8:
                    pdf.set_font("UTFFont", "", 10)
                else:
                    pdf.set_font("Helvetica", size=10)
            elif stripped.startswith("## "):
                pdf.ln(2)
                if use_utf8:
                    pdf.set_font("UTFFont", "B", 12)
                else:
                    pdf.set_font("Helvetica", "B", 12)
                pdf.multi_cell(effective_w, 6, stripped[3:])
                if use_utf8:
                    pdf.set_font("UTFFont", "", 10)
                else:
                    pdf.set_font("Helvetica", size=10)
            elif stripped.startswith("# "):
                pdf.ln(3)
                if use_utf8:
                    pdf.set_font("UTFFont", "B", 14)
                else:
                    pdf.set_font("Helvetica", "B", 14)
                pdf.multi_cell(effective_w, 7, stripped[2:])
                if use_utf8:
                    pdf.set_font("UTFFont", "", 10)
                else:
                    pdf.set_font("Helvetica", size=10)
            else:
                if use_utf8:
                    pdf.set_font("UTFFont", "", 10)
                else:
                    pdf.set_font("Helvetica", size=10)
                pdf.multi_cell(effective_w, 5, line)

        return pdf

    def _export_pdf(self):
        """Export current dashboard analysis to PDF via Save-As dialog."""
        if not self.current_analysis:
            messagebox.showwarning("Brak analizy", "Najpierw uruchom analizę!")
            return

        from datetime import datetime as _dt
        from zoneinfo import ZoneInfo as _ZI
        from tkinter import filedialog

        # Determine report date for default filename
        report_date_str = None
        try:
            report = get_latest_report()
            if report and report[1]:
                report_date_str = report[1][:16]  # "YYYY-MM-DD HH:MM"
        except (IndexError, TypeError):
            pass

        if report_date_str:
            # Parse stored date (treat naive as Warsaw)
            fname_ts = (report_date_str
                        .replace("-", "").replace(":", "").replace(" ", "_"))
        else:
            fname_ts = _dt.now(_ZI("Europe/Warsaw")).strftime("%Y%m%d_%H%M")

        default_name = f"raport_{fname_ts}.pdf"

        # Remember last export directory in config
        initial_dir = self.config_data.get("last_export_dir", "")
        if not initial_dir or not os.path.isdir(initial_dir):
            initial_dir = os.path.expanduser("~/Documents")
            if not os.path.isdir(initial_dir):
                initial_dir = os.path.expanduser("~")

        path = filedialog.asksaveasfilename(
            title="Zapisz raport jako PDF",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialdir=initial_dir,
            initialfile=default_name,
        )
        if not path:
            return

        # Save last-used directory for next time
        self.config_data["last_export_dir"] = os.path.dirname(path)
        save_config(self.config_data)

        try:
            pdf = self._build_pdf(self.current_analysis,
                                  report_date=report_date_str)
            pdf.output(path)
            messagebox.showinfo("PDF",
                                f"Raport zapisany:\n{os.path.abspath(path)}")
        except Exception as exc:
            messagebox.showerror("Błąd PDF", str(exc))

    def _export_history_pdf(self):
        """Export selected history report to PDF via Save As dialog."""
        sel = self.history_tree.selection()
        if not sel:
            messagebox.showinfo(
                "Eksport PDF", "Zaznacz raport na liście historii.")
            return
        report = get_report_by_id(int(sel[0]))
        if not report:
            messagebox.showwarning("Eksport PDF", "Nie znaleziono raportu.")
            return

        analysis = report[5] or ""
        report_date = (report[1] or "")[:16]

        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            title="Zapisz raport jako PDF",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"raport_{report_date.replace(':', '').replace(' ', '_').replace('-', '')}.pdf",
        )
        if not path:
            return

        def _generate():
            try:
                pdf = self._build_pdf(analysis, report_date=report_date)
                pdf.output(path)
                self.after(0, lambda: messagebox.showinfo(
                    "PDF", f"Raport zapisany:\n{os.path.abspath(path)}"))
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror(
                    "Błąd PDF", str(exc)))

        threading.Thread(target=_generate, daemon=True).start()

    # ═══════════════════════════════════════
    # ALERTS
    # ═══════════════════════════════════════
    def _check_alerts(self):
        if self._shutting_down:
            return
        alerts = get_unseen_alerts()
        if alerts:
            self.alert_btn.configure(
                fg=RED, text=f"🔔 Alerty ({len(alerts)})")
        self.after(60000, self._check_alerts)

    def _show_alerts(self):
        alerts = get_unseen_alerts()
        mark_alerts_seen()
        self.alert_btn.configure(fg=YELLOW, text="🔔 Alerty")
        win = tk.Toplevel(self)
        win.title("Alerty")
        win.geometry("500x400")
        win.configure(bg=BG)
        if not alerts:
            tk.Label(win, text="Brak nowych alertów", bg=BG, fg=FG,
                     font=("Segoe UI", 12)).pack(pady=40)
        for a in alerts:
            f = tk.Frame(win, bg=BG2, pady=6)
            f.pack(fill="x", padx=12, pady=4)
            tk.Label(f, text=f"[{a[1][:16]}] {a[2]}", bg=BG2, fg=ACCENT,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=8)
            tk.Label(f, text=a[3], bg=BG2, fg=FG, font=("Segoe UI", 9),
                     wraplength=460).pack(anchor="w", padx=8)

    # ═══════════════════════════════════════
    # SCHEDULER
    # ═══════════════════════════════════════
    def _start_scheduler(self):
        schedule.clear()
        if self.config_data["schedule"].get("enabled"):
            for t in self.config_data["schedule"].get("times", []):
                schedule.every().day.at(t).do(self._run_analysis_thread)

        def runner():
            while not self._shutting_down:
                schedule.run_pending()
                time.sleep(30)

        threading.Thread(target=runner, daemon=True).start()

    def _set_status(self, msg):
        """Thread-safe status update - schedules UI change on main thread."""
        if self._shutting_down:
            return
        try:
            self.after(0, lambda: self.status_label.configure(text=msg))
        except RuntimeError:
            pass

    def _show_analysis_overlay(self, message=""):
        """Show a pulsing overlay on the analysis text area."""
        self._analysis_overlay_msg = message
        if not self._analysis_overlay_visible:
            self._analysis_overlay_visible = True
            self._analysis_overlay_step = 0
            self._analysis_overlay.place(
                relx=0, rely=0, relwidth=1, relheight=1)
            self._analysis_overlay.lift()
            self._tick_overlay()

    def _hide_analysis_overlay(self):
        """Hide the analysis overlay."""
        self._analysis_overlay_visible = False
        if self._analysis_overlay_after:
            try:
                self.after_cancel(self._analysis_overlay_after)
            except (tk.TclError, ValueError):
                pass
            self._analysis_overlay_after = None
        self._analysis_overlay.place_forget()

    def _tick_overlay(self):
        """Animate the overlay text with a pulsing dot pattern."""
        if not self._analysis_overlay_visible:
            return
        _OVERLAY_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        frame = _OVERLAY_FRAMES[self._analysis_overlay_step % len(_OVERLAY_FRAMES)]
        msg = self._analysis_overlay_msg or "Analizuję"
        try:
            self._analysis_overlay.configure(text=f"{frame}  {msg}  {frame}")
        except (tk.TclError, RuntimeError):
            self._analysis_overlay_visible = False
            return
        self._analysis_overlay_step += 1
        self._analysis_overlay_after = self.after(120, self._tick_overlay)

    def set_busy(self, is_busy, message="Pracuję…"):
        """Lock/unlock buttons and start/stop spinner animation.

        Thread-safe: schedules all UI changes on the main thread.
        """
        def _apply():
            if is_busy:
                for btn in self._busy_buttons:
                    try:
                        btn.configure(state="disabled")
                    except tk.TclError:
                        pass
                if self._spinner:
                    self._spinner.start(message)
                self._show_analysis_overlay(message)
            else:
                for btn in self._busy_buttons:
                    try:
                        btn.configure(state="normal")
                    except tk.TclError:
                        pass
                if self._spinner:
                    self._spinner.stop(message)
                self._hide_analysis_overlay()
        if self._shutting_down:
            return
        try:
            self.after(0, _apply)
        except RuntimeError:
            pass

    # ═══════════════════════════════════════
    # POPUP WINDOWS (double-click)
    # ═══════════════════════════════════════

    def _open_analysis_popup(self):
        """Open a large, article-style readable view of the current analysis report."""
        win = tk.Toplevel(self)
        win.title("Raport Analizy AI")
        win.configure(bg=BG)
        win.geometry("1050x780")
        win.minsize(700, 500)
        win.resizable(True, True)

        # Header bar
        header = tk.Frame(win, bg=BG2, padx=16, pady=10)
        header.pack(fill="x")
        tk.Label(header, text="Raport Analizy AI", bg=BG2, fg=ACCENT,
                 font=("Segoe UI", 14, "bold")).pack(side="left")
        date_text = self.report_date_label.cget("text")
        if date_text:
            tk.Label(header, text=date_text, bg=BG2, fg=GREEN,
                     font=("Segoe UI", 9)).pack(side="right")

        # Scrollable article text
        txt = scrolledtext.ScrolledText(
            win, bg=BG2, fg=FG,
            font=("Segoe UI", 12),
            relief="flat", wrap="word", state="normal",
            insertbackground=FG, selectbackground=ACCENT,
            padx=28, pady=18, spacing1=2, spacing3=4)
        txt.pack(fill="both", expand=True, padx=12, pady=(8, 0))
        setup_markdown_tags(txt)

        if self.current_analysis:
            insert_markdown(txt, self.current_analysis)
        else:
            txt.insert("1.0",
                       "Brak raportu do wyświetlenia.\n"
                       "Wygeneruj pierwszą analizę klikając '▶ Uruchom Analizę'.")
        txt.configure(state="disabled")

        # Bottom bar
        bar = tk.Frame(win, bg=BG, pady=8)
        bar.pack(fill="x")
        tk.Button(bar, text="Zamknij", bg=BTN_BG, fg=FG, font=("Segoe UI", 10),
                  relief="flat", cursor="hand2", padx=16,
                  command=win.destroy).pack(side="right", padx=12)

    def _open_chat_popup(self):
        """Open a large resizable chat window that syncs with the main chat."""
        win = tk.Toplevel(self)
        win.title("Czat z AI")
        win.configure(bg=BG)
        win.geometry("950x680")
        win.minsize(600, 400)
        win.resizable(True, True)

        # Header bar
        header = tk.Frame(win, bg=BG2, padx=16, pady=8)
        header.pack(fill="x")
        tk.Label(header, text="Czat z AI", bg=BG2, fg=ACCENT,
                 font=("Segoe UI", 13, "bold")).pack(side="left")

        # Chat display
        popup_display = scrolledtext.ScrolledText(
            win, bg=BG2, fg=FG, font=("Segoe UI", 11),
            relief="flat", wrap="word", state="normal",
            insertbackground=FG, selectbackground=ACCENT,
            padx=12, pady=8)
        popup_display.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        popup_display.tag_configure("user", foreground=ACCENT)
        popup_display.tag_configure("assistant", foreground=GREEN)
        popup_display.tag_configure("label", foreground=YELLOW,
                                    font=("Segoe UI", 10, "bold"))
        popup_display.tag_configure("error", foreground=RED)
        setup_markdown_tags(popup_display)

        # Replay existing chat history into the popup display
        for msg in self._chat_history:
            if msg["role"] == "user":
                popup_display.insert("end", "Ty:\n", "label")
                popup_display.insert("end", msg["content"], "user")
                popup_display.insert("end", "\n\n", "user")
            else:
                popup_display.insert("end", "AI:\n", "label")
                insert_markdown(popup_display, msg["content"], base_tag="assistant")
                popup_display.insert("end", "\n\n", "assistant")
        popup_display.configure(state="disabled")
        popup_display.see("end")

        # Register popup as extra display so new messages appear here too
        self._chat_extra_displays.append(popup_display)

        # Input bar
        input_bar = tk.Frame(win, bg=BG)
        input_bar.pack(fill="x", padx=8, pady=8)

        popup_send_btn = tk.Button(
            input_bar, text="Wyślij", bg=ACCENT, fg=BG,
            font=("Segoe UI", 10, "bold"), relief="flat",
            cursor="hand2", padx=12)
        popup_send_btn.pack(side="right", padx=(4, 0))

        tk.Button(
            input_bar, text="Wyczyść", bg=BTN_BG, fg=SUBTEXT,
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            padx=8, command=self._clear_chat
        ).pack(side="right", padx=(4, 0))

        popup_entry = tk.Entry(
            input_bar, bg=BG2, fg=FG, insertbackground=FG,
            relief="flat", font=("Segoe UI", 11),
            highlightbackground=GRAY, highlightthickness=1)
        popup_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))

        popup_send_btn.configure(
            command=lambda: self._send_chat_message_from(popup_entry, popup_send_btn))
        popup_entry.bind(
            "<Return>",
            lambda e: self._send_chat_message_from(popup_entry, popup_send_btn))
        popup_entry.focus_set()

        def _on_popup_close():
            if popup_display in self._chat_extra_displays:
                self._chat_extra_displays.remove(popup_display)
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_popup_close)

    def _open_market_popup(self):
        """Open a large resizable window showing all market instruments."""
        win = tk.Toplevel(self)
        win.title("Kursy Rynkowe")
        win.configure(bg=BG)
        win.geometry("1150x720")
        win.minsize(700, 400)
        win.resizable(True, True)

        # Header bar
        header = tk.Frame(win, bg=BG2, padx=16, pady=8)
        header.pack(fill="x")
        tk.Label(header, text="Kursy Rynkowe", bg=BG2, fg=ACCENT,
                 font=("Segoe UI", 13, "bold")).pack(side="left")
        tk.Label(header,
                 text="Dwuklik → wykres  |  Pojedynczy klik → profil  |  Prawy klik → dodaj do portfela",
                 bg=BG2, fg=SUBTEXT, font=("Segoe UI", 8)).pack(side="right")

        # Canvas + scrollbar for tiles
        container = tk.Frame(win, bg=BG)
        container.pack(fill="both", expand=True, padx=8, pady=8)

        canvas = tk.Canvas(container, bg=BG, highlightthickness=0)
        sb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        tiles_frame = tk.Frame(canvas, bg=BG)
        win_id = canvas.create_window((0, 0), window=tiles_frame, anchor="nw")

        tiles_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(win_id, width=e.width))

        self._bind_mousewheel(canvas, canvas)

        # Build tiles — 4 columns, larger font
        COLS = 4
        for col in range(COLS):
            tiles_frame.columnconfigure(col, weight=1)

        popup_tiles = {}
        instruments = self.config_data.get("instruments", [])
        for idx, inst in enumerate(instruments):
            symbol = inst["symbol"]
            name   = inst.get("name", symbol)
            row    = idx // COLS
            col    = idx % COLS

            # Read current price/change/color from main tile widgets
            price_text  = "—"
            change_text = "—"
            change_color = GRAY
            frame_color  = GRAY
            if symbol in self._tile_widgets:
                mt = self._tile_widgets[symbol]
                price_text   = mt["price_lbl"].cget("text")
                change_text  = mt["change_lbl"].cget("text")
                change_color = mt["change_lbl"].cget("fg")
                frame_color  = mt["frame"].cget("highlightbackground")

            tile = tk.Frame(tiles_frame, bg=BG2,
                            highlightbackground=frame_color, highlightthickness=1,
                            padx=10, pady=8)
            tile.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")

            popup_name_lbl = tk.Label(tile, text=name, bg=BG2, fg=FG,
                                      font=("Segoe UI", 10, "bold"),
                                      anchor="w", wraplength=200)
            popup_name_lbl.pack(fill="x")
            tk.Label(tile, text=symbol, bg=BG2, fg=GRAY,
                     font=("Segoe UI", 8), anchor="w").pack(fill="x")

            price_lbl = tk.Label(tile, text=price_text, bg=BG2, fg=FG,
                                  font=("Segoe UI", 14, "bold"), anchor="w")
            price_lbl.pack(fill="x")

            change_lbl = tk.Label(tile, text=change_text, bg=BG2, fg=change_color,
                                   font=("Segoe UI", 10), anchor="w")
            change_lbl.pack(fill="x")

            spark = tk.Canvas(tile, bg=BG2, height=32, highlightthickness=0)
            spark.pack(fill="x", pady=(4, 0))

            popup_tiles[symbol] = {
                "frame":      tile,
                "name_lbl":   popup_name_lbl,
                "price_lbl":  price_lbl,
                "change_lbl": change_lbl,
                "spark":      spark,
            }
            self._bind_tile_events(tile, symbol)

        self._market_popup_tile_widgets = popup_tiles

        # Draw sparklines for instruments with current data
        if self.current_market_data:
            for symbol, tw in popup_tiles.items():
                d = self.current_market_data.get(symbol, {})
                sparkline = d.get("sparkline", [])
                if sparkline:
                    change_pct = d.get("change_pct", 0)
                    color = GREEN if change_pct >= 0 else RED
                    self._draw_sparkline(tw["spark"], sparkline, color)

        def _on_popup_close():
            self._market_popup_tile_widgets = {}
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_popup_close)

    def _on_close(self):
        """Clean shutdown: close all matplotlib figures before destroying Tk."""
        self._shutting_down = True
        try:
            if self._current_chart_fig:
                plt.close(self._current_chart_fig)
                self._current_chart_fig = None
            plt.close("all")
        except (ValueError, RuntimeError):
            pass
        schedule.clear()
        self.destroy()


if __name__ == "__main__":
    print("Start…")
    try:
        app = InvestmentAdvisor()
        print("Okno utworzone!")
        app.mainloop()
    except Exception as exc:
        import traceback
        traceback.print_exc()
        input("Nacisnij Enter aby zamknac...")
