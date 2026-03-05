import { useEffect, useState } from 'react';
import api from '../api/client';
import InstrumentCard from '../components/InstrumentCard';

interface InstrumentData {
  symbol: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  sparkline: number[];
  error: string | null;
}

export default function Dashboard() {
  const [instruments, setInstruments] = useState<InstrumentData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [analysisRunning, setAnalysisRunning] = useState(false);
  const [analysisMsg, setAnalysisMsg] = useState('');

  const fetchInstruments = async () => {
    try {
      const res = await api.get('/market/instruments');
      setInstruments(res.data);
      setError('');
    } catch {
      setError('Nie udalo sie pobrac danych rynkowych.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInstruments();
    const interval = setInterval(fetchInstruments, 60000);
    return () => clearInterval(interval);
  }, []);

  const runAnalysis = async () => {
    setAnalysisRunning(true);
    setAnalysisMsg('');
    try {
      await api.post('/reports/run');
      setAnalysisMsg('Analiza uruchomiona — wyniki pojawia sie w zakladce Raporty.');
    } catch {
      setAnalysisMsg('Blad uruchamiania analizy.');
    } finally {
      setAnalysisRunning(false);
    }
  };

  // Group by category based on source/symbol patterns
  const categories = {
    'Akcje / Indeksy': [] as InstrumentData[],
    'Krypto': [] as InstrumentData[],
    'Forex': [] as InstrumentData[],
    'Surowce': [] as InstrumentData[],
    'Inne': [] as InstrumentData[],
  };

  for (const inst of instruments) {
    const s = inst.symbol;
    if (s.includes('bitcoin') || s.includes('ethereum') || s.includes('BTC') || s.includes('ETH')) {
      categories['Krypto'].push(inst);
    } else if (s.includes('=X') || s.includes('PLN') || s.includes('EUR') || s.includes('DX-Y')) {
      categories['Forex'].push(inst);
    } else if (s.includes('=F')) {
      categories['Surowce'].push(inst);
    } else if (s.includes('^') || ['SPY', 'QQQ'].some((x) => s.includes(x)) || s.includes('.WA')) {
      categories['Akcje / Indeksy'].push(inst);
    } else {
      categories['Inne'].push(inst);
    }
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <div className="flex gap-3">
          <button
            onClick={fetchInstruments}
            className="px-4 py-2 rounded bg-[var(--gray)] hover:bg-[var(--overlay)] transition-colors text-sm"
          >
            Odswiez
          </button>
          <button
            onClick={runAnalysis}
            disabled={analysisRunning}
            className="px-4 py-2 rounded bg-[var(--accent)] text-[var(--bg)] font-semibold hover:opacity-90 transition-opacity text-sm disabled:opacity-50"
          >
            {analysisRunning ? 'Analizuje...' : 'Uruchom Analize'}
          </button>
        </div>
      </div>

      {analysisMsg && (
        <div className={`mb-4 px-4 py-2 rounded text-sm ${analysisMsg.includes('Blad') ? 'bg-[var(--red)]/20 text-[var(--red)]' : 'bg-[var(--green)]/20 text-[var(--green)]'}`}>
          {analysisMsg}
        </div>
      )}

      {error && (
        <div className="mb-4 px-4 py-2 rounded text-sm bg-[var(--red)]/20 text-[var(--red)]">{error}</div>
      )}

      {loading ? (
        <div className="text-[var(--overlay)] text-center py-12">Ladowanie danych rynkowych...</div>
      ) : (
        Object.entries(categories).map(
          ([cat, items]) =>
            items.length > 0 && (
              <div key={cat} className="mb-8">
                <h2 className="text-lg font-semibold text-[var(--overlay)] mb-3">{cat}</h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {items.map((inst) => (
                    <InstrumentCard key={inst.symbol} data={inst} />
                  ))}
                </div>
              </div>
            )
        )
      )}
    </div>
  );
}
