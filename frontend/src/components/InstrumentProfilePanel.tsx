import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { getInstrumentProfile, saveInstrumentProfile } from '../api/market';
import { sendMessage } from '../api/chat';
import { APP_TIMEZONE } from '../config';

// Module-level cache shared across all panel instances and page navigations
const MEM_CACHE_MAX = 50;
const memCache: Record<string, { text: string; date: string }> = {};
const memCacheOrder: string[] = [];

function memCacheSet(key: string, value: { text: string; date: string }) {
  if (!(key in memCache)) {
    memCacheOrder.push(key);
    while (memCacheOrder.length > MEM_CACHE_MAX) {
      const oldest = memCacheOrder.shift()!;
      delete memCache[oldest];
    }
  }
  memCache[key] = value;
}

const DEFAULT_SYSTEM =
  'Jestes ekspertem finansowym i analitykiem rynkow kapitalowych. Odpowiadaj po polsku, zwiezle i merytorycznie. Uzywaj markdown z naglowkami.';

const USER_MSG = (name: string, symbol: string) =>
  `Opisz instrument finansowy: **${name}** (${symbol}).\n\nStruktura odpowiedzi:\n1. **Czym jest** – krotki opis\n2. **Co wplywa na cene** – czynniki makroekonomiczne, sektorowe i techniczne\n3. **Na co wplywa** – korelacje z innymi rynkami, walutami, surowcami`;

interface Props {
  symbol: string;
  name: string;
  systemPrompt?: string;
}

export default function InstrumentProfilePanel({ symbol, name, systemPrompt }: Props) {
  const [profile, setProfile] = useState<{ text: string; date: string } | null>(null);
  const [checking, setChecking] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    if (!symbol) return;

    // Check in-memory cache first (instant)
    if (memCache[symbol]) {
      setProfile(memCache[symbol]);
      setChecking(false);
      return;
    }

    // Fetch from backend
    setChecking(true);
    setProfile(null);
    getInstrumentProfile(symbol)
      .then((data) => {
        if (data) {
          const p = { text: data.profile_text, date: data.created_at };
          memCacheSet(symbol, p);
          setProfile(p);
        }
      })
      .catch(() => {})
      .finally(() => setChecking(false));
  }, [symbol]);

  const generate = async () => {
    setGenerating(true);
    try {
      const { reply } = await sendMessage(
        [{ role: 'user', content: USER_MSG(name, symbol) }],
        systemPrompt?.trim() || DEFAULT_SYSTEM,
        'profile',
      );
      const now = new Date().toISOString();
      const p = { text: reply, date: now };
      memCache[symbol] = p;
      setProfile(p);
      // Save to backend cache (fire-and-forget, don't block UI)
      saveInstrumentProfile(symbol, reply).catch(() => {});
    } catch {
      // silently ignore — profile stays as it was
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="rounded-xl border border-[var(--gray)] bg-[var(--bg2)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 sm:px-4 py-2.5 sm:py-3 border-b border-[var(--gray)]">
        <div className="min-w-0">
          <h3 className="text-sm sm:text-base font-bold">Analiza instrumentu</h3>
          <p className="text-xs sm:text-sm text-[var(--overlay)] mt-0.5 truncate">
            {checking
              ? 'Sprawdzam cache...'
              : profile
              ? `Wygenerowano: ${new Date(profile.date).toLocaleString('pl-PL', { timeZone: APP_TIMEZONE })}`
              : 'Opis, czynniki cenowe, korelacje rynkowe'}
          </p>
        </div>
        <button
          onClick={generate}
          disabled={generating || checking}
          className="ml-2 sm:ml-3 px-3 sm:px-4 py-1.5 rounded-lg bg-[var(--accent)] text-[var(--bg)] text-xs sm:text-sm font-semibold hover:opacity-90 disabled:opacity-50 transition-opacity flex-shrink-0"
        >
          {generating ? 'Generuje...' : profile ? 'Regeneruj' : 'Generuj opis AI'}
        </button>
      </div>

      {/* Body */}
      <div className="px-3 sm:px-4 py-3 sm:py-4 min-h-[80px]">
        {checking && (
          <p className="text-sm text-[var(--overlay)] text-center py-3 animate-pulse">
            Sprawdzam cache...
          </p>
        )}
        {!checking && !profile && !generating && (
          <p className="text-sm text-[var(--overlay)] text-center py-3">
            Kliknij "Generuj opis AI" aby uzyskac analize tego instrumentu.
          </p>
        )}
        {generating && (
          <p className="text-sm text-[var(--overlay)] text-center py-3 animate-pulse">
            Generowanie analizy...
          </p>
        )}
        {profile && !generating && (
          <div className="md-content md-profile text-xs sm:text-sm leading-relaxed">
            <ReactMarkdown>{profile.text}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
