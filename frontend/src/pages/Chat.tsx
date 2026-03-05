import { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import api from '../api/client';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = async () => {
    if (!input.trim() || loading) return;
    const userMsg: Message = { role: 'user', content: input.trim() };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput('');
    setLoading(true);
    try {
      const res = await api.post('/chat', { messages: newMessages });
      setMessages([...newMessages, { role: 'assistant', content: res.data.reply }]);
    } catch {
      setMessages([
        ...newMessages,
        { role: 'assistant', content: 'Blad komunikacji z serwerem.' },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-80px)]">
      <h1 className="text-2xl font-bold mb-4">Chat AI</h1>
      <div className="flex-1 overflow-y-auto space-y-4 mb-4">
        {messages.length === 0 && (
          <div className="text-[var(--overlay)] text-center py-12">
            Rozpocznij dyskusje o rynkach i analizach.
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`rounded-lg p-4 max-w-[80%] ${
              m.role === 'user'
                ? 'bg-[var(--accent)] text-[var(--bg)] ml-auto'
                : 'bg-[var(--bg2)] border border-[var(--gray)]'
            }`}
          >
            {m.role === 'assistant' ? (
              <div className="prose prose-invert max-w-none text-sm">
                <ReactMarkdown>{m.content}</ReactMarkdown>
              </div>
            ) : (
              <p className="text-sm">{m.content}</p>
            )}
          </div>
        ))}
        {loading && (
          <div className="bg-[var(--bg2)] border border-[var(--gray)] rounded-lg p-4 max-w-[80%]">
            <span className="text-[var(--overlay)] text-sm">Mysle...</span>
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
          className="flex-1 bg-[var(--bg2)] border border-[var(--gray)] rounded px-4 py-2 text-[var(--fg)] focus:border-[var(--accent)] outline-none"
        />
        <button
          onClick={send}
          disabled={loading}
          className="px-6 py-2 rounded bg-[var(--accent)] text-[var(--bg)] font-semibold hover:opacity-90 transition-opacity disabled:opacity-50"
        >
          Wyslij
        </button>
      </div>
    </div>
  );
}
