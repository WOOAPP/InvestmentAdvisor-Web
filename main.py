import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
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
from modules.market_data import get_all_instruments, get_news, format_market_summary
from modules.ai_engine import run_analysis, run_chat, get_available_models
from modules.database import (
    save_report, get_reports, get_report_by_id,
    save_market_snapshot, get_unseen_alerts, mark_alerts_seen, delete_report,
    add_portfolio_position, get_portfolio_positions, delete_portfolio_position,
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
GRAY   = "#313244"
BTN_BG = "#313244"


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
        self._chat_history = []     # list of {"role": ..., "content": ...}
        self.inst_entries = []
        self.source_entries = []
        self._tile_widgets = {}
        self._current_chart_fig = None
        self._chart_chat_history = []
        self._cal_events = []
        self._period_buttons = {}
        self._shutting_down = False
        self._busy_buttons = []   # buttons to lock during analysis/fetch
        self._spinner = None      # BusySpinner instance (created after UI build)
        self._build_ui()
        self._start_scheduler()
        self._check_alerts()
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

        self.notebook.add(self.tab_dashboard, text="  🏠 Dashboard  ")
        self.notebook.add(self.tab_portfolio,  text="  💰 Portfel  ")
        self.notebook.add(self.tab_calendar,   text="  📅 Kalendarz  ")
        self.notebook.add(self.tab_charts,     text="  📊 Wykresy  ")
        self.notebook.add(self.tab_history,    text="  📋 Historia  ")
        self.notebook.add(self.tab_settings,   text="  ⚙️ Ustawienia  ")

        self._build_dashboard()
        self._build_portfolio_tab()
        self._build_calendar_tab()
        self._build_charts_tab()
        self._build_history_tab()
        self._build_settings_tab()

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
            btn_bar, text="Gotowy", bg=BG, fg=GRAY, font=("Segoe UI", 9))
        self.status_label.pack(side="right", padx=8)

        # Task 2: register buttons for busy-lock
        self._busy_buttons = [self.analyze_btn, self.fetch_btn, self.export_btn]
        self._spinner = BusySpinner(self, self.status_label)

        # ── PanedWindow: analysis (top) + chat (bottom) ──
        paned = tk.PanedWindow(right, orient="vertical", bg=BG,
                                sashwidth=5, sashrelief="flat")
        paned.pack(fill="both", expand=True)

        # — Analysis panel —
        analysis_frame = tk.LabelFrame(
            paned, text=" Analiza AI ", bg=BG, fg=ACCENT,
            font=("Segoe UI", 10, "bold"), relief="flat",
            highlightbackground=GRAY, highlightthickness=1)
        paned.add(analysis_frame, minsize=120)
        self.analysis_text = scrolledtext.ScrolledText(
            analysis_frame, bg=BG2, fg=FG, font=("Segoe UI", 10),
            relief="flat", wrap="word", state="disabled",
            insertbackground=FG, selectbackground=ACCENT)
        self.analysis_text.pack(fill="both", expand=True, padx=4, pady=4)
        setup_markdown_tags(self.analysis_text)

        # — Chat panel —
        self.chat_frame = tk.LabelFrame(
            paned, text=" Czat z AI ", bg=BG, fg=ACCENT,
            font=("Segoe UI", 10, "bold"), relief="flat",
            highlightbackground=GRAY, highlightthickness=1)
        paned.add(self.chat_frame, minsize=120)

        self.chat_display = scrolledtext.ScrolledText(
            self.chat_frame, bg=BG2, fg=FG, font=("Segoe UI", 10),
            relief="flat", wrap="word", state="disabled",
            insertbackground=FG, selectbackground=ACCENT, height=8)
        self.chat_display.pack(fill="both", expand=True, padx=4, pady=(4, 2))
        self.chat_display.tag_configure("user", foreground=ACCENT)
        self.chat_display.tag_configure("assistant", foreground=GREEN)
        self.chat_display.tag_configure("label", foreground=YELLOW,
                                         font=("Segoe UI", 9, "bold"))
        self.chat_display.tag_configure("error", foreground=RED)

        input_bar = tk.Frame(self.chat_frame, bg=BG)
        input_bar.pack(fill="x", padx=4, pady=(0, 4))

        self.chat_entry = tk.Entry(
            input_bar, bg=BG2, fg=FG, insertbackground=FG,
            relief="flat", font=("Segoe UI", 10),
            highlightbackground=GRAY, highlightthickness=1)
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.chat_entry.bind("<Return>", lambda e: self._send_chat_message())

        self.chat_send_btn = tk.Button(
            input_bar, text="Wyślij", bg=ACCENT, fg=BG,
            font=("Segoe UI", 10, "bold"), relief="flat",
            cursor="hand2", padx=12, command=self._send_chat_message)
        self.chat_send_btn.pack(side="left")

        tk.Button(
            input_bar, text="Wyczyść", bg=BTN_BG, fg=GRAY,
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            padx=8, command=self._clear_chat
        ).pack(side="left", padx=(4, 0))

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

            tk.Label(tile, text=name, bg=BG2, fg=FG,
                     font=("Segoe UI", 8, "bold"),
                     anchor="w", wraplength=130).pack(fill="x")
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
                "price_lbl":  price_lbl,
                "change_lbl": change_lbl,
                "spark":      spark,
            }

    def _update_price_tiles(self, market_data):
        for symbol, w in self._tile_widgets.items():
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

            if sparkline:
                self._draw_sparkline(w["spark"], sparkline, color)

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

    # ═══════════════════════════════════════
    # PORTFOLIO TAB
    # ═══════════════════════════════════════
    def _build_portfolio_tab(self):
        form_frame = tk.LabelFrame(
            self.tab_portfolio, text=" Dodaj pozycję ", bg=BG, fg=ACCENT,
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
        self.v_port_inst = tk.StringVar(value=inst_names[0] if inst_names else "")
        self.port_inst_cb = ttk.Combobox(
            inner, textvariable=self.v_port_inst,
            values=inst_names, width=24, state="readonly")
        self.port_inst_cb.pack(side="left", padx=(0, 8))

        lbl("Ilość:")
        self.v_port_qty = tk.StringVar()
        tk.Entry(inner, textvariable=self.v_port_qty, bg=BG2, fg=FG,
                 insertbackground=FG, relief="flat", width=10,
                 font=("Segoe UI", 10),
                 highlightbackground=GRAY, highlightthickness=1
                 ).pack(side="left", padx=(0, 8))

        lbl("Cena zakupu ($):")
        self.v_port_price = tk.StringVar()
        tk.Entry(inner, textvariable=self.v_port_price, bg=BG2, fg=FG,
                 insertbackground=FG, relief="flat", width=12,
                 font=("Segoe UI", 10),
                 highlightbackground=GRAY, highlightthickness=1
                 ).pack(side="left", padx=(0, 8))

        tk.Button(
            inner, text="➕ Dodaj", bg=GREEN, fg=BG,
            font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
            padx=10, pady=3, command=self._add_portfolio_position
        ).pack(side="left", padx=4)

        # Treeview pozycji
        tree_frame = tk.Frame(self.tab_portfolio, bg=BG)
        tree_frame.pack(fill="both", expand=True, padx=12, pady=4)

        cols = ("Instrument", "Symbol", "Ilość", "Kup. ($)",
                "Akt. ($)", "Wartość ($)", "Zysk ($)", "Zysk %")
        self.port_tree = ttk.Treeview(
            tree_frame, columns=cols, show="headings", height=18)

        widths = [150, 75, 70, 90, 90, 100, 100, 80]
        anchors = ["w", "center", "e", "e", "e", "e", "e", "e"]
        for col, w, anc in zip(cols, widths, anchors):
            self.port_tree.heading(col, text=col)
            self.port_tree.column(col, width=w, anchor=anc)

        self.port_tree.tag_configure("profit", foreground=GREEN)
        self.port_tree.tag_configure("loss",   foreground=RED)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical",
                             command=self.port_tree.yview)
        self.port_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.port_tree.pack(fill="both", expand=True)

        # Mousewheel scrolling for portfolio tree
        self._bind_mousewheel(self.port_tree, self.port_tree)

        # Pasek podsumowania
        bot = tk.Frame(self.tab_portfolio, bg=BG2,
                       highlightbackground=GRAY, highlightthickness=1)
        bot.pack(fill="x", padx=12, pady=(0, 8))

        tk.Button(
            bot, text="🗑️ Usuń zaznaczony", bg=BTN_BG, fg=RED,
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            padx=8, pady=4, command=self._remove_portfolio_position
        ).pack(side="left", padx=8, pady=6)

        tk.Button(
            bot, text="🔄 Odśwież ceny", bg=BTN_BG, fg=ACCENT,
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            padx=8, pady=4, command=self._quick_fetch_prices
        ).pack(side="left", padx=4, pady=6)

        self._portfolio_status = tk.Label(
            bot, text="", bg=BG2, fg=GRAY, font=("Segoe UI", 9))
        self._portfolio_status.pack(side="left", padx=12)

        self.port_summary_lbl = tk.Label(
            bot, text="", bg=BG2, fg=FG,
            font=("Segoe UI", 10, "bold"), anchor="e")
        self.port_summary_lbl.pack(side="right", padx=16, pady=6)

        self._refresh_portfolio()

    def _add_portfolio_position(self):
        inst_str  = self.v_port_inst.get()
        qty_str   = self.v_port_qty.get().strip()
        price_str = self.v_port_price.get().strip()

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

        symbol = inst_str.split("(")[-1].rstrip(")")
        name   = inst_str.split("(")[0].strip()
        add_portfolio_position(symbol, name, qty, price)
        self.v_port_qty.set("")
        self.v_port_price.set("")
        self._refresh_portfolio()

    def _remove_portfolio_position(self):
        sel = self.port_tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Usuń pozycję",
                                "Usunąć wybraną pozycję z portfela?"):
            for iid in sel:
                delete_portfolio_position(int(iid))
            self._refresh_portfolio()

    def _refresh_portfolio(self):
        for row in self.port_tree.get_children():
            self.port_tree.delete(row)

        positions      = get_portfolio_positions()
        total_invested = 0.0
        total_current  = 0.0

        for pos in positions:
            pid, symbol, name, qty, buy_price, _ = pos
            d = self.current_market_data.get(symbol, {})
            current_price = d.get("price") if "error" not in d else None

            invested = qty * buy_price
            total_invested += invested

            if current_price is not None:
                current_val = qty * current_price
                pnl_usd     = current_val - invested
                pnl_pct     = (pnl_usd / invested * 100) if invested else 0
                total_current += current_val
                tag = "profit" if pnl_usd >= 0 else "loss"
                self.port_tree.insert(
                    "", "end", iid=str(pid), tags=(tag,),
                    values=(
                        name or symbol, symbol,
                        f"{qty:g}",
                        f"{buy_price:,.4f}",
                        f"{current_price:,.4f}",
                        f"{current_val:,.2f}",
                        f"{pnl_usd:+,.2f}",
                        f"{pnl_pct:+.2f}%",
                    ))
            else:
                total_current += invested
                self.port_tree.insert(
                    "", "end", iid=str(pid),
                    values=(name or symbol, symbol,
                            f"{qty:g}", f"{buy_price:,.4f}",
                            "N/A", "—", "—", "—"))

        total_pnl = total_current - total_invested
        total_pct = (total_pnl / total_invested * 100) if total_invested else 0
        clr = GREEN if total_pnl >= 0 else RED
        self.port_summary_lbl.configure(fg=clr, text=(
            f"Zainwestowano: ${total_invested:,.2f}  |  "
            f"Wartość: ${total_current:,.2f}  |  "
            f"P&L: {total_pnl:+,.2f} $ ({total_pct:+.2f}%)"
        ))

    def _quick_fetch_prices(self):
        self._portfolio_status.configure(text="Pobieranie cen…")
        self.set_busy(True, "Pobieranie cen…")

        def _fetch():
            try:
                data = get_all_instruments(self.config_data.get("instruments", []))
                self.current_market_data.update(data)
                self.after(0, self._refresh_portfolio)
                self.after(0, lambda: self._update_price_tiles(data))
                self.after(0, lambda: self._portfolio_status.configure(
                    text="Ceny zaktualizowane"))
            except Exception as exc:
                self.after(0, lambda: self._portfolio_status.configure(
                    text=f"Błąd: {exc}"))
            finally:
                self.set_busy(False, "Gotowy")

        threading.Thread(target=_fetch, daemon=True).start()

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

        self.cal_status = tk.Label(ctrl, text="", bg=BG, fg=GRAY,
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

        self._load_calendar()

    def _load_calendar(self):
        self.cal_status.configure(text="Pobieranie…")

        def _fetch():
            events, err = fetch_calendar(self.cal_week_var.get())
            self._cal_events = events
            if err:
                self.after(0, lambda: self.cal_status.configure(
                    text=f"Błąd: {err[:60]}"))
            else:
                self.after(0, lambda: self.cal_status.configure(
                    text=f"{len(events)} wydarzeń"))
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

        # ── PanedWindow: chart (top) + chat (bottom) ──
        paned = tk.PanedWindow(self.tab_charts, orient="vertical", bg=BG,
                                sashwidth=5, sashrelief="flat")
        paned.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self.chart_container = tk.Frame(paned, bg=BG)
        paned.add(self.chart_container, minsize=200)

        # ── Chart chat panel ──
        self.chart_chat_frame = tk.LabelFrame(
            paned, text=" Czat o wykresie ", bg=BG, fg=ACCENT,
            font=("Segoe UI", 10, "bold"), relief="flat",
            highlightbackground=GRAY, highlightthickness=1)
        paned.add(self.chart_chat_frame, minsize=100)

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
        chart_input_bar.pack(fill="x", padx=4, pady=(0, 4))

        self.chart_chat_entry = tk.Entry(
            chart_input_bar, bg=BG2, fg=FG, insertbackground=FG,
            relief="flat", font=("Segoe UI", 10),
            highlightbackground=GRAY, highlightthickness=1)
        self.chart_chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.chart_chat_entry.bind("<Return>",
                                    lambda e: self._send_chart_chat_message())

        self.chart_chat_send_btn = tk.Button(
            chart_input_bar, text="Wyślij", bg=ACCENT, fg=BG,
            font=("Segoe UI", 10, "bold"), relief="flat",
            cursor="hand2", padx=12, command=self._send_chart_chat_message)
        self.chart_chat_send_btn.pack(side="left")

        tk.Button(
            chart_input_bar, text="Wyczyść", bg=BTN_BG, fg=GRAY,
            font=("Segoe UI", 9), relief="flat", cursor="hand2",
            padx=8, command=self._clear_chart_chat
        ).pack(side="left", padx=(4, 0))

        # Task 1 + 3: markdown tags + click-to-focus for chart chat
        setup_markdown_tags(self.chart_chat_display)
        bind_chat_focus(self.chart_chat_frame, self.chart_chat_entry)

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
            except Exception:
                pass

        # 2. Now safe to destroy Tk children (canvas, toolbar)
        for w in self.chart_container.winfo_children():
            try:
                w.destroy()
            except Exception:
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
        except Exception:
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
                except Exception:
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
    def _build_settings_tab(self):
        self._settings_canvas = tk.Canvas(
            self.tab_settings, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(self.tab_settings, orient="vertical",
                                command=self._settings_canvas.yview)
        self._settings_canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self._settings_canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(self._settings_canvas, bg=BG)
        self._settings_canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: self._settings_canvas.configure(
                       scrollregion=self._settings_canvas.bbox("all")))

        # Mousewheel scrolling for settings
        self._bind_mousewheel(self._settings_canvas, self._settings_canvas)

        def section(text):
            tk.Label(inner, text=text, bg=BG, fg=ACCENT,
                     font=("Segoe UI", 12, "bold")
                     ).pack(anchor="w", padx=16, pady=(16, 4))
            tk.Frame(inner, bg=GRAY, height=1).pack(
                fill="x", padx=16, pady=(0, 8))

        def entry_row(parent, label, var, show=""):
            f = tk.Frame(parent, bg=BG)
            f.pack(fill="x", padx=16, pady=3)
            tk.Label(f, text=label, bg=BG, fg=FG, font=("Segoe UI", 10),
                     width=22, anchor="w").pack(side="left")
            tk.Entry(f, textvariable=var, bg=BG2, fg=FG,
                     insertbackground=FG, relief="flat",
                     font=("Segoe UI", 10), show=show,
                     highlightbackground=GRAY, highlightthickness=1
                     ).pack(side="left", fill="x", expand=True, padx=4)

        section("🔑 Klucze API")
        # Klucze z env mają priorytet — w UI pokazujemy zamaskowane
        self._key_from_env = {}
        for kn in ("newsapi", "openai", "anthropic", "openrouter"):
            from config import ENV_KEY_MAP
            env_name = ENV_KEY_MAP.get(kn, "")
            self._key_from_env[kn] = bool(
                env_name and os.environ.get(env_name, "").strip())

        def _key_display(name):
            val = self.config_data["api_keys"].get(name, "")
            if self._key_from_env[name]:
                return mask_key(val) + " (ENV)"
            return val

        self.v_newsapi   = tk.StringVar(value=_key_display("newsapi"))
        self.v_openai    = tk.StringVar(value=_key_display("openai"))
        self.v_anthropic = tk.StringVar(value=_key_display("anthropic"))
        self.v_openrouter = tk.StringVar(value=_key_display("openrouter"))
        entry_row(inner, "NewsAPI:", self.v_newsapi, show="*")
        entry_row(inner, "OpenAI API Key:", self.v_openai, show="*")
        entry_row(inner, "Anthropic API Key:", self.v_anthropic, show="*")
        entry_row(inner, "OpenRouter API Key:", self.v_openrouter, show="*")

        section("🤖 Model AI")
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

        tk.Label(model_frame, text="lub wpisz:", bg=BG, fg=GRAY,
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

        section("💬 Model Czatu")
        tk.Label(
            inner,
            text="Model używany do dyskusji o raporcie (używa tych samych kluczy API).",
            bg=BG, fg=GRAY, font=("Segoe UI", 9)
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

        tk.Label(chat_model_frame, text="lub wpisz:", bg=BG, fg=GRAY,
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

        section("⏰ Harmonogram")
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

        section("📊 Instrumenty finansowe")
        tk.Label(
            inner,
            text="Symbol: ticker (np. AAPL) lub ID CoinGecko (np. bitcoin). "
                 "Źródło: yfinance / coingecko / stooq",
            bg=BG, fg=GRAY, font=("Segoe UI", 9)
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

        tk.Button(
            inner, text="➕ Dodaj instrument", bg=BTN_BG, fg=GREEN,
            font=("Segoe UI", 10), relief="flat", cursor="hand2",
            padx=10, pady=4,
            command=lambda: self._add_instrument_row({})
        ).pack(anchor="w", padx=16, pady=6)

        section("🌐 Źródła danych (strony www)")
        tk.Label(
            inner,
            text="Aplikacja pobierze treść z tych stron przed każdą analizą.",
            bg=BG, fg=GRAY, font=("Segoe UI", 9)
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

        section("📝 Prompt systemowy")
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

        section("💬 Prompt czatu")
        tk.Label(
            inner,
            text="Instrukcja systemowa dla czatu. Raport z analizy jest "
                 "dołączany automatycznie.",
            bg=BG, fg=GRAY, font=("Segoe UI", 9)
        ).pack(anchor="w", padx=16, pady=(0, 4))
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

        section("📊 Prompt czatu wykresów")
        tk.Label(
            inner,
            text="Instrukcja systemowa dla czatu na zakładce Wykresy. "
                 "Dane wykresu (symbol, okres, ceny) są dołączane automatycznie.",
            bg=BG, fg=GRAY, font=("Segoe UI", 9)
        ).pack(anchor="w", padx=16, pady=(0, 4))
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

        tk.Button(
            inner, text="💾 Zapisz ustawienia", bg=GREEN, fg=BG,
            font=("Segoe UI", 11, "bold"), relief="flat", cursor="hand2",
            padx=20, pady=8, command=self._save_settings
        ).pack(pady=16)

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

        def remove():
            self.inst_entries.remove((row_frame, v_sym, v_name, v_cat, v_src))
            row_frame.destroy()

        tk.Button(row_frame, text="✖", bg=BTN_BG, fg=RED,
                  font=("Segoe UI", 9), relief="flat", cursor="hand2",
                  padx=6, command=remove).pack(side="left")
        self.inst_entries.append((row_frame, v_sym, v_name, v_cat, v_src))

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

    def _save_settings(self):
        # Nie nadpisuj kluczy zarządzanych przez env
        for kn, var in (("newsapi", self.v_newsapi), ("openai", self.v_openai),
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
        self.port_inst_cb["values"] = inst_names
        if inst_names:
            self.v_port_inst.set(inst_names[0])

        messagebox.showinfo("Zapisano", "Ustawienia zostały zapisane!")

    # ═══════════════════════════════════════
    # CHAT
    # ═══════════════════════════════════════
    def _append_chat(self, label, text, tag):
        """Append a message to the chat display widget (markdown for assistant)."""
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", f"{label}\n", "label")
        if tag == "assistant":
            insert_markdown(self.chat_display, text, base_tag=tag)
        else:
            self.chat_display.insert("end", text, tag)
        self.chat_display.insert("end", "\n\n", tag)
        self.chat_display.configure(state="disabled")
        self.chat_display.see("end")

    def _clear_chat(self):
        self._chat_history.clear()
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        self.chat_display.configure(state="disabled")

    def _send_chat_message(self):
        msg = self.chat_entry.get().strip()
        if not msg:
            return
        self.chat_entry.delete(0, "end")
        self._append_chat("Ty:", msg, "user")

        self._chat_history.append({"role": "user", "content": msg})
        self.chat_send_btn.configure(state="disabled", text="…")

        def _worker():
            system = self.config_data.get("chat_prompt", "")
            if not system:
                system = "Jesteś asystentem inwestycyjnym. Odpowiadaj po polsku."
            system += "\n"
            if self.current_analysis:
                system += (
                    "\nPoniżej znajduje się ostatni raport analizy rynkowej, "
                    "który przygotowałeś. Użytkownik chce o nim porozmawiać.\n\n"
                    f"--- RAPORT ---\n{self.current_analysis}\n--- KONIEC RAPORTU ---"
                )

            try:
                reply = run_chat(self.config_data, list(self._chat_history), system)
            except Exception as exc:
                reply = f"Błąd połączenia: {exc}"
            self._chat_history.append({"role": "assistant", "content": reply})

            self.after(0, lambda: self._append_chat("AI:", reply, "assistant"))
            self.after(0, lambda: self.chat_send_btn.configure(
                state="normal", text="Wyślij"))
            self.after(0, lambda: self.chat_entry.focus_set())

        threading.Thread(target=_worker, daemon=True).start()

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
            newsapi_key = get_api_key(cfg, "newsapi")
            macro_text = ""
            news = []
            if newsapi_key:
                try:
                    macro_payload = build_macro_payload(newsapi_key)
                    macro_text = format_macro_payload_for_llm(macro_payload)
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(
                        "Macro-trend fallback: %s", e)
            # Fallback: legacy news if macro engine fails
            if not macro_text:
                news = get_news(
                    newsapi_key,
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
            analysis = run_analysis(cfg, summary, news, scraped_text,
                                    macro_text=macro_text)
            risk     = extract_risk_level(analysis)

            save_report(cfg["ai_provider"], cfg["ai_model"],
                        summary, analysis, risk)
            save_market_snapshot(market_data)

            self.current_analysis    = analysis
            self.current_market_data = market_data

            self.after(0, lambda: self._update_dashboard(
                analysis, risk, market_data))
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.set_busy(False, f"Błąd: {exc}")
        finally:
            self.set_busy(False, "Gotowy")
            self.after(0, lambda: self.analyze_btn.configure(
                text="▶  Uruchom Analizę"))

    def _update_dashboard(self, analysis, risk, market_data):
        self.analysis_text.configure(state="normal")
        self.analysis_text.delete("1.0", "end")
        insert_markdown(self.analysis_text, analysis)
        self.analysis_text.configure(state="disabled")

        self._update_price_tiles(market_data)
        self._refresh_portfolio()

        for w in self.gauge_frame.winfo_children():
            w.destroy()
        try:
            canvas, _ = create_risk_gauge(self.gauge_frame, risk)
            canvas.get_tk_widget().pack()
        except Exception:
            tk.Label(self.gauge_frame, text=f"Ryzyko: {risk}/10",
                     bg=BG, fg=YELLOW,
                     font=("Segoe UI", 14, "bold")).pack(pady=8)

        self._set_status(f"Analiza zakończona  •  {len(analysis)} znaków")
        self._load_history()

    # ═══════════════════════════════════════
    # PDF EXPORT
    # ═══════════════════════════════════════
    def _export_pdf(self):
        if not self.current_analysis:
            messagebox.showwarning("Brak analizy", "Najpierw uruchom analizę!")
            return
        try:
            from fpdf import FPDF
            from datetime import datetime
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            effective_w = pdf.w - pdf.l_margin - pdf.r_margin

            # Try to register a UTF-8 capable font
            use_utf8 = False
            try:
                windir = os.environ.get("WINDIR", "C:\\Windows")
                font_path = os.path.join(windir, "Fonts", "arial.ttf")
                bold_path = os.path.join(windir, "Fonts", "arialbd.ttf")
                if os.path.exists(font_path):
                    pdf.add_font("ArialUTF", "", font_path, uni=True)
                    if os.path.exists(bold_path):
                        pdf.add_font("ArialUTF", "B", bold_path, uni=True)
                    use_utf8 = True
            except Exception:
                pass

            # Title
            if use_utf8:
                pdf.set_font("ArialUTF", "B", 16)
            else:
                pdf.set_font("Helvetica", "B", 16)
            pdf.cell(effective_w, 10, "Investment Advisor - Raport",
                     ln=True, align="C")

            # Date
            if use_utf8:
                pdf.set_font("ArialUTF", "", 9)
            else:
                pdf.set_font("Helvetica", size=9)
            pdf.cell(effective_w, 6,
                     datetime.now().strftime("%Y-%m-%d %H:%M"),
                     ln=True, align="C")
            pdf.ln(6)

            # Body
            if use_utf8:
                pdf.set_font("ArialUTF", "", 10)
            else:
                pdf.set_font("Helvetica", size=10)

            for line in self.current_analysis.split("\n"):
                if not use_utf8:
                    line = line.encode("latin-1", "replace").decode("latin-1")
                pdf.set_x(pdf.l_margin)
                if not line.strip():
                    pdf.ln(4)
                else:
                    pdf.multi_cell(effective_w, 5, line)

            os.makedirs("data/reports", exist_ok=True)
            path = (f"data/reports/raport_"
                    f"{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
            pdf.output(path)
            messagebox.showinfo("PDF",
                                f"Raport zapisany:\n{os.path.abspath(path)}")
        except Exception as exc:
            messagebox.showerror("Błąd PDF", str(exc))

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

    def set_busy(self, is_busy, message="Pracuję…"):
        """Lock/unlock buttons and start/stop spinner animation.

        Thread-safe: schedules all UI changes on the main thread.
        """
        def _apply():
            if is_busy:
                for btn in self._busy_buttons:
                    try:
                        btn.configure(state="disabled")
                    except Exception:
                        pass
                if self._spinner:
                    self._spinner.start(message)
            else:
                for btn in self._busy_buttons:
                    try:
                        btn.configure(state="normal")
                    except Exception:
                        pass
                if self._spinner:
                    self._spinner.stop(message)
        if self._shutting_down:
            return
        try:
            self.after(0, _apply)
        except RuntimeError:
            pass

    def _on_close(self):
        """Clean shutdown: close all matplotlib figures before destroying Tk."""
        self._shutting_down = True
        try:
            if self._current_chart_fig:
                plt.close(self._current_chart_fig)
                self._current_chart_fig = None
            plt.close("all")
        except Exception:
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
