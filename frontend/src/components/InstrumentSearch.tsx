/**
 * InstrumentSearch — pola Symbol i Nazwa z autopodpowiedzią (Yahoo Finance).
 *
 * Renderuje dwa inputy jako display:contents — wpadają bezpośrednio do flex-rodzica.
 * Każdy input ma opcjonalny label nad sobą (symbolLabel / nameLabel).
 */
import { useEffect, useRef, useState } from 'react';
import { searchInstruments, type InstrumentSearchResult } from '../api/market';

interface Props {
  symbol: string;
  name: string;
  onSymbol: (v: string) => void;
  onName: (v: string) => void;
  /** Wywoływane przy wyborze sugestii — atomowe ustawienie obu pól naraz */
  onPick?: (symbol: string, name: string) => void;
  symbolPlaceholder?: string;
  namePlaceholder?: string;
  /** Klasa CSS wspólna dla obu inputów */
  inputClassName?: string;
  /** Klasa CSS dla wrappera symbolu (z relative) */
  symbolWrapClassName?: string;
  /** Klasa CSS dla wrappera nazwy (z relative) */
  nameWrapClassName?: string;
  symbolLabel?: string;
  nameLabel?: string;
}

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

type ActiveField = 'symbol' | 'name' | null;

export default function InstrumentSearch({
  symbol,
  name,
  onSymbol,
  onName,
  onPick,
  symbolPlaceholder = 'np. AAPL',
  namePlaceholder = 'np. Apple Inc.',
  inputClassName = '',
  symbolWrapClassName = '',
  nameWrapClassName = '',
  symbolLabel,
  nameLabel,
}: Props) {
  const [suggestions, setSuggestions] = useState<InstrumentSearchResult[]>([]);
  const [activeField, setActiveField] = useState<ActiveField>(null);
  const [query, setQuery] = useState('');
  const debouncedQuery = useDebounce(query, 300);
  const containerRef = useRef<HTMLDivElement>(null);

  // Fetch suggestions when debounced query changes
  useEffect(() => {
    if (debouncedQuery.length < 1) {
      setSuggestions([]);
      return;
    }
    searchInstruments(debouncedQuery).then(setSuggestions).catch(() => setSuggestions([]));
  }, [debouncedQuery]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setSuggestions([]);
        setActiveField(null);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const pick = (item: InstrumentSearchResult) => {
    // Jeśli rodzic udostępnia onPick, ustawiamy oba pola atomowo (bez problemu stale closure)
    if (onPick) {
      onPick(item.symbol, item.name);
    } else {
      onSymbol(item.symbol);
      onName(item.name);
    }
    setSuggestions([]);
    setActiveField(null);
    setQuery('');
  };

  const handleSymbolChange = (v: string) => {
    onSymbol(v);
    setActiveField('symbol');
    setQuery(v);
  };

  const handleNameChange = (v: string) => {
    onName(v);
    setActiveField('name');
    setQuery(v);
  };

  const base =
    inputClassName ||
    'bg-[var(--bg)] border border-[var(--gray)] rounded-lg px-3 py-2 text-sm focus:border-[var(--accent)] outline-none transition-colors';

  const showDropdown = suggestions.length > 0 && activeField !== null;

  return (
    <div ref={containerRef} className="contents">
      {/* Symbol */}
      <div className={`relative ${symbolWrapClassName}`}>
        {symbolLabel && (
          <label className="text-xs text-[var(--overlay)] block mb-1">{symbolLabel}</label>
        )}
        <input
          value={symbol}
          onChange={(e) => handleSymbolChange(e.target.value)}
          onFocus={() => { if (symbol) { setActiveField('symbol'); setQuery(symbol); } }}
          placeholder={symbolPlaceholder}
          autoComplete="off"
          className={base}
        />
        {showDropdown && activeField === 'symbol' && (
          <Dropdown items={suggestions} onPick={pick} />
        )}
      </div>

      {/* Nazwa */}
      <div className={`relative ${nameWrapClassName}`}>
        {nameLabel && (
          <label className="text-xs text-[var(--overlay)] block mb-1">{nameLabel}</label>
        )}
        <input
          value={name}
          onChange={(e) => handleNameChange(e.target.value)}
          onFocus={() => { if (name) { setActiveField('name'); setQuery(name); } }}
          placeholder={namePlaceholder}
          autoComplete="off"
          className={base}
        />
        {showDropdown && activeField === 'name' && (
          <Dropdown items={suggestions} onPick={pick} />
        )}
      </div>
    </div>
  );
}

function Dropdown({
  items,
  onPick,
}: {
  items: InstrumentSearchResult[];
  onPick: (item: InstrumentSearchResult) => void;
}) {
  return (
    <div className="absolute z-50 top-full mt-1 left-0 min-w-[240px] bg-[var(--bg2)] border border-[var(--accent)]/40 rounded-xl shadow-xl overflow-hidden">
      {items.map((item) => (
        <button
          key={item.symbol}
          type="button"
          onMouseDown={(e) => { e.preventDefault(); onPick(item); }}
          className="w-full text-left px-3 py-2 hover:bg-[var(--gray)]/40 transition-colors flex items-center gap-2"
        >
          <span className="font-mono text-xs font-bold text-[var(--accent)] w-20 flex-shrink-0 truncate">
            {item.symbol}
          </span>
          <span className="text-sm text-[var(--fg)] truncate flex-1">{item.name}</span>
          <span className="text-[10px] text-[var(--overlay)] flex-shrink-0">{item.type}</span>
        </button>
      ))}
    </div>
  );
}
