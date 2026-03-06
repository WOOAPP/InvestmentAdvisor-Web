import { useEffect, useRef, useState } from 'react';
import { getPositions, addPosition as apiAddPosition, deletePosition as apiDeletePosition, type Position } from '../api/portfolio';
import { getPrices, getInstruments, getInstrumentUnit, type InstrumentData } from '../api/market';
import InstrumentSearch from '../components/InstrumentSearch';
import { APP_TIMEZONE } from '../config';

const TABS = [
  { key: 'zakupione', label: 'Long' },
  { key: 'short', label: 'Short' },
];

// ─── Sparkline (identyczna jak na Dashboard) ─────────────────
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

// ─── Forex Card (taki sam styl jak InstCard na Dashboard) ────
function ForexCard({ data }: { data: InstrumentData }) {
  const isUp = (data.change_pct ?? 0) >= 0;
  const pct = data.change_pct;
  const color = isUp ? 'text-[#a6e3a1]' : 'text-[#f38ba8]';
  const unit = getInstrumentUnit(data.symbol, data.source);
  return (
    <div className="rounded-xl p-3 border border-[var(--gray)] bg-[var(--bg2)] hover:border-[var(--accent)]/50 transition-all select-none">
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
      <div className="text-xl font-bold font-mono mt-1.5 tabular-nums">
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

export default function Portfolio() {
  const [activeTab, setActiveTab] = useState('zakupione');
  const [positions, setPositions] = useState<Position[]>([]);
  const [prices, setPrices] = useState<Record<string, number | null>>({});
  const [priceOverrides, setPriceOverrides] = useState<Record<number, number>>({});
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingValue, setEditingValue] = useState('');
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ symbol: '', name: '', quantity: '', buy_price: '', buy_currency: 'USD' });
  // przechowuje ostatnio pobraną cenę w USD i kursy FX (dla przeliczania przy zmianie waluty)
  const formPriceUsdRef = useRef<number | null>(null);
  const fxRatesRef = useRef<{ PLN: number; EUR: number }>({ PLN: 1, EUR: 1 });

  // Aktualne kursy FX (USD → inna waluta)
  const [fxRates, setFxRates] = useState<Record<string, number>>({});

  // Forex instruments for bottom tiles
  const [forexInstruments, setForexInstruments] = useState<InstrumentData[]>([]);

  // Synchronizuj fxRatesRef z fxRates (formularz zawsze ma aktualne kursy)
  useEffect(() => {
    if (fxRates['PLN']) fxRatesRef.current.PLN = fxRates['PLN'];
    if (fxRates['EUR']) fxRatesRef.current.EUR = fxRates['EUR'];
  }, [fxRates]);

  const fetchFxRates = async (): Promise<Record<string, number>> => {
    const result = await getPrices(['USDPLN=X', 'EURUSD=X']);
    const rates: Record<string, number> = {};
    if (result['USDPLN=X']) rates['PLN'] = result['USDPLN=X'];
    if (result['EURUSD=X']) rates['EUR'] = 1 / result['EURUSD=X'];
    setFxRates(rates);
    return rates;
  };

  const fetchPositions = async () => {
    setLoading(true);
    const data = await getPositions(activeTab);
    setPositions(data);
    if (data.length > 0) {
      const symbols = [...new Set(data.map((p) => p.symbol))];
      // Zawsze pobieramy kursy FX
      const priceMap = await getPrices([...symbols, 'USDPLN=X', 'EURUSD=X']);
      setPrices(priceMap);
      const rates: Record<string, number> = {};
      const usdpln = priceMap['USDPLN=X'];
      const eurusd = priceMap['EURUSD=X'];
      if (usdpln) rates['PLN'] = usdpln;
      if (eurusd) rates['EUR'] = 1 / eurusd;
      setFxRates(rates);
    } else {
      setPrices({});
      // Pobierz kursy FX nawet bez pozycji (dla formularza)
      fetchFxRates();
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchPositions();
  }, [activeTab]);

  // Pobierz instrumenty forex na kafelki (+ odśwież po zmianie w Ustawieniach)
  const fetchForex = () => {
    getInstruments().then((all) => {
      setForexInstruments(all.filter((i) => /^[A-Z]{3}[A-Z]{3}=X$/.test(i.symbol)));
    }).catch(() => {});
  };

  useEffect(() => {
    fetchForex();
    window.addEventListener('instruments-changed', fetchForex);
    return () => window.removeEventListener('instruments-changed', fetchForex);
  }, []);

  const addPosition = async (e: React.FormEvent) => {
    e.preventDefault();
    await apiAddPosition({
      symbol: form.symbol,
      name: form.name || form.symbol,
      quantity: parseFloat(form.quantity),
      buy_price: parseFloat(form.buy_price),
      buy_currency: form.buy_currency,
      tab_type: activeTab,
    });
    setShowForm(false);
    setForm({ symbol: '', name: '', quantity: '', buy_price: '', buy_currency: 'USD' });
    fetchPositions();
  };

  const deletePosition = async (id: number) => {
    await apiDeletePosition(id);
    fetchPositions();
  };

  const startEditPrice = (id: number, current: number | null) => {
    setEditingId(id);
    setEditingValue(current !== null ? String(current) : '');
  };

  const commitEditPrice = (id: number) => {
    const val = parseFloat(editingValue);
    if (!isNaN(val) && val > 0) {
      setPriceOverrides((prev) => ({ ...prev, [id]: val }));
    }
    setEditingId(null);
    setEditingValue('');
  };

  const cancelEditPrice = () => {
    setEditingId(null);
    setEditingValue('');
  };

  // Przelicza cenę USD na wybraną walutę formularza
  const convertFromUsd = (usdPrice: number, currency: string): string => {
    if (currency === 'PLN') return (usdPrice * fxRatesRef.current.PLN).toFixed(4);
    if (currency === 'EUR') return (usdPrice * fxRatesRef.current.EUR).toFixed(4);
    return usdPrice.toFixed(4);
  };

  // Wywoływane gdy user wybiera instrument — pobiera aktualną cenę
  const handleInstrumentPick = async (sym: string, nm: string) => {
    const upper = sym.toUpperCase();
    setForm((p) => ({ ...p, symbol: upper, name: nm, buy_price: '' }));
    formPriceUsdRef.current = null;
    try {
      const result = await getPrices([upper]);
      const price = result[upper];
      if (price != null) {
        formPriceUsdRef.current = price;
        setForm((p) => ({ ...p, symbol: upper, name: nm, buy_price: convertFromUsd(price, p.buy_currency) }));
      }
    } catch { /* zostaw puste pole */ }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-4 md:mb-6">
        <h1 className="text-xl md:text-2xl font-bold">Portfel</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 rounded bg-[var(--accent)] text-[var(--bg)] font-semibold text-sm"
        >
          {showForm ? 'Anuluj' : '+ Dodaj pozycje'}
        </button>
      </div>

      <div className="flex gap-1 mb-4 md:mb-6">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            className={`px-4 py-2 rounded text-sm transition-colors ${
              activeTab === t.key
                ? 'bg-[var(--accent)] text-[var(--bg)]'
                : 'bg-[var(--gray)] text-[var(--fg)] hover:bg-[var(--overlay)]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {showForm && (
        <form onSubmit={addPosition} className="bg-[var(--bg2)] rounded-lg p-3 md:p-4 border border-[var(--gray)] mb-4 md:mb-6 flex flex-wrap gap-2 md:gap-3 items-end">
          <InstrumentSearch
            symbol={form.symbol}
            name={form.name}
            onSymbol={(v) => { formPriceUsdRef.current = null; setForm((p) => ({ ...p, symbol: v.toUpperCase() })); }}
            onName={(v) => setForm((p) => ({ ...p, name: v }))}
            onPick={handleInstrumentPick}
            symbolPlaceholder="Symbol"
            namePlaceholder="Nazwa"
            inputClassName="bg-[var(--bg)] border border-[var(--gray)] rounded px-3 py-2 text-sm focus:border-[var(--accent)] outline-none transition-colors"
            symbolWrapClassName="w-full sm:w-32"
            nameWrapClassName="w-full sm:w-40"
          />
          <input placeholder="Ilosc" type="number" step="any" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} required
            className="bg-[var(--bg)] border border-[var(--gray)] rounded px-3 py-2 text-sm w-full sm:w-28" />
          <div className="relative">
            <input placeholder="Cena kupna" type="number" step="any" value={form.buy_price} onChange={(e) => setForm({ ...form, buy_price: e.target.value })} required
              className="bg-[var(--bg)] border border-[var(--gray)] rounded px-3 py-2 text-sm w-32 pr-16" />
            {formPriceUsdRef.current != null && (
              <button
                type="button"
                onClick={() => setForm((p) => ({ ...p, buy_price: convertFromUsd(formPriceUsdRef.current!, p.buy_currency) }))}
                className="absolute right-1 top-1/2 -translate-y-1/2 text-[10px] px-1.5 py-0.5 rounded border border-[var(--accent)]/50 bg-[var(--accent)]/10 text-[var(--accent)] hover:bg-[var(--accent)]/20 transition-colors font-mono"
                title={`Aktualna cena: $${formPriceUsdRef.current.toLocaleString('en-US', { maximumFractionDigits: 4 })}`}
              >Aktualna</button>
            )}
          </div>
          <select
            value={form.buy_currency}
            onChange={(e) => {
              const currency = e.target.value;
              setForm((p) => ({
                ...p,
                buy_currency: currency,
                buy_price: formPriceUsdRef.current != null ? convertFromUsd(formPriceUsdRef.current, currency) : p.buy_price,
              }));
            }}
            className="bg-[var(--bg)] border border-[var(--gray)] rounded px-3 py-2 text-sm">
            <option value="USD">USD</option><option value="PLN">PLN</option><option value="EUR">EUR</option>
          </select>
          <button type="submit" className="px-4 py-2 rounded bg-[var(--green)] text-[var(--bg)] font-semibold text-sm">Dodaj</button>
        </form>
      )}

      {loading ? (
        <div className="text-[var(--overlay)] text-center py-8">Ladowanie...</div>
      ) : positions.length === 0 ? (
        <div className="text-[var(--overlay)] text-center py-8">Brak pozycji w tej zakladce.</div>
      ) : (
        <div className="overflow-x-auto -mx-3 px-3 md:mx-0 md:px-0">
        <table className="w-full text-sm min-w-[700px]">
          <thead>
            <tr className="text-[var(--overlay)] border-b border-[var(--gray)]">
              <th className="text-left py-2 pr-3">Data dodania</th>
              <th className="text-left">Symbol</th><th className="text-left">Nazwa</th>
              <th className="text-right">Ilosc</th><th className="text-right">Cena kupna</th>
              <th className="text-right">Wartosc</th>
              <th className="text-right">Akt. cena</th>
              <th className="text-right">Bilans</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => {
              // override ma pierwszeństwo nad ceną z API
              const currentPrice = priceOverrides[p.id] ?? prices[p.symbol] ?? null;
              const isOverridden = p.id in priceOverrides;
              const costUsd = p.buy_price_usd * p.quantity;
              let balance: number | null = null;
              if (currentPrice !== null) {
                if (activeTab === 'short') {
                  balance = (p.buy_price_usd - currentPrice) * p.quantity;
                } else {
                  balance = (currentPrice - p.buy_price_usd) * p.quantity;
                }
              }
              const balanceColor =
                balance === null ? '' : balance >= 0 ? 'text-[var(--green)]' : 'text-[var(--red)]';
              const dateStr = new Date(p.created_at).toLocaleDateString('pl-PL', { timeZone: APP_TIMEZONE });
              const hasAltCurrency = p.buy_currency !== 'USD';
              const altRate = hasAltCurrency ? fxRates[p.buy_currency] : null;
              const toAlt = (usd: number) => altRate ? usd * altRate : null;
              return (
                <tr key={p.id} className="border-b border-[var(--gray)] hover:bg-[var(--gray)]/30">
                  <td className="py-2 pr-3 text-[var(--overlay)] text-xs whitespace-nowrap">{dateStr}</td>
                  <td className="font-mono">{p.symbol}</td><td>{p.name}</td>
                  <td className="text-right">{p.quantity}</td>
                  <td className="text-right">
                    <div>{p.buy_price_usd.toFixed(2)} <span className="text-[var(--overlay)] text-xs">USD</span></div>
                    {hasAltCurrency && (
                      <div className="text-[var(--overlay)] text-xs">{p.buy_price.toFixed(2)} {p.buy_currency}</div>
                    )}
                  </td>
                  <td className="text-right">
                    <div>{costUsd.toFixed(2)} <span className="text-[var(--overlay)] text-xs">USD</span></div>
                    {hasAltCurrency && (
                      <div className="text-[var(--overlay)] text-xs">{(p.buy_price * p.quantity).toFixed(2)} {p.buy_currency}</div>
                    )}
                  </td>
                  <td className="text-right">
                    {editingId === p.id ? (
                      <span className="inline-flex items-center gap-1 justify-end">
                        <input
                          type="number"
                          step="any"
                          autoFocus
                          value={editingValue}
                          onChange={(e) => setEditingValue(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') commitEditPrice(p.id);
                            if (e.key === 'Escape') cancelEditPrice();
                          }}
                          className="w-24 bg-[var(--bg)] border border-[var(--accent)] rounded px-2 py-0.5 text-sm text-right outline-none"
                        />
                        <button onClick={() => commitEditPrice(p.id)} className="text-[var(--green)] hover:opacity-80 text-xs font-bold">✓</button>
                        <button onClick={cancelEditPrice} className="text-[var(--overlay)] hover:opacity-80 text-xs">✕</button>
                      </span>
                    ) : (
                      <span className="inline-flex flex-col items-end group">
                        <span className="inline-flex items-center gap-1">
                          {currentPrice !== null
                            ? <>{currentPrice.toFixed(2)} <span className={`text-xs ${isOverridden ? 'text-[var(--yellow)]' : 'text-[var(--overlay)]'}`}>USD{isOverridden ? '*' : ''}</span></>
                            : <span className="text-[var(--overlay)]">—</span>}
                          <button
                            onClick={() => startEditPrice(p.id, currentPrice)}
                            className="opacity-0 group-hover:opacity-100 text-[var(--overlay)] hover:text-[var(--accent)] transition-opacity text-xs ml-1"
                            title="Ustaw cenę ręcznie"
                          >✏</button>
                        </span>
                        {hasAltCurrency && currentPrice !== null && toAlt(currentPrice) !== null && (
                          <span className="text-[var(--overlay)] text-xs">{toAlt(currentPrice)!.toFixed(2)} {p.buy_currency}</span>
                        )}
                      </span>
                    )}
                  </td>
                  <td className={`text-right font-semibold ${balanceColor}`}>
                    {balance !== null ? (
                      <div>
                        <div>{balance >= 0 ? '+' : ''}{balance.toFixed(2)} <span className="text-[var(--overlay)] text-xs font-normal">USD</span></div>
                        {hasAltCurrency && toAlt(balance) !== null && (
                          <div className="text-xs font-normal text-[var(--overlay)]">{balance >= 0 ? '+' : ''}{toAlt(balance)!.toFixed(2)} {p.buy_currency}</div>
                        )}
                      </div>
                    ) : <span className="text-[var(--overlay)] font-normal">—</span>}
                  </td>
                  <td className="text-right pl-3">
                    <button onClick={() => deletePosition(p.id)} className="text-[var(--red)] hover:underline text-xs">Usun</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        </div>
      )}

      {/* ── Forex tiles ──────────────────────────────── */}
      {forexInstruments.length > 0 && (
        <div className="mt-8">
          <h2 className="text-xs font-bold text-[var(--fg)] uppercase tracking-widest mb-3">Kursy walut</h2>
          <div className="grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))' }}>
            {forexInstruments.map((inst) => (
              <ForexCard key={inst.symbol} data={inst} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
