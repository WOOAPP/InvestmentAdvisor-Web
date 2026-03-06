import { useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { getInstruments, refreshInstruments, getSparkline, getInstrumentUnit, type InstrumentData } from '../api/market';
import { getReports, getReport } from '../api/reports';
import { getPositions, addPosition, type Position } from '../api/portfolio';
import { sendMessage, type ChatMessage } from '../api/chat';
import { getCalendar, type CalendarEvent } from '../api/calendar';
import PriceChart from '../components/PriceChart';
import InstrumentProfilePanel from '../components/InstrumentProfilePanel';
import api from '../api/client';
import { useChatStorage } from '../hooks/useChatStorage';
import { APP_TIMEZONE } from '../config';

// ── Mini sparkline SVG (identyczny jak na Dashboard) ──────────
function Sparkline({ data, changePct }: { data: number[]; changePct: number | null }) {
  if (data.length < 2) return <div style={{ height: 28 }} />;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const W = 100, H = 28;
  const pts = data.map((v, i) => ({
    x: (i / (data.length - 1)) * W,
    y: H - ((v - min) / range) * (H - 4) - 2,
  }));
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

// ── Kafelek instrumentu (identyczny styl jak na Dashboard) ────
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
          <div
            key={flash}
            className={`text-sm font-semibold leading-tight flex items-baseline gap-1 min-w-0 ${
              flash === 'up' ? 'flash-up' : flash === 'down' ? 'flash-down' : ''
            }`}
          >
            <span className="truncate">{data.name}</span>
            {unit && <span className="text-[11px] font-mono text-[var(--overlay)] flex-shrink-0 opacity-80">{unit}</span>}
          </div>
        </div>
        {pct != null && (
          <span
            className={`text-xs font-bold px-1.5 py-0.5 rounded-md flex-shrink-0 ${
              isUp ? 'bg-[#a6e3a1]/15 text-[#a6e3a1]' : 'bg-[#f38ba8]/15 text-[#f38ba8]'
            }`}
          >
            {isUp ? '+' : ''}{pct.toFixed(2)}%
          </span>
        )}
      </div>
      <div className="text-xl font-bold font-mono mt-1.5 tabular-nums">
        {data.price != null
          ? data.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 })
          : data.error
            ? <span className="text-sm font-normal text-[var(--red)]">Błąd danych</span>
            : '—'}
      </div>
      <Sparkline data={data.sparkline} changePct={data.change_pct} />
    </div>
  );
}

// ── Dane statystyczne dla jednego interwału ────────────────────
interface TfStats {
  open: number;
  close: number;
  high: number;
  low: number;
  changePct: number;
  points: number;
}

const TF_LABELS: Record<string, string> = {
  '5m':  '5 minut (1 dzień)',
  '15m': '15 minut (5 dni)',
  '1h':  '1 godzina (5 dni)',
  '24h': '24 godziny (60 dni)',
  '72h': '72 godziny (1 rok)',
};

const ALL_TIMEFRAMES = ['5m', '15m', '1h', '24h', '72h'];

// ── Główna strona Wykresy ──────────────────────────────────────
export default function Charts() {
  const [instruments, setInstruments] = useState<InstrumentData[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<InstrumentData | null>(null);
  const [flashMap, setFlashMap] = useState<Record<string, 'up' | 'down'>>({});
  const [instSearch, setInstSearch] = useState('');
  const prevPricesRef = useRef<Record<string, number | null>>({});

  // Kolejność kafelków — ta sama co na Dashboard (localStorage)
  const orderedInstruments = useMemo(() => {
    try {
      const order: string[] = JSON.parse(localStorage.getItem('dash_instrument_order_v1') || '[]');
      if (order.length === 0) return instruments;
      const ordered = order
        .map((sym) => instruments.find((i) => i.symbol === sym))
        .filter(Boolean) as InstrumentData[];
      const rest = instruments.filter((i) => !order.includes(i.symbol));
      return [...ordered, ...rest];
    } catch { return instruments; }
  }, [instruments]);

  // Dane wszystkich interwałów dla wybranego instrumentu
  const [tfData, setTfData] = useState<Record<string, TfStats>>({});
  const [tfLoading, setTfLoading] = useState(false);

  // Kontekst chatu
  const [latestAnalysis, setLatestAnalysis] = useState('');
  const [positions, setPositions] = useState<Position[]>([]);
  const [basePrompt, setBasePrompt] = useState('');
  const [instrumentProfilePrompt, setInstrumentProfilePrompt] = useState('');
  const [calendarEvents, setCalendarEvents] = useState<CalendarEvent[]>([]);

  // Chat z persistencją 72h — osobna historia per instrument
  const chatStorageKey = selected ? `chat:charts:${selected.symbol}` : 'chat:charts';
  const { messages: chatMessages, setMessages: setChatMessages, clearMessages } = useChatStorage(chatStorageKey);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const [chatCtxOpen, setChatCtxOpen] = useState(false);
  const [mobilePanel, setMobilePanel] = useState<'chart' | 'instruments' | 'chat'>('chart');
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; html: string } | null>(null);
  const [selectedMsg, setSelectedMsg] = useState<number | null>(null);

  // Dodaj do portfela — context menu (prawy przycisk myszy)
  const [portCtx, setPortCtx] = useState<{ x: number; y: number; inst: InstrumentData } | null>(null);
  const [portModal, setPortModal] = useState<{ inst: InstrumentData; tabType: string; basePriceUSD: number } | null>(null);
  const [portForm, setPortForm] = useState({ quantity: '', price: '', currency: 'USD' });
  const [portAdding, setPortAdding] = useState(false);

  // ── Inicjalny load ─────────────────────────────────────────
  useEffect(() => {
    Promise.all([
      getInstruments(),
      getReports(1).then((list) =>
        list.length > 0 ? getReport(list[0].id).then((r) => r.analysis || '') : ''
      ),
      getPositions('zakupione'),
      getPositions('short'),
      api.get('/settings').then((r) => ({
        charts: r.data.charts_chat_prompt || '',
        profile: r.data.instrument_profile_prompt || '',
      })),
      getCalendar().then((r) => r.events).catch(() => [] as CalendarEvent[]),
    ])
      .then(([insts, analysis, longPos, shortPos, prompts, calEvents]) => {
        setInstruments(insts);
        for (const inst of insts as InstrumentData[]) {
          prevPricesRef.current[inst.symbol] = inst.price ?? null;
        }
        if (insts.length > 0) {
          try {
            const order: string[] = JSON.parse(localStorage.getItem('dash_instrument_order_v1') || '[]');
            const first = order.length > 0
              ? (insts as InstrumentData[]).find((i) => i.symbol === order[0]) ?? (insts as InstrumentData[])[0]
              : (insts as InstrumentData[])[0];
            setSelected(first);
          } catch { setSelected((insts as InstrumentData[])[0]); }
        }
        setLatestAnalysis(analysis as string);
        setPositions([...(longPos as Position[]), ...(shortPos as Position[])]);
        const p = prompts as { charts: string; profile: string };
        setBasePrompt(p.charts);
        setInstrumentProfilePrompt(p.profile);
        setCalendarEvents(calEvents as CalendarEvent[]);
      })
      .finally(() => setLoading(false));
  }, []);

  // ── Auto-odświeżanie cen co 60s + flash przy zmianie ──────────
  useEffect(() => {
    const refresh = () => {
      refreshInstruments().then((newInsts) => {
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
          setTimeout(() => setFlashMap({}), 1500);
        }
      }).catch(() => {});
    };
    const iv = setInterval(refresh, 60_000);
    // Natychmiastowy refresh po zmianie listy instrumentów w Ustawieniach
    window.addEventListener('instruments-changed', refresh);
    return () => {
      clearInterval(iv);
      window.removeEventListener('instruments-changed', refresh);
    };
  }, []);

  // ── Pobierz dane wszystkich interwałów po zmianie instrumentu ─
  useEffect(() => {
    if (!selected) { setTfData({}); return; }
    setTfLoading(true);
    const src = selected.source || 'yfinance';

    Promise.all(
      ALL_TIMEFRAMES.map((tf) =>
        getSparkline(selected.symbol, tf, src)
          .then((prices) => ({ tf, prices }))
          .catch(() => ({ tf, prices: [] as number[] }))
      )
    ).then((results) => {
      const data: Record<string, TfStats> = {};
      for (const { tf, prices } of results) {
        if (prices.length >= 1) {
          const open = prices[0];
          const close = prices[prices.length - 1];
          data[tf] = {
            open,
            close,
            high: Math.max(...prices),
            low: Math.min(...prices),
            changePct: prices.length >= 2 && open !== 0
              ? ((close - open) / open) * 100
              : 0,
            points: prices.length,
          };
        }
      }
      setTfData(data);
    }).finally(() => setTfLoading(false));
  }, [selected?.symbol]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  useEffect(() => {
    if (!contextMenu) return;
    const close = () => { setContextMenu(null); setSelectedMsg(null); };
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, [contextMenu]);

  useEffect(() => {
    if (!portCtx) return;
    const close = () => setPortCtx(null);
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, [portCtx]);

  const handleSelect = (inst: InstrumentData) => {
    setSelected(inst);
    setMobilePanel('chart');
  };

  // ── Kontekst do wyświetlenia w panelu (bez base promptu) ─────
  const buildContextOnly = (): string => {
    const lines: string[] = [];
    if (selected) {
      lines.push(`Instrument: ${selected.name} (${selected.symbol})`);
      if (selected.price != null)
        lines.push(`Cena: ${selected.price.toLocaleString('en-US', { maximumFractionDigits: 4 })}`);
      if (selected.change_pct != null)
        lines.push(`Zmiana: ${selected.change_pct >= 0 ? '+' : ''}${selected.change_pct.toFixed(2)}%`);
      if (Object.keys(tfData).length > 0 || !tfLoading) {
        lines.push('');
        lines.push('Dane historyczne:');
        for (const tf of ALL_TIMEFRAMES) {
          const d = tfData[tf];
          if (!d) { lines.push(`  ${tf.padEnd(4)} | brak danych`); continue; }
          const fmt = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 4 });
          lines.push(`  ${tf.padEnd(4)} | O=${fmt(d.open)} H=${fmt(d.high)} L=${fmt(d.low)} C=${fmt(d.close)} | ${d.changePct >= 0 ? '+' : ''}${d.changePct.toFixed(2)}%`);
        }
      }
    }
    if (instruments.length > 0) {
      lines.push('');
      lines.push('Obserwowane instrumenty:');
      for (const inst of instruments) {
        let row = `  ${inst.name}: ${inst.price != null ? inst.price.toLocaleString('en-US', { maximumFractionDigits: 4 }) : 'N/A'}`;
        if (inst.change_pct != null) row += ` (${inst.change_pct >= 0 ? '+' : ''}${inst.change_pct.toFixed(2)}%)`;
        lines.push(row);
      }
    }
    if (positions.length > 0) {
      lines.push('');
      lines.push('Portfel:');
      for (const p of positions) {
        lines.push(`  ${p.name}: ${p.quantity} szt. @ ${p.buy_price} ${p.buy_currency} [${p.tab_type}]`);
      }
    }
    if (latestAnalysis) {
      lines.push('');
      lines.push('Ostatnia analiza AI (fragment):');
      lines.push(latestAnalysis.substring(0, 400));
      if (latestAnalysis.length > 400) lines.push('…(skrócono)');
    }
    const highImpact = calendarEvents.filter((e) => e.impact_raw === 'High');
    const medImpact = calendarEvents.filter((e) => e.impact_raw === 'Medium');
    const calFiltered = [...highImpact, ...medImpact].slice(0, 10);
    if (calFiltered.length > 0) {
      lines.push('');
      lines.push(`Kalendarz makro (7 dni, ${calFiltered.length} wydarzeń):`);
      for (const e of calFiltered) {
        lines.push(`  ${e.date} ${e.time}  ${e.flag} ${e.country}  [${e.impact_label}]  ${e.event}`);
      }
    }
    return lines.join('\n');
  };

  // ── Buduj system prompt z danymi wszystkich interwałów ────────
  const buildSystemPrompt = (): string => {
    const lines: string[] = [];

    if (basePrompt.trim()) {
      lines.push(basePrompt.trim());
      lines.push('');
    }

    lines.push('--- KONTEKST RYNKOWY ---');

    if (selected) {
      lines.push('');
      lines.push(`Aktualnie wybrany instrument: ${selected.name} (${selected.symbol})`);
      if (selected.price != null)
        lines.push(
          `Aktualna cena: ${selected.price.toLocaleString('en-US', { maximumFractionDigits: 4 })}`
        );
      if (selected.change_pct != null)
        lines.push(
          `Zmiana (dziś): ${selected.change_pct >= 0 ? '+' : ''}${selected.change_pct.toFixed(2)}%`
        );

      // Dane wszystkich interwałów
      if (Object.keys(tfData).length > 0) {
        lines.push('');
        lines.push('Dane historyczne po interwałach:');
        for (const tf of ALL_TIMEFRAMES) {
          const d = tfData[tf];
          if (!d) { lines.push(`  ${tf.padEnd(4)} (${TF_LABELS[tf]}): brak danych`); continue; }
          const fmt = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 4 });
          lines.push(
            `  ${tf.padEnd(4)} | ${TF_LABELS[tf]}` +
            ` | O=${fmt(d.open)}  H=${fmt(d.high)}  L=${fmt(d.low)}  C=${fmt(d.close)}` +
            ` | zmiana: ${d.changePct >= 0 ? '+' : ''}${d.changePct.toFixed(2)}%` +
            ` (${d.points} świec)`
          );
        }
      }
    } else {
      lines.push('');
      lines.push('Aktualnie wybrany instrument: brak (użytkownik nie otworzył żadnego wykresu).');
      lines.push('Możesz odpowiadać na ogólne pytania o rynki lub poprosić o wybranie instrumentu z listy po lewej.');
    }

    // Wszystkie obserwowane instrumenty
    if (instruments.length > 0) {
      lines.push('');
      lines.push('Obserwowane instrumenty:');
      for (const inst of instruments) {
        let row = `  ${inst.name} (${inst.symbol}): ${
          inst.price != null
            ? inst.price.toLocaleString('en-US', { maximumFractionDigits: 4 })
            : 'N/A'
        }`;
        if (inst.change_pct != null)
          row += ` (${inst.change_pct >= 0 ? '+' : ''}${inst.change_pct.toFixed(2)}%)`;
        if (inst.error) row += ` [błąd: ${inst.error}]`;
        lines.push(row);
      }
    }

    if (positions.length > 0) {
      lines.push('');
      lines.push('Portfel użytkownika:');
      for (const p of positions) {
        lines.push(
          `  ${p.name} (${p.symbol}): ${p.quantity} szt. @ ${p.buy_price} ${p.buy_currency} [${p.tab_type}]`
        );
      }
    }

    if (latestAnalysis) {
      lines.push('');
      lines.push('Ostatnia analiza AI (fragment):');
      lines.push(latestAnalysis.substring(0, 2500));
    }

    const highImpact = calendarEvents.filter((e) => e.impact_raw === 'High');
    const medImpact = calendarEvents.filter((e) => e.impact_raw === 'Medium');
    const calFiltered = [...highImpact, ...medImpact];
    if (calFiltered.length > 0) {
      lines.push('');
      lines.push(`=== KALENDARZ MAKROEKONOMICZNY (najbliższe 7 dni, wpływ Wysoki/Średni) ===`);
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
        if (e.significance && e.significance !== 'Dane makroekonomiczne') {
          lines.push(`         → ${e.significance}`);
        }
      }
    }

    return lines.join('\n');
  };

  const exportMessagePDF = (htmlContent: string) => {
    const win = window.open('', '_blank');
    if (!win) return;
    const date = new Date().toLocaleString('pl-PL', { timeZone: APP_TIMEZONE });
    const instrLabel = selected ? `${selected.name} (${selected.symbol})` : 'Wykresy';
    win.document.write(`<!DOCTYPE html><html><head>
      <meta charset="utf-8">
      <title>Chat AI \u2013 ${instrLabel} \u2013 ${date}</title>
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
      <div class="meta">Chat \u2014 ${instrLabel} &bull; ${date}</div>
      ${htmlContent}
    </body></html>`);
    win.document.close();
    win.focus();
    setTimeout(() => win.print(), 400);
  };

  const sendChat = async () => {
    if (!chatInput.trim() || chatLoading) return;
    const userMsg: ChatMessage = { role: 'user', content: chatInput.trim() };
    const next = [...chatMessages, userMsg];
    setChatMessages(next);
    setChatInput('');
    setChatLoading(true);
    try {
      const { reply } = await sendMessage(next, buildSystemPrompt(), 'charts_chat');
      setChatMessages([...next, { role: 'assistant', content: reply }]);
    } catch {
      setChatMessages([...next, { role: 'assistant', content: 'Błąd komunikacji.' }]);
    } finally {
      setChatLoading(false);
    }
  };

  const getFxRate = (currency: string): number => {
    if (currency === 'USD') return 1;
    if (currency === 'PLN') return instruments.find((i) => i.symbol === 'USDPLN=X')?.price ?? 4.0;
    if (currency === 'EUR') {
      const eurusd = instruments.find((i) => i.symbol === 'EURUSD=X')?.price;
      return eurusd ? 1 / eurusd : 0.92;
    }
    return 1;
  };

  const openPortModal = (inst: InstrumentData, tabType: string) => {
    setPortCtx(null);
    const basePrice = inst.price ?? 0;
    setPortForm({ quantity: '', price: basePrice > 0 ? basePrice.toFixed(4) : '', currency: 'USD' });
    setPortModal({ inst, tabType, basePriceUSD: basePrice });
  };

  const submitPortForm = async () => {
    if (!portModal || portAdding) return;
    const qty = parseFloat(portForm.quantity);
    const price = parseFloat(portForm.price);
    if (isNaN(qty) || qty <= 0 || isNaN(price) || price <= 0) return;
    setPortAdding(true);
    try {
      await addPosition({ symbol: portModal.inst.symbol, name: portModal.inst.name, quantity: qty, buy_price: price, buy_currency: portForm.currency, tab_type: portModal.tabType });
      setPortModal(null);
      setPortForm({ quantity: '', price: '', currency: 'USD' });
    } finally { setPortAdding(false); }
  };

  if (loading) {
    return <div className="text-[var(--overlay)] text-center py-12">Ładowanie...</div>;
  }

  return (
    <div className="absolute inset-0 flex flex-col md:flex-row overflow-hidden">

      {/* ── Mobile tab bar ──────────────────────────────────── */}
      <div className="md:hidden flex border-b border-[var(--gray)] bg-[var(--bg2)] flex-shrink-0">
        {(['instruments', 'chart', 'chat'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setMobilePanel(tab)}
            className={`flex-1 px-3 py-2 text-xs font-bold uppercase tracking-widest transition-colors ${
              mobilePanel === tab
                ? 'text-[var(--accent)] border-b-2 border-[var(--accent)]'
                : 'text-[var(--overlay)]'
            }`}
          >
            {tab === 'instruments' ? 'Instrumenty' : tab === 'chart' ? 'Wykres' : 'Chat'}
          </button>
        ))}
      </div>

      {/* ── Lista instrumentów (kafelki jak na Dashboard) ───── */}
      <div className={`${mobilePanel === 'instruments' ? 'flex' : 'hidden'} md:flex w-full flex-1 md:flex-initial md:w-64 flex-shrink-0 border-r border-[var(--gray)] flex-col bg-[var(--bg)] overflow-hidden min-h-0`}>
        <div className="px-3 py-2 border-b border-[var(--gray)] flex-shrink-0 bg-[var(--bg2)]">
          <input
            value={instSearch}
            onChange={(e) => setInstSearch(e.target.value)}
            placeholder="Szukaj instrumentu..."
            className="w-full bg-[var(--bg)] border border-[var(--gray)] rounded-lg px-2.5 py-1.5 text-xs text-[var(--fg)] placeholder-[var(--overlay)] focus:border-[var(--accent)] outline-none transition-colors"
          />
        </div>
        <div className="flex-1 overflow-y-auto p-3 min-h-0 space-y-2">
          {orderedInstruments
            .filter((inst) => {
              const q = instSearch.trim().toLowerCase();
              if (!q) return true;
              return (
                inst.symbol.toLowerCase().includes(q) ||
                inst.name.toLowerCase().includes(q)
              );
            })
            .map((inst) => (
              <div
                key={inst.symbol}
                onContextMenu={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  const x = Math.min(e.clientX, window.innerWidth - 215);
                  const y = Math.min(e.clientY, window.innerHeight - 115);
                  setPortCtx({ x, y, inst });
                }}
              >
                <InstCard
                  data={inst}
                  selected={selected?.symbol === inst.symbol}
                  onClick={() => handleSelect(inst)}
                  flash={flashMap[inst.symbol]}
                />
              </div>
            ))}
        </div>
      </div>

      {/* ── Obszar wykresu ────────────────────────────────────── */}
      <div className={`${mobilePanel === 'chart' ? 'flex' : 'hidden'} md:flex flex-1 flex-col overflow-hidden min-w-0 min-h-0 border-r border-[var(--gray)]`}>
        {selected ? (
          <>
            {/* Nagłówek */}
            <div className="flex items-center gap-2 md:gap-3 px-3 md:px-5 py-2 md:py-3 border-b border-[var(--gray)] bg-[var(--bg2)] flex-shrink-0 flex-wrap">
              <div className="flex-1 min-w-0 flex items-baseline gap-1.5 sm:gap-2">
                <span className="font-bold text-sm sm:text-base truncate">{selected.name}</span>
                {getInstrumentUnit(selected.symbol, selected.source) && (
                  <span className="text-[10px] sm:text-xs font-mono text-[var(--overlay)] opacity-80 flex-shrink-0">{getInstrumentUnit(selected.symbol, selected.source)}</span>
                )}
                <span className="text-xs sm:text-sm text-[var(--overlay)] font-mono flex-shrink-0">{selected.symbol}</span>
              </div>
              {selected.price != null && (
                <span className="font-bold font-mono tabular-nums text-sm sm:text-base">
                  {selected.price.toLocaleString('en-US', {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 4,
                  })}
                </span>
              )}
              {selected.change_pct != null && (
                <span
                  className={`text-xs sm:text-sm font-bold px-1.5 sm:px-2 py-0.5 rounded-md ${
                    selected.change_pct >= 0
                      ? 'bg-[#a6e3a1]/15 text-[#a6e3a1]'
                      : 'bg-[#f38ba8]/15 text-[#f38ba8]'
                  }`}
                >
                  {selected.change_pct >= 0 ? '+' : ''}
                  {selected.change_pct.toFixed(2)}%
                </span>
              )}
              <button
                onClick={() => selected && openPortModal(selected, 'zakupione')}
                className="flex items-center gap-1.5 px-2 sm:px-3 py-1.5 rounded-lg bg-[var(--accent)]/15 border border-[var(--accent)]/50 text-xs font-semibold text-[var(--accent)] hover:bg-[var(--accent)]/25 transition-colors flex-shrink-0"
                title="Dodaj do portfela"
              >
                <span className="hidden sm:inline">+ Dodaj do portfela</span>
                <span className="sm:hidden">+ Portfel</span>
              </button>
              {tfLoading && (
                <span className="text-xs text-[var(--overlay)] animate-pulse ml-1">
                  Pobieranie interwałów...
                </span>
              )}
            </div>

            {/* Wykres + statystyki + profil */}
            <div className="flex-1 overflow-y-auto px-3 sm:px-5 py-3 sm:py-4 min-h-0 space-y-3 sm:space-y-4">
              <PriceChart
                symbol={selected.symbol}
                source={selected.source}
                sparkline={selected.sparkline}
                height={340}
              />

              {/* ── Panel statystyk (wzór: Stooq) ─────────────── */}
              {(() => {
                const unit = getInstrumentUnit(selected.symbol, selected.source) || '';
                const fmt = (n: number | null | undefined) =>
                  n != null ? n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 4 }) : '—';
                const fmtVol = (n: number | null | undefined) => {
                  if (n == null || n === 0) return '—';
                  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(2)}B`;
                  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
                  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
                  return n.toLocaleString('en-US');
                };
                const tf5m = tfData['5m'];
                const tf24h = tfData['24h'];
                const tf72h = tfData['72h'];
                const change = selected.change;
                const changePct = selected.change_pct;
                const isUp = (changePct ?? 0) >= 0;
                const changeColor = isUp ? 'text-[var(--green)]' : 'text-[var(--red)]';

                const StatCell = ({ label, value, sub, color }: { label: string; value: string; sub?: string; color?: string }) => (
                  <div className="flex flex-col min-w-0">
                    <span className="text-[9px] sm:text-[10px] text-[var(--overlay)] uppercase tracking-wider leading-none mb-1 truncate">{label}</span>
                    <span className={`text-xs sm:text-sm font-mono font-semibold tabular-nums truncate ${color || 'text-[var(--fg)]'}`}>{value}</span>
                    {sub && <span className={`text-[9px] sm:text-[10px] font-mono truncate ${color || 'text-[var(--overlay)]'}`}>{sub}</span>}
                  </div>
                );

                return (
                  <div className="rounded-xl border border-[var(--gray)] bg-[var(--bg2)] p-2.5 sm:p-3">
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-x-3 sm:gap-x-4 gap-y-2.5 sm:gap-y-3">
                      <StatCell
                        label="Zmiana"
                        value={change != null ? `${isUp ? '+' : ''}${fmt(change)}` : '—'}
                        sub={changePct != null ? `(${isUp ? '+' : ''}${changePct.toFixed(2)}%)` : undefined}
                        color={change != null ? changeColor : undefined}
                      />
                      <StatCell
                        label="Otwarcie"
                        value={fmt(tf5m?.open)}
                      />
                      <StatCell
                        label="Max / Min (dziś)"
                        value={tf5m ? `${fmt(tf5m.high)} / ${fmt(tf5m.low)}` : '—'}
                      />
                      <StatCell
                        label="Max / Min (5d)"
                        value={selected.high_5d != null ? `${fmt(selected.high_5d)} / ${fmt(selected.low_5d)}` : '—'}
                      />
                      <StatCell
                        label="Wolumen"
                        value={fmtVol(selected.volume)}
                      />
                      {tf24h && tf24h.points > 1 && (
                        <StatCell
                          label="Zmiana (60d)"
                          value={`${tf24h.changePct >= 0 ? '+' : ''}${tf24h.changePct.toFixed(2)}%`}
                          color={tf24h.changePct >= 0 ? 'text-[var(--green)]' : 'text-[var(--red)]'}
                        />
                      )}
                      {tf72h && tf72h.points > 1 && (
                        <StatCell
                          label="Zmiana (1r)"
                          value={`${tf72h.changePct >= 0 ? '+' : ''}${tf72h.changePct.toFixed(2)}%`}
                          sub={`${fmt(tf72h.low)} – ${fmt(tf72h.high)}`}
                          color={tf72h.changePct >= 0 ? 'text-[var(--green)]' : 'text-[var(--red)]'}
                        />
                      )}
                    </div>
                    {unit && (
                      <div className="mt-2 text-[10px] text-[var(--overlay)] text-right">{unit}</div>
                    )}
                  </div>
                );
              })()}

              <InstrumentProfilePanel
                symbol={selected.symbol}
                name={selected.name}
                systemPrompt={instrumentProfilePrompt}
              />
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-[var(--overlay)]">
            Wybierz instrument z listy.
          </div>
        )}
      </div>

      {/* ── Panel chatu ──────────────────────────────────────── */}
      <div className={`${mobilePanel === 'chat' ? 'flex' : 'hidden'} md:flex w-full flex-1 md:flex-initial md:w-[340px] flex-shrink-0 flex-col bg-[var(--bg)] overflow-hidden min-h-0`}>
        {/* Nagłówek chatu */}
        <div
          className="px-4 py-2.5 border-b border-[var(--gray)] flex-shrink-0 bg-[var(--bg2)] cursor-pointer hover:bg-[var(--gray)]/30 transition-colors select-none"
          onClick={() => setChatCtxOpen((v) => !v)}
          title="Kliknij aby zobaczyć pełny kontekst wysyłany do AI"
        >
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold text-[var(--fg)] uppercase tracking-widest">
              Chat z kontekstem rynkowym
            </p>
            <span className="text-[var(--overlay)] text-[10px]">{chatCtxOpen ? '▲' : '▼'} kontekst</span>
          </div>
          {selected && (
            <p className="text-xs text-[var(--accent)] mt-0.5 truncate">
              {selected.name}
              {Object.keys(tfData).length > 0
                ? ` + ${Object.keys(tfData).length} interwałów`
                : ''}
              {positions.length > 0 && ` + ${positions.length} pozycji`}
              {latestAnalysis && ' + analiza AI'}
              {calendarEvents.filter((e) => e.impact_raw === 'High' || e.impact_raw === 'Medium').length > 0
                && ` + 📅 ${calendarEvents.filter((e) => e.impact_raw === 'High' || e.impact_raw === 'Medium').length} wydarzeń makro`}
            </p>
          )}
        </div>

        {/* Rozwinięty panel kontekstu */}
        {chatCtxOpen && (
          <div className="border-b border-[var(--gray)] bg-[var(--bg2)] flex-shrink-0 max-h-60 overflow-y-auto">
            <p className="px-4 pt-3 pb-1 text-xs font-semibold text-[var(--fg)]/60 uppercase tracking-wide">
              Kontekst wysyłany do AI:
            </p>
            <pre className="px-4 pb-3 text-xs font-mono text-[var(--fg)]/75 whitespace-pre-wrap leading-relaxed">
              {buildContextOnly()}
            </pre>
          </div>
        )}

        {/* Wiadomości */}
        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2 min-h-0">
          {chatMessages.length > 0 && (
            <div className="flex justify-center mb-1">
              <button
                onClick={clearMessages}
                className="flex items-center gap-1.5 px-3 py-1 rounded-lg border border-[var(--gray)] text-[10px] font-medium text-[var(--overlay)] hover:text-[var(--red)] hover:border-[var(--red)]/40 hover:bg-[var(--red)]/5 transition-colors"
              >
                Wyczyść rozmowę
              </button>
            </div>
          )}
          {chatMessages.length === 0 && (
            <div className="text-center py-8 space-y-2">
              <p className="text-xs text-[var(--overlay)]">Chat ma dostęp do kontekstu:</p>
              <ul className="text-xs text-[var(--overlay)]/70 space-y-0.5">
                <li>&#9642; {selected?.name ?? '—'} ({selected?.symbol ?? '—'})</li>
                {Object.keys(tfData).length > 0 && (
                  <li>&#9642; Dane z {Object.keys(tfData).length} interwałów (5m–72h)</li>
                )}
                <li>&#9642; {instruments.length} obserwowanych instrumentów</li>
                {positions.length > 0 && <li>&#9642; {positions.length} pozycji portfela</li>}
                {latestAnalysis && <li>&#9642; Ostatnia analiza AI</li>}
                {calendarEvents.filter((e) => e.impact_raw === 'High' || e.impact_raw === 'Medium').length > 0 && (
                  <li>&#9642; 📅 Kalendarz makro (7 dni, {calendarEvents.filter((e) => e.impact_raw === 'High').length}🔴 {calendarEvents.filter((e) => e.impact_raw === 'Medium').length}🟡)</li>
                )}
              </ul>
              <p className="text-xs text-[var(--overlay)]/50 mt-3">
                Zadaj pytanie o wybrany instrument lub rynki.
              </p>
            </div>
          )}
          {chatMessages.map((m, i) => (
            <div
              key={i}
              className={`max-w-[92%] py-1 ${
                m.role === 'user'
                  ? 'text-[#f9e2af] ml-auto text-right font-medium'
                  : 'text-[#a6e3a1] chat-reply'
              }`}
            >
              {m.role === 'assistant' ? (
                <div
                  className={`md-content text-sm rounded-lg transition-all ${
                    selectedMsg === i
                      ? 'ring-1 ring-[var(--accent)] bg-[var(--accent)]/5 px-2 py-1'
                      : ''
                  }`}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    setContextMenu({ x: e.clientX, y: e.clientY, html: e.currentTarget.innerHTML });
                    setSelectedMsg(i);
                  }}
                >
                  <ReactMarkdown>{m.content}</ReactMarkdown>
                </div>
              ) : (
                <span className="text-sm">{m.content}</span>
              )}
            </div>
          ))}
          {chatLoading && (
            <div className="text-[#a6e3a1] text-sm animate-pulse">
              Myślę...
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input */}
        <div className="flex gap-2 px-3 py-2.5 border-t border-[var(--gray)] flex-shrink-0">
          <input
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendChat()}
            placeholder="Pytanie o wybrany instrument..."
            className="flex-1 bg-[var(--bg2)] border border-[var(--gray)] rounded-lg px-3 py-1.5 text-xs text-[var(--fg)] focus:border-[var(--accent)] outline-none transition-colors"
          />
          <button
            onClick={sendChat}
            disabled={chatLoading || !selected}
            className="px-3 py-1.5 rounded-lg bg-[var(--accent)] text-[var(--bg)] font-semibold text-xs hover:opacity-90 disabled:opacity-40 transition-opacity flex-shrink-0"
          >
            Wyślij
          </button>
        </div>
      </div>

      {/* ── Context menu: dodaj do portfela (prawy klik) ─────── */}
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

      {/* ── Modal: dodaj do portfela ────────────────────────────── */}
      {portModal && (
        <div
          className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={() => setPortModal(null)}
        >
          <div
            className="bg-[var(--bg2)] rounded-2xl border border-[var(--gray)] w-full max-w-sm shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
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
              <button onClick={() => setPortModal(null)} className="text-[var(--overlay)] hover:text-[var(--fg)] text-lg p-1 transition-colors leading-none">✕</button>
            </div>
            <div className="p-5 space-y-4">
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
                  placeholder="0.00"
                  className="w-full bg-[var(--bg)] border border-[var(--gray)] rounded-lg px-3 py-2 text-sm focus:border-[var(--accent)] outline-none transition-colors"
                />
              </div>
              <div>
                <label className="text-xs text-[var(--overlay)] block mb-1">Waluta</label>
                <div className="flex gap-2">
                  {(['USD', 'PLN', 'EUR'] as const).map((cur) => (
                    <button
                      key={cur}
                      onClick={() => {
                        if (portModal.basePriceUSD > 0) {
                          const converted = portModal.basePriceUSD * getFxRate(cur);
                          setPortForm((prev) => ({ ...prev, currency: cur, price: converted.toFixed(4) }));
                        } else {
                          setPortForm((prev) => ({ ...prev, currency: cur }));
                        }
                      }}
                      className={`flex-1 py-1.5 rounded-lg text-sm font-mono border transition-colors ${
                        portForm.currency === cur
                          ? 'border-[var(--accent)] bg-[var(--accent)]/15 text-[var(--accent)]'
                          : 'border-[var(--gray)] text-[var(--overlay)] hover:border-[var(--fg)]/30'
                      }`}
                    >{cur}</button>
                  ))}
                </div>
              </div>
            </div>
            <div className="px-5 pb-5">
              <button
                onClick={submitPortForm}
                disabled={portAdding || !portForm.quantity || !portForm.price}
                className={`w-full py-2.5 rounded-xl font-semibold text-sm transition-colors disabled:opacity-40 ${
                  portModal.tabType === 'zakupione'
                    ? 'bg-[#a6e3a1] text-[var(--bg)] hover:opacity-90'
                    : 'bg-[#f38ba8] text-[var(--bg)] hover:opacity-90'
                }`}
              >
                {portAdding ? 'Dodawanie...' : portModal.tabType === 'zakupione' ? '↑ Dodaj do Long' : '↓ Dodaj do Short'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Kontekstowe menu wiadomości ───────────────────────── */}
      {contextMenu && (
        <div
          style={{ position: 'fixed', top: contextMenu.y, left: contextMenu.x, zIndex: 9999 }}
          className="bg-[var(--bg2)] border border-[var(--accent)]/40 rounded-lg shadow-xl py-1 min-w-[160px]"
          onClick={(e) => e.stopPropagation()}
        >
          <button
            onClick={() => {
              exportMessagePDF(contextMenu.html);
              setContextMenu(null);
              setSelectedMsg(null);
            }}
            className="w-full text-left px-4 py-2 text-xs text-[var(--fg)] hover:bg-[var(--gray)] transition-colors rounded-lg"
          >
            Zapisz PDF
          </button>
        </div>
      )}
    </div>
  );
}
