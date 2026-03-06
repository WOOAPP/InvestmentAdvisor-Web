import api from './client';

export interface InstrumentData {
  symbol: string;
  name: string;
  price: number | null;
  change: number | null;
  change_pct: number | null;
  volume: number | null;
  high_5d: number | null;
  low_5d: number | null;
  sparkline: number[];
  source: string;
  error: string | null;
}

// ── Instruments cache (przeżywa między zakładkami) ──────────────
let _instrumentsCache: InstrumentData[] = [];
let _instrumentsCacheTime = 0;
const INSTRUMENTS_TTL = 5_000; // 5 sekund

export const getCachedInstruments = (): InstrumentData[] => _instrumentsCache;

/** Wyczyść cache — wywołaj po zmianie listy instrumentów w Ustawieniach */
export const clearInstrumentsCache = (): void => {
  _instrumentsCache = [];
  _instrumentsCacheTime = 0;
};

/**
 * Zwraca etykietę jednostki/waluty dla danego instrumentu na podstawie symbolu i źródła.
 * Używana na kafelkach w Dashboard i Wykresy.
 *
 * Przy dodawaniu nowych instrumentów sprawdź:
 * - Forex: symbol w formacie ABC DEF=X → "ABC/DEF"
 * - Kontrakty futures: =F suffix → dedykowane jednostki (oz, bbl, MMBtu…)
 * - Indeksy: symbol zaczyna się od ^ → "pts"
 * - Krypto yfinance: symbol kończy się na -USD → "USD"
 * - Stooq (GPW): source === 'stooq' → "PLN"
 * - CoinGecko: source === 'coingecko' → "USD"
 * - Domyślnie yfinance (akcje US, ETF): "USD"
 */
export function getInstrumentUnit(symbol: string, source: string): string | null {
  // Forex pairs: EURUSD=X, USDPLN=X, GBPUSD=X, etc.
  const forexMatch = symbol.match(/^([A-Z]{3})([A-Z]{3})=X$/);
  if (forexMatch) return `${forexMatch[1]}/${forexMatch[2]}`;

  // Commodity futures
  if (symbol === 'GC=F' || symbol === 'SI=F') return 'USD/oz';
  if (symbol === 'CL=F' || symbol === 'BZ=F') return 'USD/bbl';
  if (symbol === 'NG=F') return 'USD/MMBtu';
  if (symbol === 'HG=F') return 'USD/lb';
  if (/^(ZW|ZC|ZS|ZO|ZR)=F$/.test(symbol)) return 'USD/bu';
  if (symbol === 'PL=F' || symbol === 'PA=F') return 'USD/oz';
  if (symbol.endsWith('=F')) return 'USD';

  // Indices
  if (symbol.startsWith('^')) return 'pts';

  // Crypto via yfinance (BTC-USD, ETH-USD, etc.)
  if (source === 'yfinance' && /-USD$/.test(symbol)) return 'USD';

  // Stooq (Polish market — GPW)
  if (source === 'stooq') return 'PLN';

  // CoinGecko
  if (source === 'coingecko') return 'USD';

  // Default yfinance (US stocks, ETFs)
  if (source === 'yfinance') return 'USD';

  return null;
}

/** Wyemituj zdarzenie — wszystkie strony nasłuchujące natychmiast pobiorą świeże dane */
export const triggerInstrumentsRefresh = (): void => {
  window.dispatchEvent(new Event('instruments-changed'));
};

export const getInstruments = (): Promise<InstrumentData[]> => {
  const now = Date.now();
  if (_instrumentsCache.length > 0 && now - _instrumentsCacheTime < INSTRUMENTS_TTL) {
    return Promise.resolve(_instrumentsCache);
  }
  return api.get('/market/instruments').then((r) => {
    _instrumentsCache = r.data;
    _instrumentsCacheTime = now;
    return r.data;
  });
};

// Wymusza odświeżenie (omijając cache) i aktualizuje cache
export const refreshInstruments = (): Promise<InstrumentData[]> =>
  api.get('/market/instruments').then((r) => {
    _instrumentsCache = r.data;
    _instrumentsCacheTime = Date.now();
    return r.data;
  });

// ── Sparkline cache ─────────────────────────────────────────────
const _sparklineCache = new Map<string, { data: number[]; time: number }>();
const SPARKLINE_TTL = 120_000; // 2 minuty

export const getSparkline = (
  symbol: string,
  timeframe: string = '1h',
  source: string = 'yfinance'
): Promise<number[]> => {
  const key = `${symbol}:${timeframe}:${source}`;
  const cached = _sparklineCache.get(key);
  if (cached && Date.now() - cached.time < SPARKLINE_TTL) {
    return Promise.resolve(cached.data);
  }
  return api.post('/market/sparkline', { symbol, timeframe, source }).then((r) => {
    _sparklineCache.set(key, { data: r.data, time: Date.now() });
    return r.data;
  });
};

export interface InstrumentProfile {
  symbol: string;
  profile_text: string;
  created_at: string;
}

export const getInstrumentProfile = (symbol: string): Promise<InstrumentProfile | null> =>
  api.get(`/market/profile/${encodeURIComponent(symbol)}`).then((r) => r.data).catch((e) => {
    if (e?.response?.status === 404) return null;
    throw e;
  });

export const saveInstrumentProfile = (symbol: string, profileText: string): Promise<void> =>
  api.post(`/market/profile/${encodeURIComponent(symbol)}`, { profile_text: profileText }).then(() => undefined);

export interface InstrumentSearchResult {
  symbol: string;
  name: string;
  type: string;
  exchange: string;
}

export const searchInstruments = (q: string): Promise<InstrumentSearchResult[]> =>
  api.get('/market/search', { params: { q } }).then((r) => r.data).catch(() => []);

export interface MarketAssessment {
  risk: number;
  risk_reason: string;
  opportunity: number;
  opportunity_reason: string;
}

export const assessMarket = (context: string): Promise<MarketAssessment> =>
  api.post('/market/assess', { context }).then((r) => r.data);

export const getPrices = (symbols: string[]): Promise<Record<string, number | null>> =>
  api.post('/market/prices', { symbols }).then((r) => r.data).catch(() => ({}));
