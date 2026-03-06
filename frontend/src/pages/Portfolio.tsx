import { useEffect, useRef, useState } from 'react';
import { getPositions, addPosition as apiAddPosition, deletePosition as apiDeletePosition, type Position } from '../api/portfolio';
import { getPrices } from '../api/market';
import InstrumentSearch from '../components/InstrumentSearch';
import { APP_TIMEZONE } from '../config';

const TABS = [
  { key: 'zakupione', label: 'Long' },
  { key: 'short', label: 'Short' },
];

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

  const fetchPositions = async () => {
    setLoading(true);
    const data = await getPositions(activeTab);
    setPositions(data);
    if (data.length > 0) {
      const symbols = [...new Set(data.map((p) => p.symbol))];
      const priceMap = await getPrices(symbols);
      setPrices(priceMap);
    } else {
      setPrices({});
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchPositions();
  }, [activeTab]);

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

  // Wywoływane gdy user wybiera instrument — pobiera aktualną cenę i kursy FX
  const handleInstrumentPick = async (sym: string, nm: string) => {
    const upper = sym.toUpperCase();
    setForm((p) => ({ ...p, symbol: upper, name: nm, buy_price: '' }));
    formPriceUsdRef.current = null;
    try {
      const result = await getPrices([upper, 'USDPLN=X', 'EURUSD=X']);
      const usdPln = result['USDPLN=X'];
      const eurUsd = result['EURUSD=X'];
      if (usdPln) fxRatesRef.current.PLN = usdPln;
      if (eurUsd) fxRatesRef.current.EUR = 1 / eurUsd; // EURUSD=X: 1 EUR = N USD → 1 USD = 1/N EUR
      const price = result[upper];
      if (price != null) {
        formPriceUsdRef.current = price;
        setForm((p) => ({ ...p, symbol: upper, name: nm, buy_price: convertFromUsd(price, p.buy_currency) }));
      }
    } catch { /* zostaw puste pole */ }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Portfel</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 rounded bg-[var(--accent)] text-[var(--bg)] font-semibold text-sm"
        >
          {showForm ? 'Anuluj' : '+ Dodaj pozycje'}
        </button>
      </div>

      <div className="flex gap-1 mb-6">
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
        <form onSubmit={addPosition} className="bg-[var(--bg2)] rounded-lg p-4 border border-[var(--gray)] mb-6 flex flex-wrap gap-3 items-end">
          <InstrumentSearch
            symbol={form.symbol}
            name={form.name}
            onSymbol={(v) => { formPriceUsdRef.current = null; setForm((p) => ({ ...p, symbol: v.toUpperCase() })); }}
            onName={(v) => setForm((p) => ({ ...p, name: v }))}
            onPick={handleInstrumentPick}
            symbolPlaceholder="Symbol"
            namePlaceholder="Nazwa"
            inputClassName="bg-[var(--bg)] border border-[var(--gray)] rounded px-3 py-2 text-sm focus:border-[var(--accent)] outline-none transition-colors"
            symbolWrapClassName="w-32"
            nameWrapClassName="w-40"
          />
          <input placeholder="Ilosc" type="number" step="any" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} required
            className="bg-[var(--bg)] border border-[var(--gray)] rounded px-3 py-2 text-sm w-28" />
          <input placeholder="Cena kupna" type="number" step="any" value={form.buy_price} onChange={(e) => setForm({ ...form, buy_price: e.target.value })} required
            className="bg-[var(--bg)] border border-[var(--gray)] rounded px-3 py-2 text-sm w-32" />
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
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[var(--overlay)] border-b border-[var(--gray)]">
              <th className="text-left py-2 pr-3">Data dodania</th>
              <th className="text-left">Symbol</th><th className="text-left">Nazwa</th>
              <th className="text-right">Ilosc</th><th className="text-right">Cena kupna</th>
              <th className="text-right">Waluta</th><th className="text-right">Wartosc USD</th>
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
                  // short: zysk gdy cena spada → (buy - current) * qty
                  balance = (p.buy_price_usd - currentPrice) * p.quantity;
                } else {
                  // long: zysk gdy cena rośnie → (current - buy) * qty
                  balance = (currentPrice - p.buy_price_usd) * p.quantity;
                }
              }
              const balanceColor =
                balance === null ? '' : balance >= 0 ? 'text-[var(--green)]' : 'text-[var(--red)]';
              const dateStr = new Date(p.created_at).toLocaleDateString('pl-PL', { timeZone: APP_TIMEZONE });
              return (
                <tr key={p.id} className="border-b border-[var(--gray)] hover:bg-[var(--gray)]/30">
                  <td className="py-2 pr-3 text-[var(--overlay)] text-xs whitespace-nowrap">{dateStr}</td>
                  <td className="font-mono">{p.symbol}</td><td>{p.name}</td>
                  <td className="text-right">{p.quantity}</td>
                  <td className="text-right">{p.buy_price.toFixed(2)} <span className="text-[var(--overlay)] text-xs">{p.buy_currency}</span></td>
                  <td className="text-right">{costUsd.toFixed(2)} <span className="text-[var(--overlay)] text-xs">USD</span></td>
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
                      <span className="inline-flex items-center gap-1 justify-end group">
                        {currentPrice !== null
                          ? <>{currentPrice.toFixed(2)} <span className={`text-xs ${isOverridden ? 'text-[var(--yellow)]' : 'text-[var(--overlay)]'}`}>USD{isOverridden ? '*' : ''}</span></>
                          : <span className="text-[var(--overlay)]">—</span>}
                        <button
                          onClick={() => startEditPrice(p.id, currentPrice)}
                          className="opacity-0 group-hover:opacity-100 text-[var(--overlay)] hover:text-[var(--accent)] transition-opacity text-xs ml-1"
                          title="Ustaw cenę ręcznie"
                        >✏</button>
                      </span>
                    )}
                  </td>
                  <td className={`text-right font-semibold ${balanceColor}`}>
                    {balance !== null
                      ? <>{balance >= 0 ? '+' : ''}{balance.toFixed(2)} <span className="text-[var(--overlay)] text-xs font-normal">USD</span></>
                      : <span className="text-[var(--overlay)] font-normal">—</span>}
                  </td>
                  <td className="text-right pl-3">
                    <button onClick={() => deletePosition(p.id)} className="text-[var(--red)] hover:underline text-xs">Usun</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
