import { useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { getCachedInstruments, getInstruments, getSparkline, getInstrumentUnit, type InstrumentData, assessMarket, type MarketAssessment } from '../api/market';
import { getReports, getReport, runAnalysis, type ReportDetail } from '../api/reports';
import { sendMessage } from '../api/chat';
import { APP_TIMEZONE } from '../config';
import { getCalendar, type CalendarEvent } from '../api/calendar';
import { addPosition } from '../api/portfolio';
import PriceChart from '../components/PriceChart';
import { useAppStore } from '../stores/appStore';
import InstrumentProfilePanel from '../components/InstrumentProfilePanel';
import api from '../api/client';
import { useChatStorage } from '../hooks/useChatStorage';
import { useAuthStore } from '../stores/authStore';

// ─── Cennik LLM (USD / 1M tokenów) ───────────────────────────
const _PRICING: Record<string, Record<string, [number, number]>> = {
  anthropic: {
    'claude-opus-4-6':           [15.00, 75.00],
    'claude-sonnet-4-6':         [ 3.00, 15.00],
    'claude-haiku-4-5-20251001': [ 0.80,  4.00],
  },
  openai: {
    'gpt-4.1':      [2.00,  8.00],
    'gpt-4.1-mini': [0.40,  1.60],
    'gpt-4.1-nano': [0.10,  0.40],
    'gpt-4o':       [2.50, 10.00],
    'gpt-4o-mini':  [0.15,  0.60],
    'gpt-4-turbo':  [10.00, 30.00],
    'o1':           [15.00, 60.00],
    'o1-preview':   [15.00, 60.00],
    'o1-mini':      [ 3.00, 12.00],
    'o3':           [10.00, 40.00],
    'o3-mini':      [ 1.10,  4.40],
    'o4-mini':      [ 1.10,  4.40],
  },
};

function calcCost(provider: string | null, model: string | null, inp: number, out: number): number | null {
  const p = (provider ?? '').toLowerCase();
  const m = (model ?? '').toLowerCase();
  let rates = _PRICING[p]?.[m];
  if (!rates && p === 'openrouter' && m.includes('/')) {
    const slug = m.split('/', 2)[1];
    for (const sub of ['openai', 'anthropic']) {
      if (_PRICING[sub]?.[slug]) { rates = _PRICING[sub][slug]; break; }
    }
  }
  if (!rates) return null;
  return (inp * rates[0] + out * rates[1]) / 1_000_000;
}

function fmtUsd(v: number): string {
  if (v < 0.0001) return '<$0.0001';
  if (v < 0.01) return `$${v.toFixed(4)}`;
  return `$${v.toFixed(3)}`;
}

// ─── Dostępne modele per dostawca ─────────────────────────────
const PROVIDER_MODELS: Record<string, { value: string; label: string }[]> = {
  anthropic: [
    { value: 'claude-haiku-4-5-20251001', label: 'Claude Haiku' },
    { value: 'claude-sonnet-4-6',         label: 'Claude Sonnet' },
    { value: 'claude-opus-4-6',           label: 'Claude Opus' },
  ],
  openai: [
    { value: 'gpt-4.1-mini', label: 'GPT-4.1 Mini' },
    { value: 'gpt-4.1',      label: 'GPT-4.1' },
    { value: 'gpt-4o',       label: 'GPT-4o' },
    { value: 'o3-mini',      label: 'o3 Mini' },
  ],
  openrouter: [
    { value: 'openai/gpt-4o',              label: 'GPT-4o' },
    { value: 'anthropic/claude-sonnet-4-5', label: 'Claude Sonnet' },
    { value: 'meta-llama/llama-4-maverick', label: 'Llama 4 Maverick' },
    { value: 'google/gemini-2.0-flash-001', label: 'Gemini 2.0 Flash' },
  ],
};

// ─── Kroki wyświetlane podczas generowania analizy ────────────
const ANALYSIS_STEPS = [
  'Pobieranie danych rynkowych...',
  'Analizowanie instrumentów finansowych...',
  'Pobieranie najnowszych wiadomości...',
  'Klasyfikowanie trendów makroekonomicznych...',
  'Przygotowywanie kontekstu dla modelu AI...',
  'Generowanie analizy przez AI...',
  'Oczekiwanie na odpowiedź modelu...',
  'Przetwarzanie i formatowanie raportu...',
  'Zapisywanie analizy...',
];

// ─── Assessment Gauge (półokrągły wskaźnik) ───────────────────
function GaugeChart({
  value, label, loading, invertNeedle, onClick,
}: {
  value: number; label: string; loading?: boolean; invertNeedle?: boolean; onClick?: () => void;
}) {
  const cx = 90, cy = 84, R = 65, Rin = 44;

  const pt = (deg: number, r: number) => ({
    x: cx + r * Math.cos((deg * Math.PI) / 180),
    y: cy - r * Math.sin((deg * Math.PI) / 180),
  });

  const arcSeg = (a1: number, a2: number, fill: string) => {
    const os = pt(a1, R), oe = pt(a2, R);
    const is = pt(a2, Rin), ie = pt(a1, Rin);
    const la = a2 - a1 > 180 ? 1 : 0;
    return (
      <path fill={fill} opacity={0.72}
        d={`M${os.x.toFixed(1)},${os.y.toFixed(1)} A${R},${R},0,${la},0,${oe.x.toFixed(1)},${oe.y.toFixed(1)} L${is.x.toFixed(1)},${is.y.toFixed(1)} A${Rin},${Rin},0,${la},1,${ie.x.toFixed(1)},${ie.y.toFixed(1)}Z`}
      />
    );
  };

  const v = Math.max(1, Math.min(10, value || 5));
  const frac = (v - 1) / 9;
  // Wysoka wartość → igła w prawo (dla ryzyka: prawo=czerwone, dla okazji: prawo=zielone)
  const ndeg = (1 - frac) * 180;
  const tip = pt(ndeg, R - 10);
  const unknown = !value;

  const RISK_LABELS  = ['MIN','NISKIE','NISKIE','ŚREDNIE','ŚREDNIE','ŚREDNIE','WYSOKIE','WYSOKIE','B.WYS.','EKSTR.'];
  const OPP_LABELS   = ['BRAK','NISKA','NISKA','NISKA','ŚREDNIA','ŚREDNIA','WYSOKA','WYSOKA','B.WYS.','WYJĄTK.'];
  const levelText = (invertNeedle ? RISK_LABELS : OPP_LABELS)[v - 1];

  const valColor = loading || unknown ? '#6c7086'
    : invertNeedle
      ? (v <= 3 ? '#a6e3a1' : v <= 6 ? '#f9e2af' : v <= 8 ? '#fab387' : '#f38ba8')
      : (v >= 7 ? '#a6e3a1' : v >= 4 ? '#f9e2af' : '#f38ba8');

  // Ryzyko: zielony(lewo) → żółty → czerwony(prawo)
  // Okazja: czerwony(lewo) → żółty → zielony(prawo)
  const leftColor  = invertNeedle ? '#a6e3a1' : '#f38ba8';
  const rightColor = invertNeedle ? '#f38ba8' : '#a6e3a1';

  return (
    <svg viewBox="0 0 180 114" className="w-full cursor-pointer" onClick={onClick}>
      <title>Kliknij aby zobaczyć uzasadnienie AI</title>
      {arcSeg(0, 60, rightColor)}
      {arcSeg(60, 120, '#f9e2af')}
      {arcSeg(120, 180, leftColor)}
      <circle cx={cx} cy={cy} r={Rin - 1} fill="var(--bg)" />
      <line x1={cx} y1={cy} x2={tip.x} y2={tip.y} stroke="white" strokeWidth="2.5" strokeLinecap="round" />
      <circle cx={cx} cy={cy} r={5} fill="white" />
      <circle cx={cx} cy={cy} r={2} fill="var(--bg)" />
      <text x={cx} y={99} textAnchor="middle" fill={valColor} fontSize="13" fontWeight="bold" fontFamily="ui-monospace,monospace">
        {loading ? '…/10' : unknown ? '?/10' : `${v}/10`}
      </text>
      <text x={cx} y={111} textAnchor="middle" fill={valColor} fontSize="8" fontWeight="bold" letterSpacing="1">
        {!loading && !unknown ? levelText : ''}
      </text>
      <text x={cx} y={12} textAnchor="middle" fill={invertNeedle ? '#f38ba8' : '#a6e3a1'} fontSize="11" fontWeight="bold" letterSpacing="0.8">
        {label}
      </text>
    </svg>
  );
}

// ─── Sparkline  ────────────────────────────────────────────────
function Sparkline({ data, changePct }: { data: number[]; changePct: number | null }) {
  if (data.length < 2) return <div style={{ height: 28 }} />;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const W = 100, H = 28;
  const pts = data.map((v, i) => ({
    x: (i / (data.length - 1)) * W,
    y: H - ((v - min) / range) * (H - 4) - 2,
  }));
  // Wygładzona krzywa bezier przez punkty środkowe
  const d = pts.reduce((acc, pt, i) => {
    if (i === 0) return `M ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`;
    const prev = pts[i - 1];
    const mx = ((prev.x + pt.x) / 2).toFixed(1);
    const my = ((prev.y + pt.y) / 2).toFixed(1);
    return `${acc} Q ${prev.x.toFixed(1)} ${prev.y.toFixed(1)} ${mx} ${my}`;
  }, '') + ` T ${pts[pts.length - 1].x.toFixed(1)} ${pts[pts.length - 1].y.toFixed(1)}`;
  const isUp = (changePct ?? 0) >= 0;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="w-full mt-1" height={28}>
      <path d={d} fill="none" stroke={isUp ? '#a6e3a1' : '#f38ba8'} strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

// ─── Instrument Card ──────────────────────────────────────────
function InstCard({
  data,
  selected,
  onClick,
  flash,
}: {
  data: InstrumentData;
  selected: boolean;
  onClick: () => void;
  flash?: 'up' | 'down';
}) {
  const isUp = (data.change_pct ?? 0) >= 0;
  const pct = data.change_pct;
  const color = isUp ? 'text-[#a6e3a1]' : 'text-[#f38ba8]';
  const unit = getInstrumentUnit(data.symbol, data.source);
  return (
    <div
      onClick={onClick}
      className={`rounded-xl p-3 border cursor-pointer transition-all select-none ${
        selected
          ? 'border-[var(--accent)] bg-[var(--accent)]/10 shadow-[0_0_0_1px_var(--accent)]'
          : 'border-[var(--gray)] bg-[var(--bg2)] hover:border-[var(--accent)]/50 hover:bg-[var(--bg2)]'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="text-[10px] text-[var(--overlay)] font-mono truncate leading-none mb-0.5">
            {data.symbol}
          </div>
          <div className="text-sm font-semibold leading-tight flex items-baseline gap-1 min-w-0">
            <span className="truncate">{data.name}</span>
            {unit && <span className="text-[11px] font-mono text-[var(--overlay)] flex-shrink-0 opacity-80">{unit}</span>}
          </div>
        </div>
        {pct != null && (
          <div className={`text-xs font-bold flex-shrink-0 ${color}`}>
            {isUp ? '+' : ''}{pct.toFixed(2)}%
          </div>
        )}
      </div>
      <div
        key={flash}
        className={`text-lg sm:text-xl font-bold font-mono mt-1.5 tabular-nums ${
          flash === 'up' ? 'flash-up' : flash === 'down' ? 'flash-down' : ''
        }`}
      >
        {data.price != null
          ? data.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 })
          : data.error ? (
            <span className="text-sm font-normal text-[var(--red)]">Blad danych</span>
          ) : '—'}
      </div>
      <Sparkline data={data.sparkline} changePct={data.change_pct} />
    </div>
  );
}

// ─── Dashboard ────────────────────────────────────────────────
export default function Dashboard() {
  const [instruments, setInstruments] = useState<InstrumentData[]>(() => getCachedInstruments());
  const [loadingInst, setLoadingInst] = useState(() => getCachedInstruments().length === 0);
  const [flashMap, setFlashMap] = useState<Record<string, 'up' | 'down'>>({});
  const prevPricesRef = useRef<Record<string, number | null>>({});
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [assessment, setAssessment] = useState<MarketAssessment | null>(null);
  const [assessmentLoading, setAssessmentLoading] = useState(false);
  const [assessmentModal, setAssessmentModal] = useState<'risk' | 'opportunity' | null>(null);
  const reportIdRef = useRef<number | null>(null);
  const [analysisRunning, setAnalysisRunning] = useState(false);
  const [analysisStep, setAnalysisStep] = useState(0);
  const { setStatusMsg } = useAppStore();

  // Model picker
  const [showModelPicker, setShowModelPicker] = useState(false);
  const [pickerProvider, setPickerProvider] = useState('');
  const [pickerModel, setPickerModel] = useState('');
  const [availableProviders, setAvailableProviders] = useState<string[]>([]);

  const { loginTime } = useAuthStore();
  const [sessionCost, setSessionCost] = useState<number | null>(null);

  // Instrument panel
  const [selectedInstrument, setSelectedInstrument] = useState<InstrumentData | null>(null);
  const [instrumentProfilePrompt, setInstrumentProfilePrompt] = useState('');
  const [marketExpanded, setMarketExpanded] = useState(false);
  const [analysisExpanded, setAnalysisExpanded] = useState(false);

  // Drag & drop kolejność instrumentów (persist w localStorage)
  const [instrumentOrder, setInstrumentOrder] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem('dash_instrument_order_v1') || '[]'); } catch { return []; }
  });
  const dragIdxRef = useRef<number | null>(null);
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);

  // Dodaj do portfela — context menu (prawy przycisk myszy)
  const [portCtx, setPortCtx] = useState<{ x: number; y: number; inst: InstrumentData } | null>(null);
  const [portModal, setPortModal] = useState<{ inst: InstrumentData; tabType: string; basePriceUSD: number } | null>(null);
  const [portForm, setPortForm] = useState({ quantity: '', price: '', currency: 'USD' });
  const [portAdding, setPortAdding] = useState(false);

  // Chat z persistencją 72h
  const { messages: chatMessages, setMessages: setChatMessages } = useChatStorage('chat:dashboard');
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const [chatCtxOpen, setChatCtxOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatPrompt, setChatPrompt] = useState('');
  const [sources, setSources] = useState<string[]>([]);
  const [calendarEvents, setCalendarEvents] = useState<CalendarEvent[]>([]);

  // Ref do eksportu analizy
  const analysisRef = useRef<HTMLDivElement>(null);

  // Resizable chat panel
  const [chatHeight, setChatHeight] = useState(320);
  const startResize = (e: React.MouseEvent) => {
    e.preventDefault();
    const startY = e.clientY;
    const startH = chatHeight;
    const onMove = (ev: MouseEvent) => {
      const delta = startY - ev.clientY;
      setChatHeight(Math.max(140, Math.min(600, startH + delta)));
    };
    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  };

  // Pobiera bogatsze sparkline (1h, ~40 świec) i aktualizuje karty w tle
  const fetchSparklines = (insts: InstrumentData[]) => {
    Promise.allSettled(
      insts.map((inst) =>
        getSparkline(inst.symbol, '1h', inst.source || 'yfinance')
          .then((data) => data.length >= 4 ? { symbol: inst.symbol, sparkline: data.slice(-24) } : null)
          .catch(() => null)
      )
    ).then((results) => {
      const map: Record<string, number[]> = {};
      for (const r of results) {
        if (r.status === 'fulfilled' && r.value) map[r.value.symbol] = r.value.sparkline;
      }
      if (Object.keys(map).length > 0) {
        setInstruments((prev) =>
          prev.map((inst) => map[inst.symbol] ? { ...inst, sparkline: map[inst.symbol] } : inst)
        );
      }
    });
  };

  const fetchInstruments = () => {
    getInstruments()
      .then((newInsts: InstrumentData[]) => {
        // Wykryj zmiany cen i ustaw flash
        const flash: Record<string, 'up' | 'down'> = {};
        for (const inst of newInsts) {
          const prev = prevPricesRef.current[inst.symbol];
          if (prev != null && inst.price != null && inst.price !== prev) {
            flash[inst.symbol] = inst.price > prev ? 'up' : 'down';
          }
          prevPricesRef.current[inst.symbol] = inst.price ?? null;
        }
        setInstruments(newInsts);
        if (Object.keys(flash).length > 0) {
          setFlashMap(flash);
          setTimeout(() => setFlashMap({}), 1600);
        }
        // Pobierz płynne sparkline w tle (cache 2 min)
        fetchSparklines(newInsts);
      })
      .catch(() => {})
      .finally(() => setLoadingInst(false));
  };

  // ── Assessment cache (localStorage, keyed by report ID) ───────
  const _loadAssessmentCache = (reportId: number): MarketAssessment | null => {
    try {
      const raw = localStorage.getItem('assessment_cache_v1');
      if (!raw) return null;
      const { id, data } = JSON.parse(raw);
      return id === reportId ? data : null;
    } catch { return null; }
  };

  const _saveAssessmentCache = (reportId: number, data: MarketAssessment) => {
    try { localStorage.setItem('assessment_cache_v1', JSON.stringify({ id: reportId, data })); } catch { /* quota */ }
  };

  const fetchAssessment = async (ctx?: string) => {
    setAssessmentLoading(true);
    try {
      const context = ctx ?? buildChatContext();
      const result = await assessMarket(context);
      setAssessment(result);
      if (reportIdRef.current != null) _saveAssessmentCache(reportIdRef.current, result);
    } catch { /* ignore - AI might not be configured */ }
    finally { setAssessmentLoading(false); }
  };

  const loadLatestReport = async () => {
    try {
      const list = await getReports(1);
      if (list.length > 0) {
        const rep = await getReport(list[0].id);
        setReport(rep);
        reportIdRef.current = rep.id;
        const cached = _loadAssessmentCache(rep.id);
        if (cached) {
          setAssessment(cached);
        } else {
          setTimeout(() => fetchAssessment(), 1000);
        }
      }
    } catch { /* no reports yet */ }
  };

  useEffect(() => {
    setStatusMsg('Gotowy');
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchInstruments();
    loadLatestReport();
    fetchSessionCost();
    getCalendar().then((r) => setCalendarEvents(r.events)).catch(() => {});
    api.get('/settings').then((r) => {
      setInstrumentProfilePrompt(r.data.instrument_profile_prompt || '');
      setChatPrompt(r.data.chat_prompt || '');
      setSources(r.data.sources || []);
      // Wykryj dostępnych providerów (klucz ustawiony = non-empty)
      const keys = r.data.api_keys || {};
      const providers = ['anthropic', 'openai', 'openrouter'].filter((p) => !!keys[p]);
      setAvailableProviders(providers);
      // Ustaw domyślny provider/model z config
      const defaultProvider = r.data.ai_provider || (providers[0] ?? 'openai');
      const defaultModel = r.data.ai_model || PROVIDER_MODELS[defaultProvider]?.[0]?.value || '';
      setPickerProvider(defaultProvider);
      setPickerModel(defaultModel);
    }).catch(() => {});
    const iv = setInterval(() => { if (!document.hidden) fetchInstruments(); }, 30_000);
    const reportIv = setInterval(loadLatestReport, 120_000);
    // Natychmiastowy refresh po zmianie listy instrumentów w Ustawieniach
    window.addEventListener('instruments-changed', fetchInstruments);
    return () => {
      clearInterval(iv);
      clearInterval(reportIv);
      window.removeEventListener('instruments-changed', fetchInstruments);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Cykliczne kroki statusu podczas generowania
  useEffect(() => {
    if (!analysisRunning) { setAnalysisStep(0); return; }
    const iv = setInterval(() => setAnalysisStep((p) => (p + 1) % ANALYSIS_STEPS.length), 3200);
    return () => clearInterval(iv);
  }, [analysisRunning]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  useEffect(() => {
    fetchSessionCost();
  }, [loginTime]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!analysisExpanded) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setAnalysisExpanded(false); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [analysisExpanded]);

  // Zamknij context menu po kliknięciu poza nim
  useEffect(() => {
    if (!portCtx) return;
    const close = () => setPortCtx(null);
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, [portCtx]);

  // Synchronizuj kolejność z nowo pobranymi instrumentami
  useEffect(() => {
    if (instruments.length === 0) return;
    const syms = instruments.map((i) => i.symbol);
    setInstrumentOrder((prev) => {
      const existing = prev.filter((s) => syms.includes(s));
      const newOnes = syms.filter((s) => !prev.includes(s));
      if (existing.length === prev.length && newOnes.length === 0) return prev;
      const next = [...existing, ...newOnes];
      try { localStorage.setItem('dash_instrument_order_v1', JSON.stringify(next)); } catch { /* quota */ }
      return next;
    });
  }, [instruments]);

  const orderedInstruments =
    instrumentOrder.length > 0
      ? (instrumentOrder
          .map((sym) => instruments.find((i) => i.symbol === sym))
          .filter(Boolean) as InstrumentData[])
      : instruments;

  const handleDragStart = (idx: number) => {
    dragIdxRef.current = idx;
  };

  const handleDragOver = (e: React.DragEvent, idx: number) => {
    e.preventDefault();
    setDragOverIdx(idx);
  };

  const handleDrop = (toIdx: number) => {
    const fromIdx = dragIdxRef.current;
    if (fromIdx === null || fromIdx === toIdx) { setDragOverIdx(null); return; }
    const newOrder = [...instrumentOrder];
    const [moved] = newOrder.splice(fromIdx, 1);
    newOrder.splice(toIdx, 0, moved);
    setInstrumentOrder(newOrder);
    try { localStorage.setItem('dash_instrument_order_v1', JSON.stringify(newOrder)); } catch { /* quota */ }
    dragIdxRef.current = null;
    setDragOverIdx(null);
  };

  const fetchSessionCost = () => {
    if (!loginTime) return;
    api.get(`/stats?session_since=${encodeURIComponent(loginTime)}`)
      .then((r) => { if (r.data.session?.cost_usd != null) setSessionCost(r.data.session.cost_usd); })
      .catch(() => {});
  };

  const handleCardClick = (inst: InstrumentData) => {
    setSelectedInstrument((prev) => prev?.symbol === inst.symbol ? null : inst);
  };

  const handleOpenPicker = () => {
    if (analysisRunning) return;
    setShowModelPicker(true);
  };

  const handleRunAnalysis = async (provider: string, model: string) => {
    setShowModelPicker(false);
    setAnalysisRunning(true);
    setStatusMsg('Analizuje...');
    try {
      // Backend zwraca 202 natychmiast i uruchamia analizę w tle.
      // Zapisujemy ID aktualnego raportu, żeby wykryć nowy.
      const prevId = report?.id ?? null;
      await runAnalysis(provider, model);

      // Pollujemy co 4s aż pojawi się nowy raport (max 6 minut)
      const deadline = Date.now() + 6 * 60_000;
      while (Date.now() < deadline) {
        await new Promise<void>((r) => setTimeout(r, 4000));
        const list = await getReports(1);
        if (list.length > 0 && list[0].id !== prevId) {
          const newRep = await getReport(list[0].id);
          setReport(newRep);
          reportIdRef.current = newRep.id;
          break;
        }
      }
      setStatusMsg('Gotowy');
      fetchSessionCost();
      fetchAssessment();
    } catch {
      setStatusMsg('Blad analizy');
    } finally {
      setAnalysisRunning(false);
    }
  };

  const exportPDF = () => {
    if (!report || !analysisRef.current) return;
    const content = analysisRef.current.innerHTML;
    const win = window.open('', '_blank');
    if (!win) return;
    const date = new Date().toLocaleString('pl-PL', { timeZone: APP_TIMEZONE });
    win.document.write(`<!DOCTYPE html><html><head>
      <meta charset="utf-8">
      <title>Analiza rynkowa – ${date}</title>
      <style>
        body { font-family: Georgia, serif; max-width: 820px; margin: 40px auto; padding: 20px; color: #1a1a1a; line-height: 1.65; }
        .meta { color: #666; font-size: 0.85rem; margin-bottom: 1.5rem; padding-bottom: 0.75rem; border-bottom: 1px solid #ddd; }
        h1 { font-size: 1.45rem; font-weight: 700; margin: 1.5rem 0 0.6rem; border-bottom: 2px solid #333; padding-bottom: 0.3rem; }
        h2 { font-size: 1.2rem; font-weight: 700; margin: 1.25rem 0 0.5rem; color: #333; }
        h3 { font-size: 1.05rem; font-weight: 600; margin: 1rem 0 0.4rem; color: #444; }
        p { margin: 0.5rem 0; }
        ul { list-style-type: disc; margin: 0.5rem 0 0.5rem 1.5rem; }
        ol { list-style-type: decimal; margin: 0.5rem 0 0.5rem 1.5rem; }
        li { margin: 0.2rem 0; }
        strong { font-weight: 700; }
        em { font-style: italic; color: #444; }
        code { background: #f0f0f0; padding: 0.1rem 0.3rem; border-radius: 3px; font-family: monospace; font-size: 0.9em; }
        pre { background: #f5f5f5; padding: 0.75rem 1rem; border-radius: 6px; overflow-x: auto; margin: 0.75rem 0; }
        pre code { background: none; padding: 0; }
        blockquote { border-left: 3px solid #aaa; padding-left: 1rem; margin: 0.75rem 0; color: #555; }
        hr { border: none; border-top: 1px solid #ccc; margin: 1rem 0; }
        table { width: 100%; border-collapse: collapse; margin: 0.75rem 0; }
        th { background: #f0f0f0; padding: 0.4rem 0.75rem; text-align: left; font-weight: 600; border: 1px solid #ccc; }
        td { padding: 0.35rem 0.75rem; border: 1px solid #ccc; }
        tr:nth-child(even) { background: #fafafa; }
        @media print { body { margin: 0; } }
      </style>
    </head><body>
      <div class="meta">Analiza rynkowa &bull; ${report.provider}/${report.model} &bull; ${date}</div>
      ${content}
    </body></html>`);
    win.document.close();
    win.focus();
    setTimeout(() => win.print(), 400);
  };

  // Mapuje znane serwisy na ich URL wyszukiwarki
  const _SOURCE_SEARCH: Record<string, string> = {
    reuters:    'https://www.reuters.com/site-search/?query=',
    bloomberg:  'https://www.bloomberg.com/search?query=',
    cnbc:       'https://www.cnbc.com/search/?query=',
    wsj:        'https://www.wsj.com/search?query=',
    ft:         'https://www.ft.com/search?q=',
    'financial times': 'https://www.ft.com/search?q=',
    bbc:        'https://www.bbc.co.uk/search?q=',
    marketwatch:'https://www.marketwatch.com/search?q=',
    investing:  'https://www.investing.com/search/?q=',
    'investing.com': 'https://www.investing.com/search/?q=',
    seekingalpha: 'https://seekingalpha.com/search?q=',
    yahoo:      'https://finance.yahoo.com/search/?p=',
    'yahoo finance': 'https://finance.yahoo.com/search/?p=',
    forexfactory: 'https://www.forexfactory.com/search?q=',
    forexlive:  'https://www.forexlive.com/search/',
    tradingeconomics: 'https://tradingeconomics.com/search?q=',
    pap:        'https://www.pap.pl/wyszukiwarka?phrase=',
    'bankier.pl': 'https://www.bankier.pl/wiadomosci/szukaj?q=',
    bankier:    'https://www.bankier.pl/wiadomosci/szukaj?q=',
    'money.pl': 'https://www.money.pl/szukaj/',
    pb:         'https://www.pb.pl/szukaj?q=',
  };

  const _buildLink = (rawLine: string, title: string): string => {
    // 1. Spróbuj wyciągnąć URL wprost z linii
    const urlMatch = rawLine.match(/https?:\/\/[^\s\)\]"']+/);
    if (urlMatch) return urlMatch[0];
    // 2. Sprawdź czy nazwa źródła (część po " – ") pasuje do znanych serwisów
    const parts = rawLine.split(/\s[–—-]\s/);
    const sourceRaw = (parts[1] ?? '').replace(/\*+/g, '').trim().toLowerCase();
    for (const [key, url] of Object.entries(_SOURCE_SEARCH)) {
      if (sourceRaw.includes(key)) return url + encodeURIComponent(title);
    }
    // 3. Fallback — Google
    return 'https://www.google.com/search?q=' + encodeURIComponent(title);
  };

  // Parsuje sekcję ŹRÓDŁA — przelicza tylko gdy zmieni się id raportu
  const tickerSources = useMemo((): { title: string; url: string }[] => {
    const text = report?.analysis;
    if (!text) return [];
    const idx = text.search(/ŹRÓDŁA|Źródła|źródła/);
    if (idx === -1) return [];
    const section = text.slice(idx);
    const lines = section.split('\n').slice(1);
    const results: { title: string; url: string }[] = [];
    for (const line of lines) {
      const stripped = line.replace(/^[\s\-*#\d.[\]]+/, '').trim();
      if (!stripped) continue;
      // Zatrzymaj przy nowym nagłówku sekcji
      if (/^\*[A-ZŁŚĆĄŻŹĘ\s]{3,}\*/.test(stripped) || /^---/.test(stripped)) break;
      // Format: "Tytuł – Źródło – Data"
      const rawTitle = stripped.split(/\s[–—-]\s/)[0].replace(/\*+/g, '').trim();
      const title = rawTitle.length > 70 ? rawTitle.slice(0, 67) + '…' : rawTitle;
      if (title.length > 8 && !results.find((r) => r.title === title)) {
        results.push({ title, url: _buildLink(stripped, rawTitle) });
      }
    }
    return results;
  }, [report?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Rewrite ticker titles via nano LLM
  const [rewrittenTitles, setRewrittenTitles] = useState<Record<string, string>>({});
  useEffect(() => {
    if (tickerSources.length === 0) return;
    const originals = tickerSources.map((s) => s.title);
    // Check if we already have rewrites for these exact titles
    if (originals.every((t) => rewrittenTitles[t])) return;
    api.post('/news/rewrite-titles', { titles: originals })
      .then((res) => {
        const map: Record<string, string> = {};
        const rewritten: string[] = res.data.titles;
        originals.forEach((orig, i) => { map[orig] = rewritten[i] || orig; });
        setRewrittenTitles(map);
      })
      .catch(() => { /* keep originals */ });
  }, [tickerSources]); // eslint-disable-line react-hooks/exhaustive-deps

  const buildContextOnly = (): string => {
    const lines: string[] = [];
    if (instruments.length > 0) {
      lines.push('Kursy instrumentów:');
      for (const inst of instruments) {
        let row = `  ${inst.name} (${inst.symbol}): ${
          inst.price != null ? inst.price.toLocaleString('en-US', { maximumFractionDigits: 4 }) : 'N/A'
        }`;
        if (inst.change_pct != null)
          row += ` (${inst.change_pct >= 0 ? '+' : ''}${inst.change_pct.toFixed(2)}%)`;
        lines.push(row);
      }
    }
    if (report?.analysis) {
      lines.push('');
      lines.push('Ostatnia analiza AI (fragment):');
      lines.push(report.analysis.substring(0, 600));
      if (report.analysis.length > 600) lines.push('…(skrócono)');
    }
    if (sources.length > 0) {
      lines.push('');
      lines.push('Źródła informacji:');
      sources.forEach((s) => lines.push(`  - ${s}`));
    }
    // Kalendarz makroekonomiczny — filtruj jak backend: 7 dni, High+Medium
    const todayStr = new Date().toLocaleDateString('sv-SE', { timeZone: APP_TIMEZONE });
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() + 7);
    const cutoffStr = cutoffDate.toLocaleDateString('sv-SE', { timeZone: APP_TIMEZONE });
    const calFiltered = calendarEvents.filter(
      (e) => e.date >= todayStr && e.date <= cutoffStr && (e.impact_raw === 'High' || e.impact_raw === 'Medium'),
    );
    if (calFiltered.length > 0) {
      lines.push('');
      lines.push('=== KALENDARZ MAKROEKONOMICZNY (najbliższe 7 dni, wpływ Wysoki/Średni) ===');
      let currentDate = '';
      for (const e of calFiltered) {
        if (e.date !== currentDate) {
          currentDate = e.date;
          lines.push(`\n${e.date}:`);
        }
        let row = `  ${e.time.padEnd(5)}  ${e.flag} ${e.country.padEnd(4)}  [${e.impact_icon} ${e.impact_label}]  ${e.event}`;
        if (e.forecast) row += `  Prognoza: ${e.forecast}`;
        if (e.previous) row += `  Poprz: ${e.previous}`;
        lines.push(row);
        if (e.significance && e.significance !== 'Dane makroekonomiczne') lines.push(`         → ${e.significance}`);
      }
    }
    return lines.join('\n');
  };

  const buildChatContext = (): string => {
    const lines: string[] = [];
    if (chatPrompt.trim()) {
      lines.push(chatPrompt.trim());
      lines.push('');
    }
    lines.push('--- KONTEKST RYNKOWY ---');
    if (instruments.length > 0) {
      lines.push('');
      lines.push('Aktualne kursy instrumentów:');
      for (const inst of instruments) {
        let row = `  ${inst.name} (${inst.symbol}): ${
          inst.price != null
            ? inst.price.toLocaleString('en-US', { maximumFractionDigits: 4 })
            : 'N/A'
        }`;
        if (inst.change_pct != null)
          row += ` (${inst.change_pct >= 0 ? '+' : ''}${inst.change_pct.toFixed(2)}%)`;
        lines.push(row);
      }
    }
    if (report?.analysis) {
      lines.push('');
      lines.push('Ostatnia analiza AI:');
      lines.push(report.analysis.substring(0, 3000));
    }
    if (sources.length > 0) {
      lines.push('');
      lines.push('Skonfigurowane źródła informacji:');
      sources.forEach((s) => lines.push(`  - ${s}`));
    }
    return lines.join('\n');
  };

  // ── Portfel — prawa myszka ─────────────────────────────────────
  const getFxRate = (currency: string): number => {
    if (currency === 'USD') return 1;
    if (currency === 'PLN') return instruments.find((i) => i.symbol === 'USDPLN=X')?.price ?? 4.0;
    if (currency === 'EUR') {
      const eurusd = instruments.find((i) => i.symbol === 'EURUSD=X')?.price;
      return eurusd ? 1 / eurusd : 0.92;
    }
    return 1;
  };

  const handleInstContextMenu = (e: React.MouseEvent, inst: InstrumentData) => {
    e.preventDefault();
    e.stopPropagation();
    const x = Math.min(e.clientX, window.innerWidth - 215);
    const y = Math.min(e.clientY, window.innerHeight - 115);
    setPortCtx({ x, y, inst });
  };

  const openPortModal = (inst: InstrumentData, tabType: string) => {
    setPortCtx(null);
    const basePrice = inst.price ?? 0;
    setPortForm({ quantity: '', price: basePrice > 0 ? basePrice.toFixed(4) : '', currency: 'USD' });
    setPortModal({ inst, tabType, basePriceUSD: basePrice });
  };

  const handlePortCurrencyChange = (newCurrency: string) => {
    if (!portModal) return;
    if (portModal.basePriceUSD > 0) {
      const converted = portModal.basePriceUSD * getFxRate(newCurrency);
      setPortForm((prev) => ({ ...prev, currency: newCurrency, price: converted.toFixed(4) }));
    } else {
      setPortForm((prev) => ({ ...prev, currency: newCurrency }));
    }
  };

  const submitPortForm = async () => {
    if (!portModal || portAdding) return;
    const qty = parseFloat(portForm.quantity);
    const price = parseFloat(portForm.price);
    if (isNaN(qty) || qty <= 0 || isNaN(price) || price <= 0) return;
    setPortAdding(true);
    try {
      await addPosition({
        symbol: portModal.inst.symbol,
        name: portModal.inst.name,
        quantity: qty,
        buy_price: price,
        buy_currency: portForm.currency,
        tab_type: portModal.tabType,
      });
      setPortModal(null);
      setPortForm({ quantity: '', price: '', currency: 'USD' });
    } finally {
      setPortAdding(false);
    }
  };

  const sendChat = async () => {
    if (!chatInput.trim() || chatLoading) return;
    const userMsg = { role: 'user' as const, content: chatInput.trim() };
    const next = [...chatMessages, userMsg];
    setChatMessages(next);
    setChatInput('');
    setChatLoading(true);
    try {
      const { reply } = await sendMessage(next, buildChatContext(), 'dashboard_chat');
      setChatMessages([...next, { role: 'assistant', content: reply }]);
    } catch {
      setChatMessages([...next, { role: 'assistant', content: 'Blad komunikacji.' }]);
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div className="absolute inset-0 flex overflow-hidden p-2 md:p-4 gap-2 md:gap-4">

      {/* ══ Left sidebar ══════════════════════════════════════ */}
      <div className="hidden md:flex w-[296px] flex-shrink-0 flex-col border border-[var(--gray)] bg-[var(--bg)] overflow-hidden rounded-2xl">

        {/* Assessment gauges — ryzyko i okazja */}
        {(() => {
          const r = assessment?.risk ?? (report?.risk_level ?? 0);
          const o = assessment?.opportunity ?? 0;
          return (
            <div className="border-b border-[var(--gray)] bg-[var(--bg2)]/30 rounded-t-2xl">
              <div className="flex flex-col items-center px-3 pt-3 gap-1">
                <div className="w-52">
                  <GaugeChart
                    label="Ryzyko Rynkowe"
                    value={r}
                    loading={assessmentLoading && !assessment}
                    invertNeedle
                    onClick={() => setAssessmentModal('risk')}
                  />
                </div>
                <div className="w-52">
                  <GaugeChart
                    label="Okazja Inwest."
                    value={o}
                    loading={assessmentLoading && !assessment}
                    onClick={() => setAssessmentModal('opportunity')}
                  />
                </div>
              </div>
              <div className="px-3 pb-2.5">
                <button
                  onClick={() => fetchAssessment()}
                  disabled={assessmentLoading}
                  className="w-full px-3 py-1.5 rounded-lg border border-[var(--accent)]/30 bg-[var(--accent)]/10 text-[10px] text-[var(--accent)] hover:bg-[var(--accent)]/20 hover:border-[var(--accent)]/60 transition-colors disabled:opacity-40 tracking-widest uppercase font-semibold"
                >
                  {assessmentLoading ? 'Analizuję…' : '↻ Odśwież ocenę'}
                </button>
              </div>
            </div>
          );
        })()}

        <div
          className="px-4 py-2.5 border-y border-[var(--gray)] bg-[var(--bg2)] flex-shrink-0 flex items-center justify-between cursor-pointer hover:bg-[var(--gray)]/30 transition-colors select-none"
          onClick={() => { setMarketExpanded((v) => !v); setSelectedInstrument(null); }}
          title="Kliknij aby rozwinąć widok instrumentów"
        >
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-[var(--fg)] uppercase tracking-widest">
              Obserwowane instrumenty
            </span>
            <span className="text-[10px] text-[var(--overlay)] font-mono">24h</span>
          </div>
          <span className={`text-xs font-bold uppercase tracking-widest transition-colors ${marketExpanded ? 'text-[var(--accent)]' : 'text-[var(--overlay)]'}`}>
            {marketExpanded ? '◀' : '▶'}
          </span>
        </div>

        <div className="flex-1 overflow-y-auto p-3 min-h-0 space-y-2" onDragLeave={() => setDragOverIdx(null)}>
          {loadingInst && orderedInstruments.length === 0 ? (
            <p className="text-xs text-[var(--overlay)] text-center py-6">Ladowanie...</p>
          ) : (
            orderedInstruments.map((inst, idx) => (
              <div
                key={inst.symbol}
                draggable
                onDragStart={() => handleDragStart(idx)}
                onDragOver={(e) => handleDragOver(e, idx)}
                onDrop={() => handleDrop(idx)}
                onDragEnd={() => setDragOverIdx(null)}
                onContextMenu={(e) => handleInstContextMenu(e, inst)}
                className={`transition-opacity ${dragOverIdx === idx && dragIdxRef.current !== idx ? 'opacity-50' : 'opacity-100'}`}
                style={{ cursor: 'grab' }}
              >
                <InstCard
                  data={inst}
                  selected={selectedInstrument?.symbol === inst.symbol}
                  onClick={() => handleCardClick(inst)}
                  flash={flashMap[inst.symbol]}
                />
              </div>
            ))
          )}
        </div>
      </div>

      {/* ══ Right panel ═══════════════════════════════════════ */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0 border border-[var(--gray)] rounded-2xl bg-[var(--bg)]">

        {/* Mobile: instruments toggle */}
        <div
          className="md:hidden px-3 py-2 border-b border-[var(--gray)] bg-[var(--bg2)] flex items-center justify-between cursor-pointer select-none"
          onClick={() => { setMarketExpanded((v) => !v); setSelectedInstrument(null); }}
        >
          <span className="text-xs font-bold uppercase tracking-widest">Instrumenty</span>
          <span className={`text-xs font-bold ${marketExpanded ? 'text-[var(--accent)]' : 'text-[var(--overlay)]'}`}>
            {marketExpanded ? '▲' : '▼'}
          </span>
        </div>

        {/* Mobile: mini assessment bar — gauges ukryte w desktop sidebarze */}
        {!selectedInstrument && (() => {
          const r = assessment?.risk ?? (report?.risk_level ?? 0);
          const o = assessment?.opportunity ?? 0;
          const rColor = r === 0 ? '#6c7086' : r <= 3 ? '#a6e3a1' : r <= 6 ? '#f9e2af' : r <= 8 ? '#fab387' : '#f38ba8';
          const oColor = o === 0 ? '#6c7086' : o >= 7 ? '#a6e3a1' : o >= 4 ? '#f9e2af' : '#f38ba8';
          return (
            <div className="md:hidden flex items-center gap-2 px-3 py-1.5 border-b border-[var(--gray)] bg-[var(--bg2)]/50 flex-shrink-0">
              <button
                onClick={() => setAssessmentModal('risk')}
                className="flex-1 flex items-center justify-between px-2.5 py-1 rounded-lg border border-[var(--gray)] bg-[var(--bg)] text-xs active:bg-[var(--gray)]/40"
              >
                <span className="text-[var(--overlay)]">Ryzyko</span>
                <span className="font-bold font-mono" style={{ color: rColor }}>
                  {assessmentLoading && !assessment ? '…' : r > 0 ? `${r}/10` : '?'}
                </span>
              </button>
              <button
                onClick={() => setAssessmentModal('opportunity')}
                className="flex-1 flex items-center justify-between px-2.5 py-1 rounded-lg border border-[var(--gray)] bg-[var(--bg)] text-xs active:bg-[var(--gray)]/40"
              >
                <span className="text-[var(--overlay)]">Okazja</span>
                <span className="font-bold font-mono" style={{ color: oColor }}>
                  {assessmentLoading && !assessment ? '…' : o > 0 ? `${o}/10` : '?'}
                </span>
              </button>
              <button
                onClick={() => fetchAssessment()}
                disabled={assessmentLoading}
                className="p-1.5 rounded-lg border border-[var(--accent)]/30 bg-[var(--accent)]/10 text-[var(--accent)] text-sm disabled:opacity-40 transition-colors active:bg-[var(--accent)]/20"
                title="Odśwież ocenę"
              >
                ↻
              </button>
            </div>
          );
        })()}

        {marketExpanded && !selectedInstrument ? (
          /* ── Expanded market grid ────────────────────────── */
          <>
            <div className="px-5 py-2.5 border-b border-[var(--gray)] bg-[var(--bg2)] flex-shrink-0 flex items-center justify-between rounded-t-2xl">
              <span className="text-xs font-bold text-[var(--fg)] uppercase tracking-widest">Kursy Rynkowe</span>
              <span className="text-[10px] text-[var(--overlay)]">
                Pojedynczy klik&nbsp;→&nbsp;profil
              </span>
            </div>
            <div className="flex-1 overflow-y-auto p-4 min-h-0">
              <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(min(200px, 100%), 1fr))' }}>
                {orderedInstruments.map((inst, idx) => (
                  <div
                    key={inst.symbol}
                    draggable
                    onDragStart={() => handleDragStart(idx)}
                    onDragOver={(e) => handleDragOver(e, idx)}
                    onDrop={() => handleDrop(idx)}
                    onDragEnd={() => setDragOverIdx(null)}
                    onContextMenu={(e) => handleInstContextMenu(e, inst)}
                    className={`transition-opacity ${dragOverIdx === idx && dragIdxRef.current !== idx ? 'opacity-50' : 'opacity-100'}`}
                    style={{ cursor: 'grab' }}
                  >
                    <InstCard
                      data={inst}
                      selected={false}
                      onClick={() => { setSelectedInstrument(inst); setMarketExpanded(false); }}
                      flash={flashMap[inst.symbol]}
                    />
                  </div>
                ))}
              </div>
            </div>
          </>
        ) : selectedInstrument ? (
          /* ── Instrument view ─────────────────────────────── */
          <>
            {/* Header */}
            <div className="flex items-center gap-2 md:gap-3 px-3 md:px-5 py-2 md:py-3 border-b border-[var(--gray)] bg-[var(--bg2)] flex-shrink-0 rounded-t-2xl flex-wrap">
              <div className="flex-1 min-w-0">
                <span className="font-bold text-sm md:text-base">{selectedInstrument.name}</span>
                <span className="ml-2 text-xs md:text-sm text-[var(--overlay)] font-mono">{selectedInstrument.symbol}</span>
              </div>
              {selectedInstrument.price != null && (
                <span className="text-lg font-bold font-mono tabular-nums flex-shrink-0">
                  {selectedInstrument.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 })}
                </span>
              )}
              {selectedInstrument.change_pct != null && (
                <span className={`text-sm font-bold px-2 py-0.5 rounded-md flex-shrink-0 ${
                  (selectedInstrument.change_pct ?? 0) >= 0 ? 'bg-[#a6e3a1]/15 text-[#a6e3a1]' : 'bg-[#f38ba8]/15 text-[#f38ba8]'
                }`}>
                  {(selectedInstrument.change_pct ?? 0) >= 0 ? '+' : ''}{selectedInstrument.change_pct.toFixed(2)}%
                </span>
              )}
              <button
                onClick={() => setSelectedInstrument(null)}
                className="ml-2 text-[var(--overlay)] hover:text-[var(--fg)] text-lg leading-none flex-shrink-0 transition-colors"
                title="Zamknij"
              >
                ✕
              </button>
            </div>

            {/* Scrollable content */}
            <div className="flex-1 overflow-y-auto min-h-0">
              {/* Chart */}
              <div className="px-5 pt-4 pb-2">
                <PriceChart
                  symbol={selectedInstrument.symbol}
                  source={selectedInstrument.source}
                  sparkline={selectedInstrument.sparkline}
                />
              </div>

              {/* Profile panel */}
              <div className="px-5 pb-5">
                <InstrumentProfilePanel
                  symbol={selectedInstrument.symbol}
                  name={selectedInstrument.name}
                  systemPrompt={instrumentProfilePrompt}
                />
              </div>
            </div>
          </>
        ) : (
          /* ── Analysis view ───────────────────────────────── */
          <>
            {/* Action buttons */}
            <div className="flex items-center gap-2 px-3 md:px-5 py-2 md:py-3 border-b border-[var(--gray)] bg-[var(--bg2)] flex-shrink-0 rounded-t-2xl flex-wrap">
              <button
                onClick={handleOpenPicker}
                disabled={analysisRunning}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-[var(--accent)] text-[var(--bg)] font-semibold text-sm hover:opacity-90 disabled:opacity-50 transition-opacity"
              >
                &#9658; Uruchom Analize
              </button>

              <button
                onClick={exportPDF}
                disabled={!report}
                className="px-3 py-1.5 rounded-lg bg-[var(--gray)] text-[var(--fg)] text-sm hover:bg-[var(--overlay)]/40 disabled:opacity-40 transition-colors flex-shrink-0"
              >
                &#128196; Eksport PDF
              </button>

              {/* News ticker — key=report.id restartuje animację przy nowej analizie */}
              {tickerSources.length > 0 && (() => {
                const items = [...tickerSources, ...tickerSources];
                return (
                  <div key={report?.id} className="hidden sm:block flex-1 overflow-hidden mx-3 relative" style={{ minWidth: 0 }}>
                    <div className="absolute inset-y-0 left-0 w-6 z-10 pointer-events-none" style={{ background: 'linear-gradient(to right, var(--bg2), transparent)' }} />
                    <div className="absolute inset-y-0 right-0 w-6 z-10 pointer-events-none" style={{ background: 'linear-gradient(to left, var(--bg2), transparent)' }} />
                    <div className="news-ticker-track">
                      {items.map((s, i) => (
                        <span key={i}>
                          <button
                            onClick={() => window.open(s.url, '_blank')}
                            className="text-xs text-[var(--fg)]/70 hover:text-[var(--accent)] transition-colors cursor-pointer"
                            title={s.title}
                          >
                            {rewrittenTitles[s.title] || s.title}
                          </button>
                          <span className="mx-4 text-[var(--gray)]">·</span>
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })()}

              <div className="ml-auto flex items-center gap-3 flex-shrink-0">
                {sessionCost != null && (
                  <span className="text-xs text-[var(--overlay)]">
                    sesja:&nbsp;<span className="font-mono text-[var(--green)]">{fmtUsd(sessionCost)}</span>
                  </span>
                )}
                {tickerSources.length > 0 && !analysisRunning && (
                  <div className="hidden sm:flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--yellow)]/10 border border-[var(--yellow)]/35 select-none"
                    title={`${tickerSources.length} aktualnych newsów`}>
                    <span className="text-sm animate-bounce" style={{ animationDuration: '1.8s' }}>🔥</span>
                    <span className="text-[10px] font-bold text-[var(--yellow)] tracking-widest uppercase">Hot News</span>
                    <span className="text-[10px] font-mono text-[var(--yellow)]/70">{tickerSources.length}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Report info bar */}
            {report && (
              <div className="px-3 md:px-5 py-1.5 border-b border-[var(--gray)] bg-[var(--bg2)] flex-shrink-0 text-[10px] md:text-xs text-[var(--overlay)] flex items-center gap-2 md:gap-3 flex-wrap">
                <span>
                  <span className="text-[var(--fg)]/60 mr-1">Model:</span>
                  <span className="font-mono text-[var(--fg)]">{report.provider}/{report.model}</span>
                </span>
                <span className="text-[var(--gray)]">|</span>
                <span>
                  <span className="text-[var(--fg)]/60 mr-1">in</span>
                  <span className="font-mono text-[var(--fg)]">{report.input_tokens.toLocaleString()}</span>
                  <span className="text-[var(--fg)]/60 mx-1">out</span>
                  <span className="font-mono text-[var(--fg)]">{report.output_tokens.toLocaleString()}</span>
                  <span className="text-[var(--fg)]/60 mx-1">tok</span>
                </span>
                {(() => { const c = calcCost(report.provider, report.model, report.input_tokens, report.output_tokens); return c != null ? (
                  <>
                    <span className="text-[var(--gray)]">|</span>
                    <span>
                      <span className="text-[var(--fg)]/60 mr-1">raport:</span>
                      <span className="font-mono text-[var(--green)]">{fmtUsd(c)}</span>
                    </span>
                  </>
                ) : null; })()}
                {report.created_at && (() => {
                  const d = new Date(report.created_at);
                  return (
                    <>
                      <span className="text-[var(--gray)]">|</span>
                      <span className="font-mono text-[var(--accent)]">
                        {d.toLocaleDateString('pl-PL', { timeZone: APP_TIMEZONE })} {d.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit', timeZone: APP_TIMEZONE })}
                      </span>
                    </>
                  );
                })()}
              </div>
            )}

            {/* Analysis content */}
            <div className="flex-1 overflow-y-auto px-3 md:px-5 py-3 md:py-5 min-h-0">
              {analysisRunning ? (
                <div className="flex flex-col items-center justify-center py-16 gap-5">
                  <div className="flex gap-2">
                    {[0, 1, 2].map((i) => (
                      <div
                        key={i}
                        className="w-2.5 h-2.5 rounded-full bg-[var(--accent)] animate-bounce"
                        style={{ animationDelay: `${i * 0.18}s` }}
                      />
                    ))}
                  </div>
                  <p className="text-[var(--fg)] text-sm font-medium text-center transition-all duration-500">
                    {ANALYSIS_STEPS[analysisStep]}
                  </p>
                  <p className="text-xs text-[var(--overlay)]">
                    Analiza rynków w toku &bull; krok {analysisStep + 1}/{ANALYSIS_STEPS.length}
                  </p>
                </div>
              ) : !report ? (
                <div className="flex flex-col items-center justify-center py-16 gap-3">
                  <p className="text-[var(--overlay)] text-base">Brak raportu</p>
                  <p className="text-sm text-[var(--overlay)]/70">
                    Kliknij "Uruchom Analize" aby wygenerowac raport AI
                  </p>
                </div>
              ) : (
                <div
                  ref={analysisRef}
                  className="md-content text-sm"
                  onMouseDown={(e) => { if (e.detail === 2) e.preventDefault(); }}
                  onDoubleClick={() => setAnalysisExpanded(true)}
                  title="Kliknij dwukrotnie aby powiększyć"
                >
                  <ReactMarkdown>{report.analysis || ''}</ReactMarkdown>
                </div>
              )}
            </div>

            {/* Chat — desktop only, mobile uses floating bubble */}
            <div className="hidden md:flex border-t border-[var(--gray)] flex-col flex-shrink-0" style={{ height: `${chatHeight}px` }}>
              {/* Drag handle */}
              <div
                onMouseDown={startResize}
                className="h-1.5 flex-shrink-0 cursor-ns-resize bg-[var(--gray)] hover:bg-[var(--accent)] transition-colors"
                title="Przeciągnij aby zmienić rozmiar"
              />
              <div
                className="px-5 py-2 border-b border-[var(--gray)] flex-shrink-0 cursor-pointer hover:bg-[var(--gray)]/20 transition-colors select-none"
                onClick={() => setChatCtxOpen((v) => !v)}
                title="Kliknij aby zobaczyć kontekst czatu"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[var(--fg)] uppercase tracking-widest">
                    Czat z AI
                  </span>
                  <span className="text-[var(--overlay)] text-[10px]">{chatCtxOpen ? '▲' : '▼'} kontekst</span>
                </div>
              </div>
              {chatCtxOpen && (
                <div className="border-b border-[var(--gray)] bg-[var(--bg2)] flex-shrink-0 max-h-44 overflow-y-auto">
                  <div className="px-5 py-3 space-y-2">
                    <p className="text-xs font-semibold text-[var(--fg)]/60 uppercase tracking-wide mb-1">
                      Kontekst wysyłany do AI:
                    </p>
                    <pre className="text-xs font-mono text-[var(--fg)]/75 whitespace-pre-wrap leading-relaxed">
                      {buildContextOnly()}
                    </pre>
                  </div>
                </div>
              )}
              <div className="flex-1 overflow-y-auto px-5 py-2 space-y-1.5 min-h-0">
                {chatMessages.length === 0 && (
                  <p className="text-xs text-[var(--overlay)] text-center py-3">
                    Zadaj pytanie o rynki i analizy...
                  </p>
                )}
                {chatMessages.map((m, i) => (
                  <div
                    key={i}
                    className={`text-sm max-w-[85%] py-1 ${
                      m.role === 'user'
                        ? 'text-[#f9e2af] ml-auto text-right font-medium'
                        : 'text-[#a6e3a1] chat-reply'
                    }`}
                  >
                    {m.content}
                  </div>
                ))}
                {chatLoading && (
                  <div className="text-sm text-[#a6e3a1] animate-pulse">
                    Mysle...
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>
              <div className="flex gap-2 px-3 md:px-5 py-2 md:py-2.5 border-t border-[var(--gray)] flex-shrink-0 rounded-b-2xl">
                <input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && sendChat()}
                  placeholder="Napisz wiadomosc..."
                  className="flex-1 bg-[var(--bg2)] border border-[var(--gray)] rounded-lg px-3 py-1.5 text-sm text-[var(--fg)] focus:border-[var(--accent)] outline-none transition-colors"
                />
                <button
                  onClick={sendChat}
                  disabled={chatLoading}
                  className="px-4 py-1.5 rounded-lg bg-[var(--accent)] text-[var(--bg)] font-semibold text-sm hover:opacity-90 disabled:opacity-50 transition-opacity"
                >
                  Wyslij
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* ══ Analysis expanded overlay ══════════════════════ */}
      {analysisExpanded && report && (
        <div className="absolute inset-0 z-50 flex flex-col bg-[var(--bg)]">
          {/* Header */}
          <div className="flex items-center gap-2 sm:gap-3 px-3 sm:px-6 py-3 border-b border-[var(--gray)] bg-[var(--bg2)] flex-shrink-0">
            <span className="text-xs font-bold text-[var(--fg)] uppercase tracking-widest flex-1">
              Analiza rynkowa
            </span>
            <span className="text-xs text-[var(--overlay)] hidden sm:inline">
              {report.provider}/{report.model}
              &nbsp;&bull;&nbsp;
              {report.input_tokens + report.output_tokens} tokenów
            </span>
            <button
              onClick={exportPDF}
              className="px-3 py-1 rounded-lg bg-[var(--gray)] text-[var(--fg)] text-xs hover:bg-[var(--overlay)]/40 transition-colors"
            >
              &#128196; Eksport PDF
            </button>
            <button
              onClick={() => setAnalysisExpanded(false)}
              className="ml-1 text-[var(--overlay)] hover:text-[var(--fg)] text-lg leading-none transition-colors"
              title="Zamknij (Esc)"
            >
              ✕
            </button>
          </div>
          {/* Content */}
          <div className="flex-1 overflow-y-auto px-4 sm:px-10 py-4 sm:py-8 min-h-0">
            <div
              ref={analysisRef}
              className="md-content max-w-4xl mx-auto"
              onMouseDown={(e) => { if (e.detail === 2) e.preventDefault(); }}
              onDoubleClick={() => setAnalysisExpanded(false)}
              title="Kliknij dwukrotnie aby zamknąć"
            >
              <ReactMarkdown>{report.analysis || ''}</ReactMarkdown>
            </div>
          </div>
        </div>
      )}


      {/* ══ Assessment modal ═══════════════════════════════════ */}
      {assessmentModal && (
        <div
          className="fixed inset-0 z-[150] flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={() => setAssessmentModal(null)}
        >
          <div
            className="bg-[var(--bg2)] border border-[var(--gray)] rounded-2xl p-6 w-[440px] max-w-[92vw] shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {(() => {
              const isRisk = assessmentModal === 'risk';
              const value = isRisk ? (assessment?.risk ?? 0) : (assessment?.opportunity ?? 0);
              const reason = isRisk ? assessment?.risk_reason : assessment?.opportunity_reason;
              const riskColor = (v: number) => v <= 3 ? '#a6e3a1' : v <= 6 ? '#f9e2af' : v <= 8 ? '#fab387' : '#f38ba8';
              const oppColor  = (v: number) => v >= 7 ? '#a6e3a1' : v >= 4 ? '#f9e2af' : '#f38ba8';
              const color = isRisk ? riskColor(value) : oppColor(value);
              const pct = (value / 10) * 100;
              return (
                <>
                  <div className="flex items-center justify-between mb-5">
                    <h2 className="text-base font-bold">{isRisk ? 'Ryzyko Rynkowe' : 'Okazja Inwestycyjna'}</h2>
                    <button
                      onClick={() => setAssessmentModal(null)}
                      className="text-[var(--overlay)] hover:text-[var(--fg)] text-lg leading-none transition-colors"
                    >✕</button>
                  </div>
                  <div className="text-center mb-4">
                    <span className="text-6xl font-bold font-mono tabular-nums" style={{ color }}>{value}</span>
                    <span className="text-2xl font-mono text-[var(--fg)]/40">/10</span>
                  </div>
                  <div className="h-2 bg-[var(--gray)] rounded-full overflow-hidden mb-5">
                    <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, background: color }} />
                  </div>
                  {reason ? (
                    <p className="text-sm text-[var(--fg)]/80 leading-relaxed">{reason}</p>
                  ) : (
                    <p className="text-sm text-[var(--overlay)] italic">Brak uzasadnienia — uruchom ocenę ponownie.</p>
                  )}
                  <div className="flex gap-3 justify-end mt-6">
                    <button
                      onClick={() => { fetchAssessment(); setAssessmentModal(null); }}
                      disabled={assessmentLoading}
                      className="px-4 py-2 rounded-lg text-sm bg-[var(--bg)] border border-[var(--gray)] text-[var(--overlay)] hover:text-[var(--fg)] disabled:opacity-40 transition-colors"
                    >
                      ↻ Odśwież
                    </button>
                    <button
                      onClick={() => setAssessmentModal(null)}
                      className="px-5 py-2 rounded-lg text-sm bg-[var(--accent)] text-[var(--bg)] font-semibold hover:opacity-90 transition-opacity"
                    >
                      Zamknij
                    </button>
                  </div>
                </>
              );
            })()}
          </div>
        </div>
      )}

      {/* ══ Context menu: dodaj do portfela (prawy klik) ══════════ */}
      {portCtx && (
        <div
          style={{ position: 'fixed', top: portCtx.y, left: portCtx.x, zIndex: 9999 }}
          className="bg-[var(--bg2)] border border-[var(--gray)] rounded-xl shadow-2xl py-1.5 min-w-[205px]"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="px-3 py-1.5 border-b border-[var(--gray)] mb-1">
            <p className="text-xs font-semibold text-[var(--fg)] truncate">{portCtx.inst.name}</p>
            <p className="text-[10px] font-mono text-[var(--overlay)]">
              {portCtx.inst.symbol}
              {portCtx.inst.price != null && (
                <span className="ml-1.5 text-[var(--fg)]/70">
                  {portCtx.inst.price.toLocaleString('en-US', { maximumFractionDigits: 4 })}
                </span>
              )}
            </p>
          </div>
          <button
            onClick={() => openPortModal(portCtx.inst, 'zakupione')}
            className="w-full text-left px-3 py-2 text-xs text-[var(--fg)] hover:bg-[var(--gray)] transition-colors flex items-center gap-2 rounded-lg"
          >
            <span className="text-[#a6e3a1] font-bold">↑</span> Dodaj do Long
          </button>
          <button
            onClick={() => openPortModal(portCtx.inst, 'short')}
            className="w-full text-left px-3 py-2 text-xs text-[var(--fg)] hover:bg-[var(--gray)] transition-colors flex items-center gap-2 rounded-lg"
          >
            <span className="text-[#f38ba8] font-bold">↓</span> Dodaj do Short
          </button>
        </div>
      )}

      {/* ══ Modal: dodaj do portfela ══════════════════════════════ */}
      {portModal && (
        <div
          className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={() => setPortModal(null)}
        >
          <div
            className="bg-[var(--bg2)] rounded-2xl border border-[var(--gray)] w-full max-w-sm shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Nagłówek */}
            <div className="flex items-center justify-between px-5 py-3.5 border-b border-[var(--gray)]">
              <div>
                <p className="font-semibold text-sm">{portModal.inst.name}</p>
                <p className="text-[10px] text-[var(--overlay)] font-mono mt-0.5">
                  {portModal.inst.symbol}
                  {portModal.inst.price != null && (
                    <span className="ml-2 text-[var(--fg)]/50">
                      ${portModal.inst.price.toLocaleString('en-US', { maximumFractionDigits: 4 })}
                    </span>
                  )}
                </p>
              </div>
              <button
                onClick={() => setPortModal(null)}
                className="text-[var(--overlay)] hover:text-[var(--fg)] text-lg p-1 transition-colors leading-none"
              >✕</button>
            </div>

            <div className="p-5 space-y-4">
              {/* Long / Short */}
              <div className="flex gap-2">
                <button
                  onClick={() => setPortModal((prev) => prev ? { ...prev, tabType: 'zakupione' } : prev)}
                  className={`flex-1 py-2 rounded-lg text-sm font-semibold border transition-colors ${
                    portModal.tabType === 'zakupione'
                      ? 'border-[#a6e3a1] bg-[#a6e3a1]/15 text-[#a6e3a1]'
                      : 'border-[var(--gray)] text-[var(--overlay)] hover:border-[var(--fg)]/30'
                  }`}
                >↑ Long</button>
                <button
                  onClick={() => setPortModal((prev) => prev ? { ...prev, tabType: 'short' } : prev)}
                  className={`flex-1 py-2 rounded-lg text-sm font-semibold border transition-colors ${
                    portModal.tabType === 'short'
                      ? 'border-[#f38ba8] bg-[#f38ba8]/15 text-[#f38ba8]'
                      : 'border-[var(--gray)] text-[var(--overlay)] hover:border-[var(--fg)]/30'
                  }`}
                >↓ Short</button>
              </div>

              {/* Ilość */}
              <div>
                <label className="text-xs text-[var(--overlay)] block mb-1">Ilość</label>
                <input
                  type="number" step="any" min="0"
                  value={portForm.quantity}
                  onChange={(e) => setPortForm((prev) => ({ ...prev, quantity: e.target.value }))}
                  placeholder="np. 10"
                  autoFocus
                  className="w-full bg-[var(--bg)] border border-[var(--gray)] rounded-lg px-3 py-2 text-sm focus:border-[var(--accent)] outline-none transition-colors"
                />
              </div>

              {/* Cena nabycia */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs text-[var(--overlay)]">Cena nabycia ({portForm.currency})</label>
                  {portModal.basePriceUSD > 0 && (
                    <button
                      onClick={() => {
                        const p = portModal.basePriceUSD * getFxRate(portForm.currency);
                        setPortForm((prev) => ({ ...prev, price: p.toFixed(4) }));
                      }}
                      title={`Przywróć aktualną cenę: $${portModal.basePriceUSD.toLocaleString('en-US', { maximumFractionDigits: 4 })}`}
                      className="text-[10px] px-2 py-0.5 rounded-md border border-[var(--accent)]/50 bg-[var(--accent)]/10 text-[var(--accent)] hover:bg-[var(--accent)]/20 transition-colors font-mono"
                    >
                      Aktualna
                    </button>
                  )}
                </div>
                <input
                  type="number" step="any" min="0"
                  value={portForm.price}
                  onChange={(e) => setPortForm((prev) => ({ ...prev, price: e.target.value }))}
                  placeholder="Cena"
                  className="w-full bg-[var(--bg)] border border-[var(--gray)] rounded-lg px-3 py-2 text-sm focus:border-[var(--accent)] outline-none transition-colors"
                />
              </div>

              {/* Waluta — zmiana przelicza cenę */}
              <div>
                <label className="text-xs text-[var(--overlay)] block mb-1.5">Waluta (przelicza cenę)</label>
                <div className="flex gap-2">
                  {(['USD', 'PLN', 'EUR'] as const).map((cur) => (
                    <button
                      key={cur}
                      onClick={() => handlePortCurrencyChange(cur)}
                      className={`flex-1 py-1.5 rounded-lg text-sm font-mono border transition-colors ${
                        portForm.currency === cur
                          ? 'border-[var(--accent)] bg-[var(--accent)]/15 text-[var(--accent)]'
                          : 'border-[var(--gray)] text-[var(--overlay)] hover:border-[var(--fg)]/30'
                      }`}
                    >{cur}</button>
                  ))}
                </div>
              </div>

              {/* Dodaj */}
              <button
                onClick={submitPortForm}
                disabled={portAdding || !portForm.quantity || !portForm.price}
                className="w-full py-2.5 rounded-xl font-semibold text-sm transition-opacity hover:opacity-90 disabled:opacity-40 bg-[var(--accent)] text-[var(--bg)]"
              >
                {portAdding ? 'Dodawanie…' : `Dodaj do ${portModal.tabType === 'zakupione' ? 'Long' : 'Short'}`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══ Mobile: floating chat bubble ══════════════════════════ */}
      <button
        className="md:hidden fixed bottom-5 right-4 z-40 w-14 h-14 rounded-full bg-[var(--accent)] text-[var(--bg)] shadow-2xl flex items-center justify-center text-2xl active:scale-95 transition-transform"
        onClick={() => setChatOpen(true)}
        title="Czat z AI"
      >
        💬
      </button>

      {/* ══ Mobile: chat overlay ═══════════════════════════════════ */}
      {chatOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex flex-col bg-[var(--bg)]">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--gray)] bg-[var(--bg2)] flex-shrink-0">
            <span className="text-sm font-bold uppercase tracking-widest">Czat z AI</span>
            <button onClick={() => setChatOpen(false)} className="text-[var(--overlay)] hover:text-[var(--fg)] text-xl leading-none transition-colors">✕</button>
          </div>
          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2 min-h-0">
            {chatMessages.length === 0 && (
              <p className="text-xs text-[var(--overlay)] text-center py-4">Zadaj pytanie o rynki i analizy...</p>
            )}
            {chatMessages.map((m, i) => (
              <div key={i} className={`text-sm max-w-[85%] py-1 ${m.role === 'user' ? 'text-[#f9e2af] ml-auto text-right font-medium' : 'text-[#a6e3a1] chat-reply'}`}>
                {m.content}
              </div>
            ))}
            {chatLoading && <div className="text-sm text-[#a6e3a1] animate-pulse">Myślę...</div>}
            <div ref={chatEndRef} />
          </div>
          <div className="flex gap-2 px-4 py-3 border-t border-[var(--gray)] flex-shrink-0">
            <input
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && sendChat()}
              placeholder="Napisz wiadomość..."
              className="flex-1 bg-[var(--bg2)] border border-[var(--gray)] rounded-lg px-3 py-2 text-sm text-[var(--fg)] focus:border-[var(--accent)] outline-none transition-colors"
              autoFocus
            />
            <button
              onClick={sendChat}
              disabled={chatLoading}
              className="px-4 py-2 rounded-lg bg-[var(--accent)] text-[var(--bg)] font-semibold text-sm hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              Wyślij
            </button>
          </div>
        </div>
      )}

      {/* ══ Modal wyboru modelu ══════════════════════════════════ */}
      {showModelPicker && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={() => setShowModelPicker(false)}
        >
          <div
            className="bg-[var(--bg2)] border border-[var(--gray)] rounded-2xl p-6 w-[400px] shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-base font-bold mb-4">Wybierz model do analizy</h2>

            {/* Provider */}
            <div className="mb-4">
              <label className="text-xs text-[var(--overlay)] block mb-2 uppercase tracking-widest font-semibold">Dostawca</label>
              <div className="flex gap-2 flex-wrap">
                {availableProviders.length === 0
                  ? <p className="text-xs text-[var(--red)]">Brak skonfigurowanych kluczy API. Przejdź do Ustawień.</p>
                  : availableProviders.map((p) => (
                    <button
                      key={p}
                      onClick={() => {
                        setPickerProvider(p);
                        setPickerModel(PROVIDER_MODELS[p]?.[0]?.value ?? '');
                      }}
                      className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                        pickerProvider === p
                          ? 'bg-[var(--accent)] text-[var(--bg)]'
                          : 'bg-[var(--bg)] border border-[var(--gray)] text-[var(--fg)] hover:border-[var(--accent)]/50'
                      }`}
                    >
                      {p}
                    </button>
                  ))
                }
              </div>
            </div>

            {/* Model */}
            {pickerProvider && PROVIDER_MODELS[pickerProvider] && (
              <div className="mb-6">
                <label className="text-xs text-[var(--overlay)] block mb-2 uppercase tracking-widest font-semibold">Model</label>
                <div className="space-y-1.5">
                  {PROVIDER_MODELS[pickerProvider].map((m) => (
                    <button
                      key={m.value}
                      onClick={() => setPickerModel(m.value)}
                      className={`w-full text-left px-4 py-2 rounded-lg text-sm transition-colors ${
                        pickerModel === m.value
                          ? 'bg-[var(--accent)]/15 border border-[var(--accent)] text-[var(--fg)]'
                          : 'bg-[var(--bg)] border border-[var(--gray)] text-[var(--fg)] hover:border-[var(--accent)]/40'
                      }`}
                    >
                      {m.label}
                      <span className="ml-2 text-[10px] text-[var(--overlay)] font-mono">{m.value}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowModelPicker(false)}
                className="px-4 py-2 rounded-lg text-sm bg-[var(--bg)] border border-[var(--gray)] text-[var(--overlay)] hover:text-[var(--fg)] transition-colors"
              >
                Anuluj
              </button>
              <button
                onClick={() => handleRunAnalysis(pickerProvider, pickerModel)}
                disabled={!pickerProvider || !pickerModel}
                className="px-5 py-2 rounded-lg text-sm bg-[var(--accent)] text-[var(--bg)] font-semibold hover:opacity-90 disabled:opacity-40 transition-opacity"
              >
                &#9658; Uruchom
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

