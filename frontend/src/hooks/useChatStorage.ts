/**
 * Hook do persystencji wiadomości chatu w localStorage.
 * Każda wiadomość ma timestamp; wiadomości starsze niż 72h są automatycznie usuwane.
 */
import { useState, useRef, useCallback, useEffect } from 'react';
import type { ChatMessage } from '../api/chat';

const TTL = 72 * 60 * 60 * 1000; // 72 godziny w ms

interface StoredMsg { role: string; content: string; ts: number; }

function load(key: string): { msgs: ChatMessage[]; ts: number[] } {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return { msgs: [], ts: [] };
    const arr: StoredMsg[] = JSON.parse(raw);
    const cutoff = Date.now() - TTL;
    const valid = arr.filter((m) => m.ts > cutoff);
    return {
      msgs: valid.map(({ role, content }) => ({ role: role as ChatMessage['role'], content })),
      ts: valid.map((m) => m.ts),
    };
  } catch {
    return { msgs: [], ts: [] };
  }
}

function persist(key: string, msgs: ChatMessage[], ts: number[]): void {
  try {
    localStorage.setItem(key, JSON.stringify(msgs.map((m, i) => ({ ...m, ts: ts[i] ?? Date.now() }))));
  } catch { /* quota exceeded or private mode */ }
}

/**
 * @param storageKey - unikalny klucz localStorage dla tego okna chatu
 */
export function useChatStorage(storageKey: string) {
  const [initMsgs] = useState(() => {
    const data = load(storageKey);
    return { msgs: data.msgs, ts: data.ts };
  });
  const tsRef = useRef<number[]>(initMsgs.ts);

  const keyRef = useRef(storageKey);
  const [messages, setMessagesRaw] = useState<ChatMessage[]>(initMsgs.msgs);

  // Reload messages when storageKey changes
  useEffect(() => {
    if (keyRef.current === storageKey) return;
    keyRef.current = storageKey;
    const { msgs, ts } = load(storageKey);
    tsRef.current = ts;
    setMessagesRaw(msgs);
  }, [storageKey]);

  /** Zastępuje całą tablicę wiadomości. Nowe wiadomości (powyżej poprzedniej długości) dostają aktualny timestamp. */
  const setMessages = useCallback((next: ChatMessage[]) => {
    const now = Date.now();
    // Rozszerz timestamps dla nowych wiadomości
    while (tsRef.current.length < next.length) tsRef.current.push(now);
    // Przytnij jeśli wiadomości zostały usunięte
    tsRef.current = tsRef.current.slice(0, next.length);
    persist(storageKey, next, tsRef.current);
    setMessagesRaw(next);
  }, [storageKey]);

  /** Czyści historię i usuwa wpis z localStorage. */
  const clearMessages = useCallback(() => {
    tsRef.current = [];
    setMessagesRaw([]);
    try { localStorage.removeItem(storageKey); } catch { /* ignore */ }
  }, [storageKey]);

  return { messages, setMessages, clearMessages };
}
