import { useEffect, useRef, useState } from 'react';
import {
  createChart,
  ColorType,
  AreaSeries,
  type UTCTimestamp,
  type IChartApi,
  type ISeriesApi,
} from 'lightweight-charts';
import { getSparkline } from '../api/market';

interface PriceChartProps {
  symbol: string;
  source?: string;
  sparkline: number[];
  height?: number;
}

const TIMEFRAMES = [
  { label: '5m',  value: '5m'  },
  { label: '15m', value: '15m' },
  { label: '1h',  value: '1h'  },
  { label: '24h', value: '24h' },
  { label: '72h', value: '72h' },
];

// Sekundy między próbkami — muszą pasować do yf_interval z _SPARK_CFG w market_data.py
const INTERVAL_BY_TF: Record<string, number> = {
  '5m':  5 * 60,       // backend: yf_interval="5m"
  '15m': 15 * 60,      // backend: yf_interval="15m"
  '1h':  60 * 60,      // backend: yf_interval="1h"
  '24h': 24 * 3600,    // backend: yf_interval="1d"
  '72h': 24 * 3600,    // backend: yf_interval="1d" (1y danych z 1d świecami)
};

function buildChartData(prices: number[], intervalSeconds: number) {
  const now = Math.floor(Date.now() / 1000);
  return prices.map((value, i) => ({
    time: (now - (prices.length - 1 - i) * intervalSeconds) as UTCTimestamp,
    value,
  }));
}

function applySeriesColors(
  series: ISeriesApi<'Area'>,
  prices: number[],
) {
  const isUp = prices[prices.length - 1] >= prices[0];
  series.applyOptions({
    lineColor: isUp ? '#a6e3a1' : '#f38ba8',
    topColor: isUp ? 'rgba(166,227,161,0.22)' : 'rgba(243,139,168,0.22)',
  });
}

export default function PriceChart({
  symbol,
  source = 'yfinance',
  sparkline,
  height = 220,
}: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Area'> | null>(null);

  const [timeframe, setTimeframe] = useState('5m');
  const [loading, setLoading] = useState(true);
  const [chartError, setChartError] = useState('');

  // ── Inicjalizacja wykresu (raz po mount) ─────────────────────
  useEffect(() => {
    if (!containerRef.current) return;
    try {
      const chart = createChart(containerRef.current, {
        autoSize: true,
        layout: {
          background: { type: ColorType.Solid, color: '#181825' },
          textColor: '#cdd6f4',
        },
        grid: {
          vertLines: { color: '#313244' },
          horzLines: { color: '#313244' },
        },
        crosshair: {
          vertLine: { color: '#585b70' },
          horzLine: { color: '#585b70' },
        },
        rightPriceScale: { borderColor: '#313244' },
        timeScale: { borderColor: '#313244', timeVisible: true },
        handleScroll: true,
        handleScale: true,
      });

      const series = chart.addSeries(AreaSeries, {
        lineColor: '#a6e3a1',
        topColor: 'rgba(166,227,161,0.22)',
        bottomColor: 'rgba(0,0,0,0)',
        lineWidth: 2,
      });

      chartRef.current = chart;
      seriesRef.current = series;
    } catch (err) {
      console.error('PriceChart init error:', err);
      setChartError('Nie udało się zainicjalizować wykresu.');
    }

    return () => {
      chartRef.current?.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // ── Pobierz dane i zaktualizuj serię ─────────────────────────
  useEffect(() => {
    if (!symbol) return;

    setLoading(true);

    getSparkline(symbol, timeframe, source)
      .then((data) => {
        const prices = data.length >= 2 ? data : sparkline;
        if (prices.length < 2 || !seriesRef.current) return;

        applySeriesColors(seriesRef.current, prices);
        seriesRef.current.setData(
          buildChartData(prices, INTERVAL_BY_TF[timeframe] ?? 3600),
        );
        chartRef.current?.timeScale().fitContent();
      })
      .catch(() => {
        // Fallback na dane sparkline z initial load
        if (sparkline.length >= 2 && seriesRef.current) {
          applySeriesColors(seriesRef.current, sparkline);
          seriesRef.current.setData(
            buildChartData(sparkline, INTERVAL_BY_TF[timeframe] ?? 3600),
          );
          chartRef.current?.timeScale().fitContent();
        }
      })
      .finally(() => setLoading(false));
  }, [symbol, timeframe, source]); // eslint-disable-line react-hooks/exhaustive-deps

  if (chartError) {
    return (
      <div
        className="flex items-center justify-center text-sm text-[var(--overlay)]"
        style={{ height: `${height}px` }}
      >
        {chartError}
      </div>
    );
  }

  return (
    <div>
      {/* Przyciski timeframe */}
      <div className="flex gap-2 mb-2">
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf.value}
            onClick={() => setTimeframe(tf.value)}
            className={`px-3 py-2 sm:py-1 rounded text-xs font-medium transition-colors ${
              timeframe === tf.value
                ? 'bg-[var(--accent)] text-[var(--bg)]'
                : 'bg-[var(--gray)] text-[var(--fg)] hover:bg-[var(--overlay)]/60'
            }`}
          >
            {tf.label}
          </button>
        ))}
      </div>

      {/* Kontener wykresu + overlay loadingu */}
      <div ref={containerRef} style={{ height: `${height}px` }} className="w-full relative rounded overflow-hidden">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#181825]/70 z-10">
            <span className="text-xs text-[var(--overlay)] animate-pulse">Ładowanie...</span>
          </div>
        )}
      </div>
    </div>
  );
}
