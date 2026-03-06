import { useEffect, useRef, useState } from 'react';
import api from '../api/client';
import InstrumentSearch from '../components/InstrumentSearch';
import { clearInstrumentsCache, triggerInstrumentsRefresh } from '../api/market';
import { getStats, type StatsResponse } from '../api/stats';
import { APP_TIMEZONE } from '../config';
import { useAuthStore } from '../stores/authStore';

type TabKey = 'general' | 'customize' | 'prompts' | 'stats';

interface Instrument {
  symbol: string;
  name: string;
  category: string;
  source: string;
}

const TABS: { key: TabKey; label: string }[] = [
  { key: 'general', label: 'Ogolne' },
  { key: 'customize', label: 'Dostosuj' },
  { key: 'prompts', label: 'Prompty' },
  { key: 'stats', label: 'Statystyki' },
];

const PROVIDERS = ['anthropic', 'openai', 'openrouter'];
const SOURCES = ['yfinance', 'coingecko', 'stooq'];

const MODEL_OPTIONS: Record<string, { value: string; label: string }[]> = {
  openai: [
    { value: 'gpt-4.1-mini', label: 'GPT-4.1 Mini' },
    { value: 'o3-mini',      label: 'o3 Mini' },
    { value: 'gpt-4o',       label: 'GPT-4o' },
    { value: 'gpt-4.1',      label: 'GPT-4.1' },
  ],
  anthropic: [
    { value: 'claude-haiku-4-5-20251001', label: 'Haiku' },
    { value: 'claude-sonnet-4-6',         label: 'Sonnet' },
  ],
};
const CATEGORIES = ['Akcje / Indeksy', 'Krypto', 'Forex', 'Surowce', 'Inne'];

/** Auto-detect category and source from Yahoo search result type and symbol */
function detectCategoryAndSource(symbol: string, type?: string): { category: string; source: string } {
  const s = symbol.toUpperCase();
  const t = (type ?? '').toLowerCase();

  // Forex
  if (t === 'currency' || /^[A-Z]{3}[A-Z]{3}=X$/.test(s)) {
    return { category: 'Forex', source: 'yfinance' };
  }
  // Crypto
  if (t === 'cryptocurrency' || /-USD$/.test(s)) {
    return { category: 'Krypto', source: 'yfinance' };
  }
  // Futures / commodities
  if (t === 'future' || s.endsWith('=F')) {
    return { category: 'Surowce', source: 'yfinance' };
  }
  // Index
  if (t === 'index' || s.startsWith('^')) {
    return { category: 'Akcje / Indeksy', source: 'yfinance' };
  }
  // Equity, ETF, Mutual Fund
  if (t === 'equity' || t === 'etf' || t === 'mutualfund') {
    return { category: 'Akcje / Indeksy', source: 'yfinance' };
  }
  return { category: 'Akcje / Indeksy', source: 'yfinance' };
}

// ── Prompt card types & components ──────────────────────────────────────────

interface PromptCardDef {
  key: string;
  title: string;
  desc: string;
  value: string;
  setValue: (v: string) => void;
  contextLines: string[];
  rows: number;
  placeholder?: string;
}

function ExpandIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 1h4v4M5 13H1V9M13 1 8 6M1 13l5-5" />
    </svg>
  );
}

function PromptCard({ def, defaultValue, ctxOpen, onToggleCtx, onExpand }: {
  def: PromptCardDef;
  defaultValue: string;
  ctxOpen: boolean;
  onToggleCtx: () => void;
  onExpand: () => void;
}) {
  return (
    <section className="bg-[var(--bg2)] rounded-xl border border-[var(--gray)] overflow-hidden flex flex-col">
      {/* Baner — kliknij aby pokazać kontekst */}
      <div
        className="px-4 py-3 border-b border-[var(--gray)] cursor-pointer select-none hover:bg-[var(--gray)]/20 transition-colors"
        onClick={onToggleCtx}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold">{def.title}</h2>
            <p className="text-xs text-[var(--overlay)] mt-0.5 leading-relaxed">{def.desc}</p>
          </div>
          <div className="flex items-center gap-1.5 flex-shrink-0 mt-0.5">
            <button
              onClick={(e) => { e.stopPropagation(); onExpand(); }}
              title="Powiększ edytor"
              className="p-1 rounded text-[var(--overlay)] hover:text-[var(--fg)] hover:bg-[var(--gray)]/60 transition-colors"
            >
              <ExpandIcon />
            </button>
            <span className="text-[var(--overlay)] text-[10px]">{ctxOpen ? '▲' : '▼'}</span>
          </div>
        </div>
      </div>

      {/* Panel kontekstu agenta */}
      {ctxOpen && (
        <div className="px-4 py-3 border-b border-[var(--gray)] bg-[var(--bg)]/60">
          <p className="text-[10px] font-semibold text-[var(--overlay)] uppercase tracking-widest mb-2">
            Kontekst dołączany do tego promptu:
          </p>
          <ul className="space-y-1">
            {def.contextLines.map((line, i) => (
              <li key={i} className="text-xs text-[var(--fg)]/70 flex gap-2">
                <span className="text-[var(--accent)] flex-shrink-0 mt-px">▪</span>
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Textarea */}
      <div className="p-4 flex-1">
        <textarea
          value={def.value}
          onChange={(e) => def.setValue(e.target.value)}
          rows={def.rows}
          placeholder={def.placeholder}
          className="w-full bg-[var(--bg)] border border-[var(--gray)] rounded-lg px-3 py-2 text-sm font-mono text-[var(--fg)] focus:border-[var(--accent)] outline-none resize-y transition-colors"
        />
      </div>

      {/* Stopka */}
      <div className="px-4 pb-3 flex items-center justify-between">
        <span className="text-xs text-[var(--overlay)]">{def.value.length} znaków</span>
        {defaultValue && (
          <button
            onClick={() => def.setValue(defaultValue)}
            title="Przywróć fabryczny prompt domyślny"
            className="text-xs text-[var(--overlay)] hover:text-[var(--accent)] transition-colors underline underline-offset-2"
          >
            Ustaw domyślny
          </button>
        )}
      </div>
    </section>
  );
}

export default function Settings() {
  const [activeTab, setActiveTab] = useState<TabKey>('general');
  const [loading, setLoading] = useState(true);
  const [saved, setSaved] = useState(false);

  // General
  const [keys, setKeys] = useState({ anthropic: '', openai: '', openrouter: '', newsdata: '' });
  const [provider, setProvider] = useState('openai');
  const [model, setModel] = useState('gpt-4.1-mini');
  const [chatProvider, setChatProvider] = useState('openai');
  const [chatModel, setChatModel] = useState('gpt-4.1-mini');

  // Customize
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [newInst, setNewInst] = useState<Instrument>({ symbol: '', name: '', category: 'Akcje / Indeksy', source: 'yfinance' });
  const [showAddForm, setShowAddForm] = useState(false);

  // Sources
  const [sources, setSources] = useState<string[]>([]);
  const [newSource, setNewSource] = useState('');
  const [showAddSource, setShowAddSource] = useState(false);

  // Saved server state — for detecting unsaved changes
  const savedInstrumentsRef = useRef<string>('[]');
  const savedSourcesRef = useRef<string>('[]');

  // Prompts
  const [prompt, setPrompt] = useState('');
  const [chatPrompt, setChatPrompt] = useState('');
  const [chartsChatPrompt, setChartsChatPrompt] = useState('');
  const [instrumentProfilePrompt, setInstrumentProfilePrompt] = useState('');
  const [calendarEventPrompt, setCalendarEventPrompt] = useState('');
  const [assessmentPrompt, setAssessmentPrompt] = useState('');

  // Prompt editor state
  const [defaults, setDefaults] = useState<Record<string, string>>({});
  const [expandedKey, setExpandedKey] = useState<string | null>(null);
  const [ctxOpen, setCtxOpen] = useState<Record<string, boolean>>({});

  // Stats
  const loginTime = useAuthStore((s) => s.loginTime);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  useEffect(() => {
    api.get('/settings').then((res) => {
      const d = res.data;
      const apiKeys = (d.api_keys || {}) as Record<string, string>;
      setKeys({
        anthropic: apiKeys.anthropic || '',
        openai: apiKeys.openai || '',
        openrouter: apiKeys.openrouter || '',
        newsdata: apiKeys.newsdata || '',
      });
      setProvider(d.ai_provider || 'openai');
      setModel(d.ai_model || 'gpt-4.1-mini');
      setChatProvider(d.chat_provider || d.ai_provider || 'openai');
      setChatModel(d.chat_model || d.ai_model || 'gpt-4.1-mini');
      const inst = d.instruments || [];
      const src = d.sources || [];
      setInstruments(inst);
      setSources(src);
      savedInstrumentsRef.current = JSON.stringify(inst);
      savedSourcesRef.current = JSON.stringify(src);
      setPrompt(d.prompt || '');
      setChatPrompt(d.chat_prompt || '');
      setChartsChatPrompt(d.charts_chat_prompt || '');
      setInstrumentProfilePrompt(d.instrument_profile_prompt || '');
      setCalendarEventPrompt(d.calendar_event_prompt || '');
      setAssessmentPrompt(d.market_assessment_prompt || '');
    }).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    api.get('/settings/defaults').then((r) => setDefaults(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (activeTab !== 'stats') return;
    setStatsLoading(true);
    getStats(loginTime ?? undefined)
      .then(setStats)
      .catch(() => setStats(null))
      .finally(() => setStatsLoading(false));
  }, [activeTab, loginTime]);

  const notify = () => { setSaved(true); setTimeout(() => setSaved(false), 2000); };

  const saveGeneral = async () => {
    const apiKeysToSend: Record<string, string> = {};
    for (const [k, v] of Object.entries(keys)) {
      if (v && !v.includes('*')) apiKeysToSend[k] = v;
    }
    await api.put('/settings', {
      api_keys: apiKeysToSend,
      ai_provider: provider,
      ai_model: model,
      chat_provider: chatProvider,
      chat_model: chatModel,
    });
    notify();
  };

  const saveCustomize = async () => {
    await api.put('/settings', { instruments, sources });
    savedInstrumentsRef.current = JSON.stringify(instruments);
    savedSourcesRef.current = JSON.stringify(sources);
    clearInstrumentsCache();
    triggerInstrumentsRefresh();
    notify();
  };

  const addSource = () => {
    let url = newSource.trim();
    if (!url) return;
    // Automatycznie uzupełnij protokół jeśli brakuje
    if (!/^https?:\/\//i.test(url)) {
      url = 'https://' + url;
    }
    if (sources.includes(url)) return;
    setSources([...sources, url]);
    setNewSource('');
    setShowAddSource(false);
  };
  const savePrompts = async () => { await api.put('/settings', { prompt, chat_prompt: chatPrompt, charts_chat_prompt: chartsChatPrompt, instrument_profile_prompt: instrumentProfilePrompt, calendar_event_prompt: calendarEventPrompt, market_assessment_prompt: assessmentPrompt }); notify(); };

  const addInstrument = () => {
    if (!newInst.symbol.trim()) return;
    setInstruments([...instruments, {
      ...newInst,
      symbol: newInst.symbol.trim().toUpperCase(),
      name: newInst.name.trim() || newInst.symbol.trim(),
    }]);
    setNewInst({ symbol: '', name: '', category: 'Akcje / Indeksy', source: 'yfinance' });
    setShowAddForm(false);
  };

  const promptDefs: PromptCardDef[] = [
    {
      key: 'prompt',
      title: 'Analiza rynkowa',
      desc: 'System prompt wysyłany do AI przy generowaniu raportu',
      value: prompt, setValue: setPrompt, rows: 14,
      placeholder: 'Wprowadź system prompt dla analizy...',
      contextLines: [
        'Dane rynkowe wszystkich instrumentów (ceny, zmiana %, sparkline)',
        'Treści pobrane ze skonfigurowanych stron web (scraper)',
        'Newsy z Newsdata.io (ostatnie 24h)',
        'Trendy makro — porównanie 24h / 7d / 30d / 90d',
        'Portfel użytkownika',
        'Kalendarz ekonomiczny (7 dni, zdarzenia High i Medium)',
      ],
    },
    {
      key: 'chat_prompt',
      title: 'Chat AI — Dashboard',
      desc: 'System prompt dla chatu na zakładce Dashboard',
      value: chatPrompt, setValue: setChatPrompt, rows: 10,
      placeholder: 'Wprowadź system prompt dla chatu...',
      contextLines: [
        'Ceny i zmiany wszystkich obserwowanych instrumentów',
        'Portfel użytkownika (zakupione + short)',
        'Ostatnia analiza AI (fragment do ~2500 znaków)',
        'Kalendarz ekonomiczny (7 dni, zdarzenia High i Medium)',
      ],
    },
    {
      key: 'instrument_profile_prompt',
      title: 'Profil instrumentu',
      desc: 'System prompt generujący opis instrumentu (Dashboard i Wykresy)',
      value: instrumentProfilePrompt, setValue: setInstrumentProfilePrompt, rows: 8,
      placeholder: 'np. Jesteś ekspertem finansowym. Opisz instrument zwięźle po polsku...',
      contextLines: [
        'Symbol i nazwa instrumentu',
        'Kategoria (Akcje, Krypto, Forex, Surowce, Inne)',
        'Aktualna cena i zmiana %',
        'Źródło danych (yfinance / coingecko / stooq)',
      ],
    },
    {
      key: 'charts_chat_prompt',
      title: 'Chat — Wykresy',
      desc: 'Bazowy system prompt dla chatu na stronie Wykresy',
      value: chartsChatPrompt, setValue: setChartsChatPrompt, rows: 8,
      placeholder: 'np. Jesteś ekspertem analizy technicznej i makroekonomicznej...',
      contextLines: [
        'Wybrany instrument: cena, zmiana %, symbol',
        'Dane z 5 interwałów: 5m / 15m / 1h / 24h / 72h (O/H/L/C, zmiana %)',
        'Ceny i zmiany wszystkich obserwowanych instrumentów',
        'Portfel użytkownika',
        'Ostatnia analiza AI (fragment)',
        'Kalendarz ekonomiczny (7 dni, zdarzenia High i Medium)',
      ],
    },
    {
      key: 'calendar_event_prompt',
      title: 'Analiza wydarzenia kalendarza',
      desc: 'System prompt przy analizie AI wydarzeń z kalendarza ekonomicznego',
      value: calendarEventPrompt, setValue: setCalendarEventPrompt, rows: 8,
      placeholder: 'np. Przeanalizuj to wydarzenie z kalendarza ekonomicznego...',
      contextLines: [
        'Nazwa wydarzenia i kraj (z flagą)',
        'Data i godzina publikacji',
        'Poziom wpływu (High / Medium)',
        'Prognoza (consensus rynkowy)',
        'Poprzedni odczyt',
      ],
    },
    {
      key: 'market_assessment_prompt',
      title: 'Ocena ryzyka i okazji — Dashboard',
      desc: 'Agent zwraca JSON: { risk, risk_reason, opportunity, opportunity_reason }',
      value: assessmentPrompt, setValue: setAssessmentPrompt, rows: 10,
      placeholder: '{"risk": <1-10>, "risk_reason": "...", "opportunity": <1-10>, "opportunity_reason": "..."}',
      contextLines: [
        'Ceny i zmiany wszystkich obserwowanych instrumentów',
        'Portfel użytkownika',
        'Ostatnia analiza AI (fragment)',
        'Agent MUSI zwrócić poprawny JSON — bez żadnych dodatkowych treści',
      ],
    },
  ];

  if (loading) return <div className="text-[var(--overlay)] text-center py-12">Ladowanie...</div>;

  return (
    <div className="max-w-5xl">
      <h1 className="text-2xl font-bold mb-6">Ustawienia</h1>

      {/* Tab bar */}
      <div className="flex border-b border-[var(--gray)] mb-6">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-6 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
              activeTab === t.key
                ? 'border-[var(--accent)] text-[var(--accent)]'
                : 'border-transparent text-[var(--overlay)] hover:text-[var(--fg)]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Ogolne ──────────────────────────────────────────── */}
      {activeTab === 'general' && (
        <div className="space-y-5">
          <section className="bg-[var(--bg2)] rounded-xl p-5 border border-[var(--gray)]">
            <h2 className="text-xs font-semibold text-[var(--overlay)] uppercase tracking-widest mb-4">Klucze API</h2>
            <div className="space-y-3">
              {(['anthropic', 'openai', 'openrouter', 'newsdata'] as const).map((k) => (
                <div key={k} className="flex items-center gap-3">
                  <label className="text-xs text-[var(--overlay)] w-24 flex-shrink-0 capitalize">{k}</label>
                  <input
                    type="password"
                    value={keys[k]}
                    onChange={(e) => setKeys({ ...keys, [k]: e.target.value })}
                    placeholder={`Klucz ${k}`}
                    className="flex-1 bg-[var(--bg)] border border-[var(--gray)] rounded-lg px-3 py-2 text-sm focus:border-[var(--accent)] outline-none transition-colors"
                  />
                </div>
              ))}
            </div>
          </section>

          <div className="grid grid-cols-2 gap-5">
            <section className="bg-[var(--bg2)] rounded-xl p-5 border border-[var(--gray)]">
              <h2 className="text-xs font-semibold text-[var(--overlay)] uppercase tracking-widest mb-4">Model — Analiza</h2>
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-[var(--overlay)] block mb-1">Dostawca</label>
                  <select value={provider} onChange={(e) => setProvider(e.target.value)}
                    className="w-full bg-[var(--bg)] border border-[var(--gray)] rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--accent)]">
                    {PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-[var(--overlay)] block mb-1">Model</label>
                  {MODEL_OPTIONS[provider] ? (
                    <select value={model} onChange={(e) => setModel(e.target.value)}
                      className="w-full bg-[var(--bg)] border border-[var(--gray)] rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--accent)]">
                      {MODEL_OPTIONS[provider].map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  ) : (
                    <input value={model} onChange={(e) => setModel(e.target.value)}
                      placeholder="np. openai/gpt-4o"
                      className="w-full bg-[var(--bg)] border border-[var(--gray)] rounded-lg px-3 py-2 text-sm focus:border-[var(--accent)] outline-none transition-colors" />
                  )}
                </div>
              </div>
            </section>

            <section className="bg-[var(--bg2)] rounded-xl p-5 border border-[var(--gray)]">
              <h2 className="text-xs font-semibold text-[var(--overlay)] uppercase tracking-widest mb-4">Model — Chat</h2>
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-[var(--overlay)] block mb-1">Dostawca</label>
                  <select value={chatProvider} onChange={(e) => setChatProvider(e.target.value)}
                    className="w-full bg-[var(--bg)] border border-[var(--gray)] rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--accent)]">
                    {PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs text-[var(--overlay)] block mb-1">Model</label>
                  {MODEL_OPTIONS[chatProvider] ? (
                    <select value={chatModel} onChange={(e) => setChatModel(e.target.value)}
                      className="w-full bg-[var(--bg)] border border-[var(--gray)] rounded-lg px-3 py-2 text-sm outline-none focus:border-[var(--accent)]">
                      {MODEL_OPTIONS[chatProvider].map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  ) : (
                    <input value={chatModel} onChange={(e) => setChatModel(e.target.value)}
                      placeholder="np. openai/gpt-4o"
                      className="w-full bg-[var(--bg)] border border-[var(--gray)] rounded-lg px-3 py-2 text-sm focus:border-[var(--accent)] outline-none transition-colors" />
                  )}
                </div>
              </div>
            </section>
          </div>

          <div className="flex items-center gap-3">
            <button onClick={saveGeneral}
              className="px-6 py-2 rounded-lg bg-[var(--accent)] text-[var(--bg)] font-semibold hover:opacity-90 transition-opacity">
              Zapisz
            </button>
            {saved && <span className="text-sm text-[var(--green)]">&#10003; Zapisano</span>}
          </div>
        </div>
      )}

      {/* ── Dostosuj ─────────────────────────────────────────── */}
      {activeTab === 'customize' && (() => {
        const hasChanges = JSON.stringify(instruments) !== savedInstrumentsRef.current
          || JSON.stringify(sources) !== savedSourcesRef.current;
        return (
        <div className="space-y-4">
          {hasChanges && (
            <div className="flex items-center gap-3 bg-[var(--accent)]/10 border border-[var(--accent)]/30 rounded-xl px-4 py-2.5">
              <span className="text-sm text-[var(--accent)] font-medium flex-1">Masz niezapisane zmiany</span>
              <button onClick={saveCustomize}
                className="px-5 py-1.5 rounded-lg bg-[var(--accent)] text-[var(--bg)] font-semibold text-sm hover:opacity-90 transition-opacity">
                Zapisz zmiany
              </button>
            </div>
          )}
          <div className="flex gap-6 items-start">

            {/* ── Lewa kolumna: instrumenty ─────────────────── */}
            <div className="flex-1 min-w-0 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm text-[var(--overlay)]">Obserwowane instrumenty ({instruments.length})</p>
                <button onClick={() => setShowAddForm(!showAddForm)}
                  className="px-4 py-1.5 rounded-lg bg-[var(--accent)] text-[var(--bg)] text-sm font-semibold hover:opacity-90 transition-opacity">
                  {showAddForm ? 'Anuluj' : '+ Dodaj instrument'}
                </button>
              </div>

              {showAddForm && (
                <div className="bg-[var(--bg2)] rounded-xl border border-[var(--accent)]/40 p-4 flex flex-wrap gap-3 items-end">
                  <InstrumentSearch
                    symbol={newInst.symbol}
                    name={newInst.name}
                    onSymbol={(v) => setNewInst((p) => ({ ...p, symbol: v.toUpperCase() }))}
                    onName={(v) => setNewInst((p) => ({ ...p, name: v }))}
                    onPick={(sym, nm, type) => {
                      const detected = detectCategoryAndSource(sym, type);
                      setNewInst((p) => ({ ...p, symbol: sym.toUpperCase(), name: nm, category: detected.category, source: detected.source }));
                    }}
                    symbolPlaceholder="np. AAPL"
                    namePlaceholder="np. Apple Inc."
                    symbolLabel="Symbol *"
                    nameLabel="Nazwa"
                    inputClassName="bg-[var(--bg)] border border-[var(--gray)] rounded-lg px-3 py-2 text-sm focus:border-[var(--accent)] outline-none"
                    symbolWrapClassName="w-28"
                    nameWrapClassName="w-44"
                  />
                  <div>
                    <label className="text-xs text-[var(--overlay)] block mb-1">Kategoria</label>
                    <select value={newInst.category} onChange={(e) => setNewInst({ ...newInst, category: e.target.value })}
                      className="bg-[var(--bg)] border border-[var(--gray)] rounded-lg px-3 py-2 text-sm outline-none">
                      {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-[var(--overlay)] block mb-1">Zrodlo</label>
                    <select value={newInst.source} onChange={(e) => setNewInst({ ...newInst, source: e.target.value })}
                      className="bg-[var(--bg)] border border-[var(--gray)] rounded-lg px-3 py-2 text-sm outline-none">
                      {SOURCES.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                  <button onClick={addInstrument}
                    className="px-4 py-2 rounded-lg bg-[var(--green)] text-[var(--bg)] font-semibold text-sm hover:opacity-90">
                    Dodaj
                  </button>
                </div>
              )}

              <div className="bg-[var(--bg2)] rounded-xl border border-[var(--gray)] overflow-hidden">
                {instruments.length === 0 ? (
                  <p className="text-sm text-[var(--overlay)] text-center py-8">Brak instrumentow. Dodaj pierwszy powyzej.</p>
                ) : (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-[var(--gray)] bg-[var(--bg)]">
                        <th className="text-left px-4 py-2.5 text-xs text-[var(--overlay)] uppercase tracking-wide font-semibold">Symbol</th>
                        <th className="text-left px-4 py-2.5 text-xs text-[var(--overlay)] uppercase tracking-wide font-semibold">Nazwa</th>
                        <th className="text-left px-4 py-2.5 text-xs text-[var(--overlay)] uppercase tracking-wide font-semibold">Kategoria</th>
                        <th className="text-left px-4 py-2.5 text-xs text-[var(--overlay)] uppercase tracking-wide font-semibold">Zrodlo</th>
                        <th className="px-4 py-2.5"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {instruments.map((inst, i) => (
                        <tr key={i} className="border-b border-[var(--gray)] last:border-0 hover:bg-[var(--gray)]/20 transition-colors">
                          <td className="px-4 py-3 font-mono font-semibold text-[var(--accent)]">{inst.symbol}</td>
                          <td className="px-4 py-3">{inst.name}</td>
                          <td className="px-4 py-3 text-xs text-[var(--overlay)]">{inst.category}</td>
                          <td className="px-4 py-3 text-xs text-[var(--overlay)]">{inst.source}</td>
                          <td className="px-4 py-3 text-right">
                            <button onClick={() => setInstruments(instruments.filter((_, j) => j !== i))}
                              className="text-xs text-[var(--red)] hover:underline">Usun</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            {/* ── Prawa kolumna: źródła ─────────────────────── */}
            <div className="w-64 flex-shrink-0 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm text-[var(--overlay)]">Źródła web ({sources.length})</p>
                <button onClick={() => setShowAddSource(!showAddSource)}
                  className="px-3 py-1.5 rounded-lg bg-[var(--accent)] text-[var(--bg)] text-sm font-semibold hover:opacity-90 transition-opacity">
                  {showAddSource ? 'Anuluj' : '+ Dodaj'}
                </button>
              </div>

              {showAddSource && (
                <div className="bg-[var(--bg2)] rounded-xl border border-[var(--accent)]/40 p-3 space-y-2">
                  <label className="text-xs text-[var(--overlay)] block">URL strony *</label>
                  <input
                    value={newSource}
                    onChange={(e) => setNewSource(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && addSource()}
                    placeholder="np. https://www.bloomberg.com"
                    className="w-full bg-[var(--bg)] border border-[var(--gray)] rounded-lg px-3 py-2 text-sm focus:border-[var(--accent)] outline-none"
                  />
                  <button onClick={addSource}
                    className="w-full px-4 py-2 rounded-lg bg-[var(--green)] text-[var(--bg)] font-semibold text-sm hover:opacity-90">
                    Dodaj
                  </button>
                </div>
              )}

              <div className="bg-[var(--bg2)] rounded-xl border border-[var(--gray)]">
                {sources.length === 0 ? (
                  <p className="text-sm text-[var(--overlay)] text-center py-8">Brak źródeł.</p>
                ) : (
                  <ul className="divide-y divide-[var(--gray)]">
                    {sources.map((url, i) => (
                      <li key={i} className="flex items-center gap-2 px-3 py-2.5 hover:bg-[var(--gray)]/20 transition-colors">
                        <span
                          className="flex-1 font-mono text-xs text-[var(--fg)] truncate"
                          title={url}
                        >{url}</span>
                        <button onClick={() => setSources(sources.filter((_, j) => j !== i))}
                          className="flex-shrink-0 text-xs text-[var(--red)] hover:underline">Usuń</button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button onClick={saveCustomize}
              className="px-6 py-2 rounded-lg bg-[var(--accent)] text-[var(--bg)] font-semibold hover:opacity-90 transition-opacity">
              Zapisz
            </button>
            {saved && <span className="text-sm text-[var(--green)]">&#10003; Zapisano</span>}
          </div>
        </div>
        );
      })()}

      {/* ── Statystyki ───────────────────────────────────────── */}
      {activeTab === 'stats' && (
        <div className="space-y-5">
          {statsLoading && (
            <p className="text-sm text-[var(--overlay)] text-center py-8 animate-pulse">Ladowanie statystyk...</p>
          )}
          {!statsLoading && !stats && (
            <p className="text-sm text-[var(--overlay)] text-center py-8">Brak danych. Uruchom analizę lub czat aby zobaczyć statystyki.</p>
          )}
          {!statsLoading && stats && (
            <>
              {/* Session block */}
              {stats.session && (
                <section className="bg-[var(--bg2)] rounded-xl border border-[var(--gray)] overflow-hidden">
                  <div className="px-5 py-3 border-b border-[var(--gray)]">
                    <h2 className="text-sm font-semibold">Bieżąca sesja</h2>
                    <p className="text-xs text-[var(--overlay)] mt-0.5">
                      Od zalogowania: {loginTime ? new Date(loginTime).toLocaleString('pl-PL', { timeZone: APP_TIMEZONE }) : '—'}
                    </p>
                  </div>
                  <div className="p-5">
                    <StatsGrid agg={stats.session} />
                  </div>
                </section>
              )}

              {/* Historical block */}
              <section className="bg-[var(--bg2)] rounded-xl border border-[var(--gray)] overflow-hidden">
                <div className="px-5 py-3 border-b border-[var(--gray)]">
                  <h2 className="text-sm font-semibold">Łącznie (historycznie)</h2>
                  <p className="text-xs text-[var(--overlay)] mt-0.5">Wszystkie żądania od początku konta</p>
                </div>
                <div className="p-5">
                  <StatsGrid agg={stats.historical} />
                </div>
              </section>

              <p className="text-xs text-[var(--overlay)] text-right">
                Ceny: Anthropic (claude.com/pricing) i OpenAI (openai.com/api/pricing). Odśwież stronę aby zaktualizować.
              </p>
            </>
          )}
        </div>
      )}

      {/* ── Prompty ──────────────────────────────────────────── */}
      {activeTab === 'prompts' && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-5">
            {promptDefs.map((def) => (
              <PromptCard
                key={def.key}
                def={def}
                defaultValue={defaults[def.key] ?? ''}
                ctxOpen={ctxOpen[def.key] ?? false}
                onToggleCtx={() => setCtxOpen((prev) => ({ ...prev, [def.key]: !prev[def.key] }))}
                onExpand={() => setExpandedKey(def.key)}
              />
            ))}
          </div>
          <div className="flex items-center gap-3">
            <button onClick={savePrompts}
              className="px-6 py-2 rounded-lg bg-[var(--accent)] text-[var(--bg)] font-semibold hover:opacity-90 transition-opacity">
              Zapisz prompty
            </button>
            {saved && <span className="text-sm text-[var(--green)]">&#10003; Zapisano</span>}
          </div>
        </div>
      )}

      {/* ── Modal powiększenia promptu ────────────────────────── */}
      {expandedKey && (() => {
        const def = promptDefs.find((d) => d.key === expandedKey);
        if (!def) return null;
        return (
          <div
            className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-6"
            onClick={() => setExpandedKey(null)}
          >
            <div
              className="bg-[var(--bg2)] rounded-2xl border border-[var(--gray)] w-full max-w-5xl flex flex-col shadow-2xl"
              style={{ height: '88vh' }}
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between px-5 py-3 border-b border-[var(--gray)] flex-shrink-0">
                <div>
                  <h3 className="font-semibold">{def.title}</h3>
                  <p className="text-xs text-[var(--overlay)] mt-0.5">{def.desc}</p>
                </div>
                <button
                  onClick={() => setExpandedKey(null)}
                  className="p-1.5 rounded-lg text-[var(--overlay)] hover:text-[var(--fg)] hover:bg-[var(--gray)]/60 transition-colors text-lg leading-none"
                >
                  ✕
                </button>
              </div>
              <div className="flex-1 p-4 min-h-0">
                <textarea
                  value={def.value}
                  onChange={(e) => def.setValue(e.target.value)}
                  className="w-full h-full bg-[var(--bg)] border border-[var(--gray)] rounded-lg px-3 py-2 text-sm font-mono text-[var(--fg)] focus:border-[var(--accent)] outline-none resize-none transition-colors"
                />
              </div>
              <div className="px-5 py-3 border-t border-[var(--gray)] flex-shrink-0 flex items-center justify-between">
                <span className="text-xs text-[var(--overlay)]">{def.value.length} znaków</span>
                <button
                  onClick={() => setExpandedKey(null)}
                  className="px-4 py-1.5 rounded-lg bg-[var(--accent)] text-[var(--bg)] text-sm font-semibold hover:opacity-90 transition-opacity"
                >
                  Zamknij
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
}

// ── StatsGrid helper ────────────────────────────────────────────────
import type { UsageAggregate } from '../api/stats';

const TYPE_LABELS: Record<string, string> = {
  analysis: 'Analiza raportu',
  profile: 'Analiza instrumentu',
  charts_chat: 'Chat — Wykresy',
  dashboard_chat: 'Chat — Dashboard',
  chat: 'Chat — zakładka Chat',
  calendar_event: 'Analiza kalendarza',
};

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-[var(--bg)] rounded-lg px-4 py-3 border border-[var(--gray)]">
      <p className="text-xs text-[var(--overlay)] mb-1">{label}</p>
      <p className="text-lg font-bold text-[var(--fg)] font-mono">{value}</p>
    </div>
  );
}

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + ' M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + ' k';
  return String(n);
}

function fmtCost(usd: number): string {
  if (usd < 0.001) return '< $0.001';
  return '$' + usd.toFixed(4);
}

function StatsGrid({ agg }: { agg: UsageAggregate }) {
  const types = Object.keys(agg.by_type ?? {});
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatBox label="Tokeny wejście" value={fmtTokens(agg.input_tokens)} />
        <StatBox label="Tokeny wyjście" value={fmtTokens(agg.output_tokens)} />
        <StatBox label="Łączny koszt" value={fmtCost(agg.cost_usd)} />
        <StatBox label="Żądania" value={String(agg.requests)} />
      </div>
      {types.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-[var(--gray)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--gray)] bg-[var(--bg)]">
                <th className="text-left px-4 py-2 text-xs text-[var(--overlay)] uppercase tracking-wide font-semibold">Typ</th>
                <th className="text-right px-4 py-2 text-xs text-[var(--overlay)] uppercase tracking-wide font-semibold">Wejście</th>
                <th className="text-right px-4 py-2 text-xs text-[var(--overlay)] uppercase tracking-wide font-semibold">Wyjście</th>
                <th className="text-right px-4 py-2 text-xs text-[var(--overlay)] uppercase tracking-wide font-semibold">Koszt</th>
                <th className="text-right px-4 py-2 text-xs text-[var(--overlay)] uppercase tracking-wide font-semibold">Żąd.</th>
              </tr>
            </thead>
            <tbody>
              {types.map((t) => {
                const row = agg.by_type[t];
                return (
                  <tr key={t} className="border-b border-[var(--gray)] last:border-0">
                    <td className="px-4 py-2.5 font-medium">{TYPE_LABELS[t] ?? t}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-xs">{fmtTokens(row.input_tokens)}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-xs">{fmtTokens(row.output_tokens)}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-xs text-[var(--yellow)]">{fmtCost(row.cost_usd)}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-xs text-[var(--overlay)]">{row.requests}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
