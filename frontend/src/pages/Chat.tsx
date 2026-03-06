import { useRef, useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { sendMessage } from '../api/chat';
import { getCalendar, type CalendarEvent } from '../api/calendar';
import { useChatStorage } from '../hooks/useChatStorage';

export default function Chat() {
  const { messages, setMessages } = useChatStorage('chat:main');
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [calendarEvents, setCalendarEvents] = useState<CalendarEvent[]>([]);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getCalendar().then((r) => setCalendarEvents(r.events)).catch(() => {});
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = async () => {
    if (!input.trim() || loading) return;
    const newMessages = [...messages, { role: 'user' as const, content: input.trim() }];
    setMessages(newMessages);
    setInput('');
    setLoading(true);
    try {
      const { reply } = await sendMessage(newMessages);
      setMessages([...newMessages, { role: 'assistant', content: reply }]);
    } catch {
      setMessages([...newMessages, { role: 'assistant', content: 'Blad komunikacji z serwerem.' }]);
    } finally {
      setLoading(false);
    }
  };

  const highImpactCount = calendarEvents.filter((e) => e.impact_raw === 'High').length;
  const mediumImpactCount = calendarEvents.filter((e) => e.impact_raw === 'Medium').length;

  return (
    <div className="absolute inset-0 flex flex-col p-3 sm:p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl sm:text-2xl font-bold">Chat AI</h1>
        {calendarEvents.length > 0 && (
          <div className="flex items-center gap-2 text-xs text-[var(--overlay)] bg-[var(--bg2)] border border-[var(--gray)] rounded-lg px-3 py-1.5">
            <span>📅 Kalendarz makro w kontekście:</span>
            {highImpactCount > 0 && <span className="text-[#f38ba8] font-semibold">🔴 {highImpactCount}</span>}
            {mediumImpactCount > 0 && <span className="text-[#f9e2af] font-semibold">🟡 {mediumImpactCount}</span>}
            <span>wydarzeń (7 dni)</span>
          </div>
        )}
      </div>
      <div className="flex-1 overflow-y-auto space-y-3 mb-4 min-h-0">
        {messages.length === 0 && (
          <div className="text-[var(--overlay)] text-center py-12 space-y-2">
            <p>Rozpocznij dyskusje o rynkach i analizach.</p>
            {calendarEvents.length > 0 && (
              <p className="text-xs text-[var(--overlay)]/60">
                Agent ma dostęp do kalendarza makroekonomicznego na najbliższe 7 dni
                ({highImpactCount > 0 ? `🔴 ${highImpactCount} wysoki` : ''}
                {highImpactCount > 0 && mediumImpactCount > 0 ? ', ' : ''}
                {mediumImpactCount > 0 ? `🟡 ${mediumImpactCount} średni` : ''}).
              </p>
            )}
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-[92%] sm:max-w-[80%] py-1 ${
              m.role === 'user'
                ? 'text-[#f9e2af] ml-auto text-right font-medium'
                : 'text-[#a6e3a1]'
            }`}
          >
            {m.role === 'assistant' ? (
              <div className="md-content text-base sm:text-lg">
                <ReactMarkdown>{m.content}</ReactMarkdown>
              </div>
            ) : (
              <p className="text-base sm:text-lg">{m.content}</p>
            )}
          </div>
        ))}
        {loading && (
          <div className="text-[#a6e3a1] text-base sm:text-lg animate-pulse">
            Mysle...
          </div>
        )}
        <div ref={endRef} />
      </div>
      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder="Napisz wiadomosc..."
          className="flex-1 bg-[var(--bg2)] border border-[var(--gray)] rounded-lg px-4 py-2.5 text-[var(--fg)] focus:border-[var(--accent)] outline-none transition-colors"
        />
        <button
          onClick={send}
          disabled={loading}
          className="px-6 py-2.5 rounded-lg bg-[var(--accent)] text-[var(--bg)] font-semibold hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          Wyslij
        </button>
      </div>
    </div>
  );
}
