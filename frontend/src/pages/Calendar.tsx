import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { getCalendar, analyzeCalendarEvent, type CalendarEvent } from '../api/calendar';
import { APP_TIMEZONE } from '../config';

const CACHE_KEY = 'cal_analyses_v1';

function loadCache(): Record<string, string> {
  try { return JSON.parse(localStorage.getItem(CACHE_KEY) || '{}'); } catch { return {}; }
}

function saveCache(cache: Record<string, string>): void {
  try { localStorage.setItem(CACHE_KEY, JSON.stringify(cache)); } catch { /* quota */ }
}

function eventKey(ev: CalendarEvent): string {
  return `${ev.date}|${ev.country}|${ev.event}`;
}

const IMPACT_COLORS: Record<string, string> = {
  High:    'bg-[#f38ba8]/20 text-[#f38ba8] border border-[#f38ba8]/40',
  Medium:  'bg-[#f9e2af]/20 text-[#f9e2af] border border-[#f9e2af]/40',
  Low:     'bg-[var(--gray)] text-[var(--overlay)] border border-[var(--gray)]',
  Holiday: 'bg-[var(--accent)]/10 text-[var(--accent)] border border-[var(--accent)]/30',
};

const IMPACT_DOT: Record<string, string> = {
  High:    'bg-[#f38ba8]',
  Medium:  'bg-[#f9e2af]',
  Low:     'bg-[var(--overlay)]',
  Holiday: 'bg-[var(--accent)]',
};

type ImpactFilter = 'all' | 'High' | 'Medium';

function formatDateHeader(dateStr: string): string {
  try {
    const d = new Date(dateStr + 'T12:00:00');
    return d.toLocaleDateString('pl-PL', { weekday: 'long', day: 'numeric', month: 'long', timeZone: APP_TIMEZONE });
  } catch {
    return dateStr;
  }
}

function isToday(dateStr: string): boolean {
  const now = new Date();
  const warsawDate = now.toLocaleDateString('sv-SE', { timeZone: APP_TIMEZONE });
  return dateStr === warsawDate;
}

export default function Calendar() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<ImpactFilter>('all');
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [analyses, setAnalyses] = useState<Record<string, string>>(loadCache);
  const [analyzing, setAnalyzing] = useState<Record<string, boolean>>({});

  useEffect(() => {
    getCalendar()
      .then((res) => {
        setEvents(res.events);
        if (res.error && res.events.length === 0) setError(res.error);
      })
      .catch(() => setError('Nie udalo sie pobrac kalendarza.'))
      .finally(() => setLoading(false));
  }, []);

  const handleAnalyze = async (rowKey: string, ev: CalendarEvent) => {
    const cKey = eventKey(ev);
    if (analyses[cKey] || analyzing[rowKey]) return;
    setAnalyzing((prev) => ({ ...prev, [rowKey]: true }));
    try {
      const res = await analyzeCalendarEvent(ev);
      setAnalyses((prev) => {
        const next = { ...prev, [cKey]: res.analysis };
        saveCache(next);
        return next;
      });
    } catch {
      setAnalyses((prev) => {
        const next = { ...prev, [cKey]: 'Błąd podczas generowania analizy.' };
        saveCache(next);
        return next;
      });
    } finally {
      setAnalyzing((prev) => ({ ...prev, [rowKey]: false }));
    }
  };

  const filtered = events.filter((e) => {
    if (filter === 'all') return true;
    return e.impact_raw === filter;
  });

  // Group by date
  const grouped = filtered.reduce<Record<string, CalendarEvent[]>>((acc, e) => {
    if (!acc[e.date]) acc[e.date] = [];
    acc[e.date].push(e);
    return acc;
  }, {});
  const dates = Object.keys(grouped).sort();

  return (
    <div className="max-w-5xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4 md:mb-6">
        <h1 className="text-xl md:text-2xl font-bold">Kalendarz ekonomiczny</h1>
        <div className="flex items-center gap-1 text-xs">
          {(['all', 'High', 'Medium'] as ImpactFilter[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-lg transition-colors font-medium ${
                filter === f
                  ? 'bg-[var(--accent)] text-[var(--bg)]'
                  : 'bg-[var(--bg2)] text-[var(--overlay)] hover:text-[var(--fg)] border border-[var(--gray)]'
              }`}
            >
              {f === 'all' ? 'Wszystkie' : f === 'High' ? 'Wysokie' : 'Srednie'}
            </button>
          ))}
          <span className="ml-2 text-[var(--overlay)]">
            {filtered.length} wyd.
          </span>
        </div>
      </div>

      {loading && (
        <div className="text-[var(--overlay)] text-center py-16">Ladowanie kalendarza...</div>
      )}

      {!loading && error && (
        <div className="bg-[#f38ba8]/10 border border-[#f38ba8]/30 rounded-xl p-6 text-center">
          <p className="text-[#f38ba8] text-sm">{error}</p>
          <p className="text-[var(--overlay)] text-xs mt-1">Sprawdz polaczenie lub sprobuj pozniej.</p>
        </div>
      )}

      {!loading && !error && filtered.length === 0 && (
        <div className="bg-[var(--bg2)] rounded-xl border border-[var(--gray)] p-8 text-center">
          <p className="text-[var(--overlay)]">Brak wydarzen spelniajacych kryterium filtru.</p>
        </div>
      )}

      {!loading && dates.map((date) => (
        <div key={date} className="mb-6">
          {/* Date header */}
          <div className={`flex items-center gap-3 mb-2 ${isToday(date) ? 'text-[var(--accent)]' : 'text-[var(--fg)]'}`}>
            <span className="text-sm font-bold capitalize">{formatDateHeader(date)}</span>
            {isToday(date) && (
              <span className="text-[9px] font-bold bg-[var(--accent)] text-[var(--bg)] px-2 py-0.5 rounded-full uppercase tracking-wider">
                Dzisiaj
              </span>
            )}
            <div className="flex-1 h-px bg-[var(--gray)]" />
            <span className="text-xs text-[var(--overlay)]">{grouped[date].length} wydarzen</span>
          </div>

          {/* Events table */}
          <div className="bg-[var(--bg2)] rounded-xl border border-[var(--gray)] overflow-hidden overflow-x-auto">
            <table className="w-full text-sm min-w-[600px]">
              <thead>
                <tr className="border-b border-[var(--gray)] bg-[var(--bg)]">
                  <th className="text-left px-4 py-2 text-[10px] text-[var(--overlay)] uppercase tracking-wide font-semibold w-16">Czas</th>
                  <th className="text-left px-3 py-2 text-[10px] text-[var(--overlay)] uppercase tracking-wide font-semibold w-24">Kraj</th>
                  <th className="text-left px-3 py-2 text-[10px] text-[var(--overlay)] uppercase tracking-wide font-semibold">Wydarzenie</th>
                  <th className="text-center px-3 py-2 text-[10px] text-[var(--overlay)] uppercase tracking-wide font-semibold w-24">Waga</th>
                  <th className="text-right px-3 py-2 text-[10px] text-[var(--overlay)] uppercase tracking-wide font-semibold w-24">Prognoza</th>
                  <th className="text-right px-4 py-2 text-[10px] text-[var(--overlay)] uppercase tracking-wide font-semibold w-24">Poprzednio</th>
                </tr>
              </thead>
              <tbody>
                {grouped[date].map((ev, i) => {
                  const rowKey = `${date}-${i}`;
                  const isExpanded = expandedRow === rowKey;
                  return (
                    <>
                      <tr
                        key={rowKey}
                        onClick={() => setExpandedRow(isExpanded ? null : rowKey)}
                        className={`border-b border-[var(--gray)] last:border-0 transition-colors cursor-pointer ${
                          isExpanded ? 'bg-[var(--gray)]/30' : 'hover:bg-[var(--gray)]/20'
                        }`}
                      >
                        <td className="px-4 py-3 font-mono text-xs text-[var(--overlay)] whitespace-nowrap">
                          {ev.time || '—'}
                        </td>
                        <td className="px-3 py-3 whitespace-nowrap">
                          <span className="mr-1.5">{ev.flag}</span>
                          <span className="text-xs text-[var(--overlay)] font-mono">{ev.country}</span>
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex items-center gap-2">
                            <span
                              className={`inline-block w-1.5 h-1.5 rounded-full flex-shrink-0 ${IMPACT_DOT[ev.impact_raw] ?? 'bg-[var(--overlay)]'}`}
                            />
                            <span className="font-medium text-[var(--fg)] leading-tight">{ev.event}</span>
                          </div>
                        </td>
                        <td className="px-3 py-3 text-center">
                          <span className={`inline-block text-[10px] font-semibold px-2 py-0.5 rounded-full ${IMPACT_COLORS[ev.impact_raw] ?? ''}`}>
                            {ev.impact_icon} {ev.impact_label}
                          </span>
                        </td>
                        <td className="px-3 py-3 text-right font-mono text-xs">
                          {ev.forecast || <span className="text-[var(--overlay)]">—</span>}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-xs text-[var(--overlay)]">
                          {ev.previous || '—'}
                        </td>
                      </tr>
                      {isExpanded && (
                        <tr key={`${rowKey}-exp`} className="bg-[var(--bg)]/60 border-b border-[var(--gray)]">
                          <td colSpan={6} className="px-4 py-4 space-y-3">
                            {/* Znaczenie */}
                            <p className="text-xs text-[var(--overlay)] leading-relaxed">
                              <span className="text-[var(--accent)] font-semibold">Znaczenie: </span>
                              {ev.significance}
                            </p>

                            {/* Analiza AI */}
                            {!analyses[eventKey(ev)] && !analyzing[rowKey] && (
                              <button
                                onClick={(e) => { e.stopPropagation(); handleAnalyze(rowKey, ev); }}
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--accent)]/10 border border-[var(--accent)]/30 text-[var(--accent)] text-xs font-semibold hover:bg-[var(--accent)]/20 transition-colors"
                              >
                                <span>✦</span> Analizuj AI
                              </button>
                            )}

                            {analyzing[rowKey] && (
                              <div className="flex items-center gap-2 text-xs text-[var(--overlay)]">
                                <span className="inline-flex gap-0.5">
                                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-bounce [animation-delay:-0.3s]" />
                                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-bounce [animation-delay:-0.15s]" />
                                  <span className="w-1.5 h-1.5 rounded-full bg-[var(--accent)] animate-bounce" />
                                </span>
                                Generowanie analizy AI...
                              </div>
                            )}

                            {analyses[eventKey(ev)] && (
                              <div className="bg-[var(--bg2)] border border-[var(--accent)]/20 rounded-lg p-3">
                                <p className="text-[10px] font-semibold text-[var(--accent)] uppercase tracking-widest mb-2">Analiza AI</p>
                                <div className="md-content md-profile text-xs">
                                  <ReactMarkdown>{analyses[eventKey(ev)]}</ReactMarkdown>
                                </div>
                              </div>
                            )}
                          </td>
                        </tr>
                      )}
                    </>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
