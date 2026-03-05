interface InstrumentData {
  symbol: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  sparkline: number[];
  error: string | null;
}

function MiniSparkline({ data }: { data: number[] }) {
  if (data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const h = 30;
  const w = 80;
  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * w;
      const y = h - ((v - min) / range) * h;
      return `${x},${y}`;
    })
    .join(' ');

  const isUp = data[data.length - 1] >= data[0];
  return (
    <svg width={w} height={h} className="inline-block">
      <polyline
        fill="none"
        stroke={isUp ? 'var(--green)' : 'var(--red)'}
        strokeWidth="1.5"
        points={points}
      />
    </svg>
  );
}

export default function InstrumentCard({ data }: { data: InstrumentData }) {
  if (data.error) {
    return (
      <div className="bg-[var(--bg2)] rounded-lg p-4 border border-[var(--gray)]">
        <div className="text-sm text-[var(--overlay)]">{data.name}</div>
        <div className="text-xs text-[var(--red)] mt-1">{data.error}</div>
      </div>
    );
  }

  const isUp = (data.change_pct ?? 0) >= 0;
  const color = isUp ? 'var(--green)' : 'var(--red)';
  const arrow = isUp ? '\u25B2' : '\u25BC';

  return (
    <div className="bg-[var(--bg2)] rounded-lg p-4 border border-[var(--gray)] hover:border-[var(--accent)] transition-colors">
      <div className="flex justify-between items-start">
        <div>
          <div className="text-sm text-[var(--overlay)]">{data.name}</div>
          <div className="text-xl font-semibold mt-1">
            {data.price?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 })}
          </div>
        </div>
        <MiniSparkline data={data.sparkline} />
      </div>
      <div className="mt-2 text-sm" style={{ color }}>
        {arrow} {data.change_pct !== null ? `${data.change_pct >= 0 ? '+' : ''}${data.change_pct.toFixed(2)}%` : '--'}
      </div>
    </div>
  );
}
