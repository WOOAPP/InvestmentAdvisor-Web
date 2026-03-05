import { useEffect, useState } from 'react';
import api from '../api/client';

interface Position {
  id: number;
  symbol: string;
  name: string;
  quantity: number;
  buy_price: number;
  buy_currency: string;
  buy_price_usd: number;
  tab_type: string;
  created_at: string;
}

const TABS = [
  { key: 'obserwowane', label: 'Obserwowane' },
  { key: 'zakupione', label: 'Long' },
  { key: 'short', label: 'Short' },
];

export default function Portfolio() {
  const [activeTab, setActiveTab] = useState('zakupione');
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ symbol: '', name: '', quantity: '', buy_price: '', buy_currency: 'USD' });

  const fetchPositions = async () => {
    setLoading(true);
    const res = await api.get(`/portfolio?tab_type=${activeTab}`);
    setPositions(res.data);
    setLoading(false);
  };

  useEffect(() => {
    fetchPositions();
  }, [activeTab]);

  const addPosition = async (e: React.FormEvent) => {
    e.preventDefault();
    await api.post('/portfolio', {
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
    await api.delete(`/portfolio/${id}`);
    fetchPositions();
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
          <input placeholder="Symbol" value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value })} required
            className="bg-[var(--bg)] border border-[var(--gray)] rounded px-3 py-2 text-sm w-32" />
          <input placeholder="Nazwa" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="bg-[var(--bg)] border border-[var(--gray)] rounded px-3 py-2 text-sm w-40" />
          <input placeholder="Ilosc" type="number" step="any" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} required
            className="bg-[var(--bg)] border border-[var(--gray)] rounded px-3 py-2 text-sm w-28" />
          <input placeholder="Cena kupna" type="number" step="any" value={form.buy_price} onChange={(e) => setForm({ ...form, buy_price: e.target.value })} required
            className="bg-[var(--bg)] border border-[var(--gray)] rounded px-3 py-2 text-sm w-32" />
          <select value={form.buy_currency} onChange={(e) => setForm({ ...form, buy_currency: e.target.value })}
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
              <th className="text-left py-2">Symbol</th><th className="text-left">Nazwa</th>
              <th className="text-right">Ilosc</th><th className="text-right">Cena kupna</th>
              <th className="text-right">Waluta</th><th className="text-right">Wartosc USD</th><th></th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => (
              <tr key={p.id} className="border-b border-[var(--gray)] hover:bg-[var(--gray)]/30">
                <td className="py-2 font-mono">{p.symbol}</td><td>{p.name}</td>
                <td className="text-right">{p.quantity}</td>
                <td className="text-right">{p.buy_price.toFixed(2)}</td>
                <td className="text-right">{p.buy_currency}</td>
                <td className="text-right">{(p.buy_price_usd * p.quantity).toFixed(2)}</td>
                <td className="text-right">
                  <button onClick={() => deletePosition(p.id)} className="text-[var(--red)] hover:underline text-xs">Usun</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
