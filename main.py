import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import schedule
import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from config import load_config, save_config
from modules.market_data import get_all_instruments, get_news, format_market_summary
from modules.ai_engine import run_analysis, get_available_models
from modules.database import save_report, get_reports, get_report_by_id, save_market_snapshot, get_unseen_alerts, mark_alerts_seen, delete_report
from modules.charts import create_price_chart, create_risk_gauge, extract_risk_level
from modules.scraper import scrape_all

BG = "#1e1e2e"
BG2 = "#181825"
FG = "#cdd6f4"
ACCENT = "#89b4fa"
GREEN = "#a6e3a1"
RED = "#f38ba8"
YELLOW = "#f9e2af"
GRAY = "#313244"
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
        self.inst_entries = []
        self.source_entries = []
        self._build_ui()
        self._start_scheduler()
        self._check_alerts()

    # ── UI ──
    def _build_ui(self):
        top = tk.Frame(self, bg=BG2, height=50)
        top.pack(fill="x")
        tk.Label(top, text="📈 Investment Advisor", bg=BG2, fg=ACCENT,
                 font=("Segoe UI", 16, "bold")).pack(side="left", padx=16, pady=8)
        self.alert_btn = tk.Button(top, text="🔔 Alerty", bg=BTN_BG, fg=YELLOW,
                                   font=("Segoe UI", 10), relief="flat", cursor="hand2",
                                   command=self._show_alerts)
        self.alert_btn.pack(side="right", padx=8, pady=8)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BTN_BG, foreground=FG,
                        padding=[12, 6], font=("Segoe UI", 10))
        style.map("TNotebook.Tab", background=[("selected", ACCENT)],
                  foreground=[("selected", BG)])

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.tab_dashboard = tk.Frame(self.notebook, bg=BG)
        self.tab_charts    = tk.Frame(self.notebook, bg=BG)
        self.tab_history   = tk.Frame(self.notebook, bg=BG)
        self.tab_settings  = tk.Frame(self.notebook, bg=BG)

        self.notebook.add(self.tab_dashboard, text="  🏠 Dashboard  ")
        self.notebook.add(self.tab_charts,    text="  📊 Wykresy  ")
        self.notebook.add(self.tab_history,   text="  📋 Historia  ")
        self.notebook.add(self.tab_settings,  text="  ⚙️ Ustawienia  ")

        self._build_dashboard()
        self._build_charts_tab()
        self._build_history_tab()
        self._build_settings_tab()

    # ── DASHBOARD ──
    def _build_dashboard(self):
        left = tk.Frame(self.tab_dashboard, bg=BG, width=320)
        left.pack(side="left", fill="y", padx=(8, 4), pady=8)
        left.pack_propagate(False)

        risk_frame = tk.LabelFrame(left, text=" Ryzyko Rynkowe ", bg=BG, fg=ACCENT,
                                   font=("Segoe UI", 10, "bold"), relief="flat",
                                   highlightbackground=GRAY, highlightthickness=1)
        risk_frame.pack(fill="x", pady=(0, 8))
        self.gauge_frame = tk.Frame(risk_frame, bg=BG)
        self.gauge_frame.pack()

        prices_frame = tk.LabelFrame(left, text=" Kursy Rynkowe ", bg=BG, fg=ACCENT,
                                     font=("Segoe UI", 10, "bold"), relief="flat",
                                     highlightbackground=GRAY, highlightthickness=1)
        prices_frame.pack(fill="both", expand=True)

        self.prices_text = tk.Text(prices_frame, bg=BG2, fg=FG, font=("Consolas", 9),
                                   relief="flat", state="disabled", wrap="none")
        self.prices_text.pack(fill="both", expand=True, padx=4, pady=4)

        right = tk.Frame(self.tab_dashboard, bg=BG)
        right.pack(side="right", fill="both", expand=True, padx=(4, 8), pady=8)

        btn_bar = tk.Frame(right, bg=BG)
        btn_bar.pack(fill="x", pady=(0, 6))

        self.analyze_btn = tk.Button(btn_bar, text="▶  Uruchom Analizę", bg=ACCENT, fg=BG,
                                     font=("Segoe UI", 11, "bold"), relief="flat",
                                     cursor="hand2", padx=16, pady=6,
                                     command=self._run_analysis_thread)
        self.analyze_btn.pack(side="left")

        tk.Button(btn_bar, text="📄 Eksport PDF", bg=BTN_BG, fg=FG,
                  font=("Segoe UI", 10), relief="flat", cursor="hand2",
                  padx=12, pady=6, command=self._export_pdf).pack(side="left", padx=8)

        self.status_label = tk.Label(btn_bar, text="Gotowy", bg=BG, fg=GRAY,
                                     font=("Segoe UI", 9))
        self.status_label.pack(side="right", padx=8)

        analysis_frame = tk.LabelFrame(right, text=" Analiza AI ", bg=BG, fg=ACCENT,
                                       font=("Segoe UI", 10, "bold"), relief="flat",
                                       highlightbackground=GRAY, highlightthickness=1)
        analysis_frame.pack(fill="both", expand=True)

        self.analysis_text = scrolledtext.ScrolledText(
            analysis_frame, bg=BG2, fg=FG, font=("Segoe UI", 10),
            relief="flat", wrap="word", state="disabled",
            insertbackground=FG, selectbackground=ACCENT)
        self.analysis_text.pack(fill="both", expand=True, padx=4, pady=4)

    # ── WYKRESY ──
    def _build_charts_tab(self):
        ctrl = tk.Frame(self.tab_charts, bg=BG)
        ctrl.pack(fill="x", padx=12, pady=8)

        tk.Label(ctrl, text="Instrument:", bg=BG, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left")

        all_symbols = [i["symbol"] for i in self.config_data.get("instruments", [])]
        self.chart_symbol_var = tk.StringVar(value=all_symbols[0] if all_symbols else "SPY")
        self.chart_sym_cb = ttk.Combobox(ctrl, textvariable=self.chart_symbol_var,
                                          values=all_symbols, width=14, state="readonly")
        self.chart_sym_cb.pack(side="left", padx=6)

        tk.Label(ctrl, text="Okres:", bg=BG, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left", padx=(12, 0))
        self.chart_period_var = tk.StringVar(value="1M")
        for p in ["1T", "5T", "1M", "3M", "6M", "1R", "2R"]:
            tk.Radiobutton(ctrl, text=p, variable=self.chart_period_var, value=p,
                           bg=BG, fg=FG, selectcolor=ACCENT, activebackground=BG,
                           font=("Segoe UI", 9)).pack(side="left", padx=2)

        tk.Label(ctrl, text="Porównaj:", bg=BG, fg=FG,
                 font=("Segoe UI", 10)).pack(side="left", padx=(12, 0))
        self.compare_var = tk.StringVar()
        self.compare_cb = ttk.Combobox(ctrl, textvariable=self.compare_var,
                                        values=[""] + all_symbols, width=14, state="readonly")
        self.compare_cb.pack(side="left", padx=6)

        tk.Button(ctrl, text="📊 Rysuj", bg=ACCENT, fg=BG,
                  font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
                  padx=12, pady=4, command=self._draw_chart).pack(side="left", padx=8)

        self.chart_container = tk.Frame(self.tab_charts, bg=BG)
        self.chart_container.pack(fill="both", expand=True, padx=12, pady=(0, 8))

    def _draw_chart(self):
        for w in self.chart_container.winfo_children():
            w.destroy()
        symbol = self.chart_symbol_var.get()
        period = self.chart_period_var.get()
        compare = [self.compare_var.get()] if self.compare_var.get() else None
        try:
            canvas, fig = create_price_chart(self.chart_container, symbol, period, compare)
            canvas.get_tk_widget().pack(fill="both", expand=True)
        except Exception as e:
            tk.Label(self.chart_container, text=f"Błąd wykresu: {e}",
                     bg=BG, fg=RED, font=("Segoe UI", 11)).pack(pady=20)

    def _refresh_chart_symbols(self):
        """Odświeża listę symboli w zakładce Wykresy po zapisie ustawień."""
        symbols = [i["symbol"] for i in self.config_data.get("instruments", [])]
        self.chart_sym_cb["values"] = symbols
        self.compare_cb["values"] = [""] + symbols

    # ── HISTORIA ──
    def _build_history_tab(self):
        top = tk.Frame(self.tab_history, bg=BG)
        top.pack(fill="x", padx=12, pady=8)
        tk.Button(top, text="🔄 Odśwież", bg=BTN_BG, fg=FG,
                  font=("Segoe UI", 10), relief="flat", cursor="hand2",
                  padx=10, pady=4, command=self._load_history).pack(side="left")
        tk.Button(top, text="🗑️ Usuń zaznaczony", bg=BTN_BG, fg=RED,
                  font=("Segoe UI", 10), relief="flat", cursor="hand2",
                  padx=10, pady=4, command=self._delete_selected_report).pack(side="left", padx=8)

        paned = tk.PanedWindow(self.tab_history, orient="horizontal", bg=BG, sashwidth=4)
        paned.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        list_frame = tk.Frame(paned, bg=BG)
        paned.add(list_frame, minsize=280)

        cols = ("Data", "Model", "Ryzyko")
        self.history_tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=20)
        style = ttk.Style()
        style.configure("Treeview", background=BG2, foreground=FG,
                        fieldbackground=BG2, rowheight=24)
        style.configure("Treeview.Heading", background=BTN_BG, foreground=ACCENT)
        for col in cols:
            self.history_tree.heading(col, text=col)
            self.history_tree.column(col, width=90 if col != "Data" else 140)
        self.history_tree.pack(fill="both", expand=True)
        self.history_tree.bind("<<TreeviewSelect>>", self._on_report_select)

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
            self.history_tree.insert("", "end", iid=str(rid),
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
        if messagebox.askyesno("Usuń raport", "Czy na pewno usunąć wybrany raport?"):
            delete_report(int(sel[0]))
            self._load_history()

    # ── USTAWIENIA ──
    def _build_settings_tab(self):
        canvas = tk.Canvas(self.tab_settings, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(self.tab_settings, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=BG)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def section(text):
            tk.Label(inner, text=text, bg=BG, fg=ACCENT,
                     font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=16, pady=(16, 4))
            tk.Frame(inner, bg=GRAY, height=1).pack(fill="x", padx=16, pady=(0, 8))

        def entry_row(parent, label, var, show=""):
            f = tk.Frame(parent, bg=BG)
            f.pack(fill="x", padx=16, pady=3)
            tk.Label(f, text=label, bg=BG, fg=FG, font=("Segoe UI", 10),
                     width=22, anchor="w").pack(side="left")
            tk.Entry(f, textvariable=var, bg=BG2, fg=FG, insertbackground=FG,
                     relief="flat", font=("Segoe UI", 10), show=show,
                     highlightbackground=GRAY, highlightthickness=1).pack(side="left", fill="x", expand=True, padx=4)

        # API Keys
        section("🔑 Klucze API")
        self.v_newsapi   = tk.StringVar(value=self.config_data["api_keys"].get("newsapi", ""))
        self.v_openai    = tk.StringVar(value=self.config_data["api_keys"].get("openai", ""))
        self.v_anthropic = tk.StringVar(value=self.config_data["api_keys"].get("anthropic", ""))
        entry_row(inner, "NewsAPI:", self.v_newsapi, show="*")
        entry_row(inner, "OpenAI API Key:", self.v_openai, show="*")
        entry_row(inner, "Anthropic API Key:", self.v_anthropic, show="*")

        # Model AI
        section("🤖 Model AI")
        prov_frame = tk.Frame(inner, bg=BG)
        prov_frame.pack(fill="x", padx=16, pady=3)
        tk.Label(prov_frame, text="Dostawca:", bg=BG, fg=FG,
                 font=("Segoe UI", 10), width=22, anchor="w").pack(side="left")
        self.v_provider = tk.StringVar(value=self.config_data.get("ai_provider", "anthropic"))
        for p in ["anthropic", "openai"]:
            tk.Radiobutton(prov_frame, text=p.capitalize(), variable=self.v_provider, value=p,
                           bg=BG, fg=FG, selectcolor=ACCENT, activebackground=BG,
                           font=("Segoe UI", 10),
                           command=self._update_model_list).pack(side="left", padx=8)

        model_frame = tk.Frame(inner, bg=BG)
        model_frame.pack(fill="x", padx=16, pady=3)
        tk.Label(model_frame, text="Model:", bg=BG, fg=FG,
                 font=("Segoe UI", 10), width=22, anchor="w").pack(side="left")
        self.v_model = tk.StringVar(value=self.config_data.get("ai_model", "claude-opus-4-6"))
        self.model_cb = ttk.Combobox(model_frame, textvariable=self.v_model, width=30, state="readonly")
        self.model_cb.pack(side="left", padx=4)
        self._update_model_list()

        # Harmonogram
        section("⏰ Harmonogram")
        sched_frame = tk.Frame(inner, bg=BG)
        sched_frame.pack(fill="x", padx=16, pady=3)
        self.v_sched_enabled = tk.BooleanVar(value=self.config_data["schedule"].get("enabled", False))
        tk.Checkbutton(sched_frame, text="Włącz automatyczną analizę",
                       variable=self.v_sched_enabled, bg=BG, fg=FG,
                       selectcolor=ACCENT, activebackground=BG,
                       font=("Segoe UI", 10)).pack(side="left")

        times_frame = tk.Frame(inner, bg=BG)
        times_frame.pack(fill="x", padx=16, pady=3)
        tk.Label(times_frame, text="Godziny (HH:MM, przecinek):", bg=BG, fg=FG,
                 font=("Segoe UI", 10), width=28, anchor="w").pack(side="left")
        self.v_times = tk.StringVar(value=", ".join(self.config_data["schedule"].get("times", ["08:00"])))
        tk.Entry(times_frame, textvariable=self.v_times, bg=BG2, fg=FG,
                 insertbackground=FG, relief="flat", font=("Segoe UI", 10),
                 highlightbackground=GRAY, highlightthickness=1).pack(side="left", fill="x", expand=True, padx=4)

        # Instrumenty
        section("📊 Instrumenty finansowe")
        tk.Label(inner,
                 text="Symbol: ticker giełdowy (np. AAPL) lub ID CoinGecko (np. bitcoin). Źródło: yfinance / coingecko / stooq",
                 bg=BG, fg=GRAY, font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(0, 6))

        hdr = tk.Frame(inner, bg=BG)
        hdr.pack(fill="x", padx=16)
        for txt, w in [("Symbol", 12), ("Nazwa", 18), ("Kategoria", 14), ("Źródło", 12)]:
            tk.Label(hdr, text=txt, bg=BG, fg=ACCENT,
                     font=("Segoe UI", 9, "bold"), width=w, anchor="w").pack(side="left")

        self.inst_frame = tk.Frame(inner, bg=BG)
        self.inst_frame.pack(fill="x", padx=16, pady=4)

        for inst in self.config_data.get("instruments", []):
            self._add_instrument_row(inst)

        tk.Button(inner, text="➕ Dodaj instrument", bg=BTN_BG, fg=GREEN,
                  font=("Segoe UI", 10), relief="flat", cursor="hand2",
                  padx=10, pady=4,
                  command=lambda: self._add_instrument_row({})).pack(anchor="w", padx=16, pady=6)

        # Źródła www
        section("🌐 Źródła danych (strony www)")
        tk.Label(inner, text="Aplikacja pobierze treść z tych stron przed każdą analizą.",
                 bg=BG, fg=GRAY, font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(0, 6))

        self.sources_frame = tk.Frame(inner, bg=BG)
        self.sources_frame.pack(fill="x", padx=16, pady=4)

        for url in self.config_data.get("sources", []):
            self._add_source_row(url)

        tk.Button(inner, text="➕ Dodaj źródło", bg=BTN_BG, fg=GREEN,
                  font=("Segoe UI", 10), relief="flat", cursor="hand2",
                  padx=10, pady=4, command=lambda: self._add_source_row("")).pack(anchor="w", padx=16, pady=6)

        # Prompt
        section("📝 Prompt systemowy")
        self.prompt_text = scrolledtext.ScrolledText(inner, bg=BG2, fg=FG,
                                                      font=("Segoe UI", 10), height=10,
                                                      relief="flat", wrap="word",
                                                      insertbackground=FG)
        self.prompt_text.pack(fill="x", padx=16, pady=4)
        self.prompt_text.insert("end", self.config_data.get("prompt", ""))

        tk.Button(inner, text="🔄 Przywróć domyślny prompt", bg=BTN_BG, fg=YELLOW,
                  font=("Segoe UI", 9), relief="flat", cursor="hand2",
                  command=self._reset_prompt).pack(anchor="w", padx=16, pady=2)

        tk.Button(inner, text="💾 Zapisz ustawienia", bg=GREEN, fg=BG,
                  font=("Segoe UI", 11, "bold"), relief="flat", cursor="hand2",
                  padx=20, pady=8, command=self._save_settings).pack(pady=16)

    def _add_instrument_row(self, inst={}):
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
        ttk.Combobox(row_frame, textvariable=v_cat, width=12, state="readonly",
                     values=["Akcje", "Krypto", "Forex", "Surowce", "Inne"]
                     ).pack(side="left", padx=(0, 4))
        ttk.Combobox(row_frame, textvariable=v_src, width=10, state="readonly",
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
                 highlightbackground=GRAY, highlightthickness=1).pack(side="left", fill="x", expand=True, padx=(0, 6))

        def remove():
            self.source_entries.remove((row_frame, var))
            row_frame.destroy()

        tk.Button(row_frame, text="✖", bg=BTN_BG, fg=RED,
                  font=("Segoe UI", 10), relief="flat", cursor="hand2",
                  padx=6, command=remove).pack(side="left")
        self.source_entries.append((row_frame, var))

    def _update_model_list(self):
        models = get_available_models(self.v_provider.get())
        self.model_cb["values"] = models
        if models:
            self.v_model.set(models[0])

    def _reset_prompt(self):
        from config import DEFAULT_CONFIG
        self.prompt_text.delete("1.0", "end")
        self.prompt_text.insert("end", DEFAULT_CONFIG["prompt"])

    def _save_settings(self):
        self.config_data["api_keys"]["newsapi"]   = self.v_newsapi.get().strip()
        self.config_data["api_keys"]["openai"]    = self.v_openai.get().strip()
        self.config_data["api_keys"]["anthropic"] = self.v_anthropic.get().strip()
        self.config_data["ai_provider"] = self.v_provider.get()
        self.config_data["ai_model"]    = self.v_model.get()
        self.config_data["schedule"]["enabled"] = self.v_sched_enabled.get()
        self.config_data["schedule"]["times"] = [t.strip() for t in self.v_times.get().split(",") if t.strip()]
        self.config_data["prompt"] = self.prompt_text.get("1.0", "end").strip()

        instruments = []
        for _, v_sym, v_name, v_cat, v_src in self.inst_entries:
            if v_sym.get().strip():
                instruments.append({
                    "symbol":   v_sym.get().strip(),
                    "name":     v_name.get().strip(),
                    "category": v_cat.get(),
                    "source":   v_src.get()
                })
        self.config_data["instruments"] = instruments

        sources = [var.get().strip() for _, var in self.source_entries if var.get().strip()]
        self.config_data["sources"] = sources

        save_config(self.config_data)
        self._refresh_chart_symbols()
        self._start_scheduler()
        messagebox.showinfo("Zapisano", "Ustawienia zostały zapisane!")

    # ── ANALIZA ──
    def _run_analysis_thread(self):
        self.analyze_btn.configure(state="disabled", text="⏳ Analizuję...")
        self._set_status("Pobieranie danych...")
        threading.Thread(target=self._run_analysis, daemon=True).start()

    def _run_analysis(self):
        try:
            cfg = self.config_data

            self._set_status("Pobieranie danych instrumentów...")
            market_data = get_all_instruments(cfg.get("instruments", []))

            self._set_status("Pobieranie newsów...")
            news = get_news(cfg["api_keys"].get("newsapi", ""),
                            query="geopolitics economy markets finance", language="en")

            scraped_text = ""
            sources = cfg.get("sources", [])
            if sources:
                self._set_status(f"Pobieranie treści z {len(sources)} źródeł www...")
                scraped_text = scrape_all(sources, max_chars_per_site=2000)

            self._set_status("Generowanie analizy AI...")
            summary = format_market_summary(market_data)
            analysis = run_analysis(cfg, summary, news, scraped_text)

            risk = extract_risk_level(analysis)
            save_report(cfg["ai_provider"], cfg["ai_model"], summary, analysis, risk)
            save_market_snapshot(market_data)

            self.current_analysis = analysis
            self.current_market_data = market_data

            self.after(0, lambda: self._update_dashboard(summary, analysis, risk))
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.after(0, lambda: self._set_status(f"Błąd: {e}"))
        finally:
            self.after(0, lambda: self.analyze_btn.configure(state="normal", text="▶  Uruchom Analizę"))

    def _update_dashboard(self, summary, analysis, risk):
        self.analysis_text.configure(state="normal")
        self.analysis_text.delete("1.0", "end")
        self.analysis_text.insert("end", analysis)
        self.analysis_text.configure(state="disabled")

        self.prices_text.configure(state="normal")
        self.prices_text.delete("1.0", "end")
        self.prices_text.tag_configure("green",  foreground=GREEN)
        self.prices_text.tag_configure("red",    foreground=RED)
        self.prices_text.tag_configure("header", foreground=ACCENT, font=("Consolas", 9, "bold"))
        self.prices_text.tag_configure("normal", foreground=FG)
        for line in summary.split("\n"):
            if line.startswith("===") or line.startswith("📈") or line.startswith("🪙") or \
               line.startswith("💱") or line.startswith("🛢") or line.startswith("📊"):
                self.prices_text.insert("end", line + "\n", "header")
            elif "▲" in line:
                self.prices_text.insert("end", line + "\n", "green")
            elif "▼" in line:
                self.prices_text.insert("end", line + "\n", "red")
            else:
                self.prices_text.insert("end", line + "\n", "normal")
        self.prices_text.configure(state="disabled")

        for w in self.gauge_frame.winfo_children():
            w.destroy()
        try:
            canvas, _ = create_risk_gauge(self.gauge_frame, risk)
            canvas.get_tk_widget().pack()
        except Exception:
            tk.Label(self.gauge_frame, text=f"Ryzyko: {risk}/10",
                     bg=BG, fg=YELLOW, font=("Segoe UI", 14, "bold")).pack(pady=8)

        self._set_status(f"Analiza zakończona • {len(analysis)} znaków")
        self._load_history()

    # ── PDF ──
    def _export_pdf(self):
        if not self.current_analysis:
            messagebox.showwarning("Brak analizy", "Najpierw uruchom analizę!")
            return
        try:
            from fpdf import FPDF
            from datetime import datetime
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 10, "Investment Advisor - Raport", ln=True, align="C")
            pdf.set_font("Helvetica", size=9)
            pdf.cell(0, 6, datetime.now().strftime("%Y-%m-%d %H:%M"), ln=True, align="C")
            pdf.ln(6)
            pdf.set_font("Helvetica", size=10)
            for line in self.current_analysis.split("\n"):
                safe = line.encode("latin-1", "replace").decode("latin-1")
                pdf.multi_cell(0, 5, safe)
            path = f"data/reports/raport_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
            pdf.output(path)
            messagebox.showinfo("PDF", f"Raport zapisany:\n{os.path.abspath(path)}")
        except Exception as e:
            messagebox.showerror("Błąd PDF", str(e))

    # ── ALERTY ──
    def _check_alerts(self):
        alerts = get_unseen_alerts()
        if alerts:
            self.alert_btn.configure(fg=RED, text=f"🔔 Alerty ({len(alerts)})")
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
            tk.Label(f, text=a[3], bg=BG2, fg=FG,
                     font=("Segoe UI", 9), wraplength=460).pack(anchor="w", padx=8)

    # ── SCHEDULER ──
    def _start_scheduler(self):
        schedule.clear()
        if self.config_data["schedule"].get("enabled"):
            for t in self.config_data["schedule"].get("times", []):
                schedule.every().day.at(t).do(self._run_analysis_thread)

        def runner():
            while True:
                schedule.run_pending()
                time.sleep(30)

        threading.Thread(target=runner, daemon=True).start()

    def _set_status(self, msg):
        self.status_label.configure(text=msg)
        self.update_idletasks()

if __name__ == "__main__":
    print("Start...")
    try:
        app = InvestmentAdvisor()
        print("Okno utworzone!")
        app.mainloop()
    except Exception as e:
        import traceback
        traceback.print_exc()
        input("Nacisnij Enter aby zamknac...")