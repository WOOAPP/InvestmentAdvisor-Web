import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { getReports, getReport, type ReportSummary, type ReportDetail } from '../api/reports';
import { APP_TIMEZONE } from '../config';

export default function History() {
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [selected, setSelected] = useState<ReportDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getReports().then((data) => {
      setReports(data);
      setLoading(false);
    });
  }, []);

  const openReport = async (id: number) => {
    const data = await getReport(id);
    setSelected(data);
  };

  if (selected) {
    return (
      <div>
        <button
          onClick={() => setSelected(null)}
          className="mb-4 px-3 py-1 rounded bg-[var(--gray)] hover:bg-[var(--overlay)] transition-colors text-sm"
        >
          Wstecz
        </button>
        <div className="bg-[var(--bg2)] rounded-lg p-6 border border-[var(--gray)]">
          <div className="flex justify-between items-center mb-4">
            <div>
              <span className="text-[var(--overlay)] text-sm">
                {new Date(selected.created_at).toLocaleString('pl-PL', { timeZone: APP_TIMEZONE })}
              </span>
              <span className="ml-3 text-sm text-[var(--accent)]">
                {selected.provider} / {selected.model}
              </span>
            </div>
            <div className="text-sm text-[var(--overlay)]">
              Ryzyko: {selected.risk_level}/10 &nbsp;|&nbsp; Tokeny: {selected.input_tokens} in / {selected.output_tokens} out
            </div>
          </div>
          <div className="prose prose-invert max-w-none">
            <ReactMarkdown>{selected.analysis || ''}</ReactMarkdown>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Historia raportow</h1>
      {loading ? (
        <div className="text-[var(--overlay)] text-center py-12">Ladowanie...</div>
      ) : reports.length === 0 ? (
        <div className="text-[var(--overlay)] text-center py-12">
          Brak raportow. Uruchom analize z Dashboardu.
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {reports.map((r) => (
            <button
              key={r.id}
              onClick={() => openReport(r.id)}
              className="bg-[var(--bg2)] rounded-lg p-4 border border-[var(--gray)] hover:border-[var(--accent)] transition-colors text-left w-full"
            >
              <div className="flex justify-between items-center">
                <span className="text-sm text-[var(--overlay)]">
                  {new Date(r.created_at).toLocaleString('pl-PL', { timeZone: APP_TIMEZONE })}
                </span>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-[var(--overlay)]">Ryzyko: {r.risk_level}/10</span>
                  <span className="text-sm text-[var(--accent)]">
                    {r.provider} / {r.model}
                  </span>
                </div>
              </div>
              <div className="mt-2 text-sm text-[var(--fg)] line-clamp-2">{r.preview}</div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
