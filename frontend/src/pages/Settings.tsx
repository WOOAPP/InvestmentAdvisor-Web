import { useEffect, useState } from 'react';
import api from '../api/client';

export default function Settings() {
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);
  const [keys, setKeys] = useState({ anthropic: '', openai: '', openrouter: '', newsdata: '' });
  const [provider, setProvider] = useState('openai');
  const [model, setModel] = useState('gpt-4.1-mini');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.get('/settings').then((res) => {
      setConfig(res.data);
      const apiKeys = (res.data.api_keys || {}) as Record<string, string>;
      setKeys({
        anthropic: apiKeys.anthropic || '',
        openai: apiKeys.openai || '',
        openrouter: apiKeys.openrouter || '',
        newsdata: apiKeys.newsdata || '',
      });
      setProvider(res.data.ai_provider || 'openai');
      setModel(res.data.ai_model || 'gpt-4.1-mini');
    });
  }, []);

  const save = async () => {
    // Only send non-masked keys
    const apiKeysToSend: Record<string, string> = {};
    for (const [k, v] of Object.entries(keys)) {
      if (v && !v.includes('*')) {
        apiKeysToSend[k] = v;
      }
    }
    await api.put('/settings', {
      api_keys: apiKeysToSend,
      ai_provider: provider,
      ai_model: model,
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  if (!config) return <div className="text-[var(--overlay)]">Ladowanie...</div>;

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold mb-6">Ustawienia</h1>

      <section className="bg-[var(--bg2)] rounded-lg p-6 border border-[var(--gray)] mb-6">
        <h2 className="text-lg font-semibold mb-4">Klucze API</h2>
        {(['anthropic', 'openai', 'openrouter', 'newsdata'] as const).map((k) => (
          <div key={k} className="mb-3">
            <label className="text-sm text-[var(--overlay)] block mb-1 capitalize">{k}</label>
            <input
              type="password"
              value={keys[k]}
              onChange={(e) => setKeys({ ...keys, [k]: e.target.value })}
              placeholder={`Klucz ${k}`}
              className="w-full bg-[var(--bg)] border border-[var(--gray)] rounded px-3 py-2 text-sm focus:border-[var(--accent)] outline-none"
            />
          </div>
        ))}
      </section>

      <section className="bg-[var(--bg2)] rounded-lg p-6 border border-[var(--gray)] mb-6">
        <h2 className="text-lg font-semibold mb-4">Model AI</h2>
        <div className="flex gap-4">
          <div className="flex-1">
            <label className="text-sm text-[var(--overlay)] block mb-1">Dostawca</label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
              className="w-full bg-[var(--bg)] border border-[var(--gray)] rounded px-3 py-2 text-sm"
            >
              <option value="anthropic">Anthropic</option>
              <option value="openai">OpenAI</option>
              <option value="openrouter">OpenRouter</option>
            </select>
          </div>
          <div className="flex-1">
            <label className="text-sm text-[var(--overlay)] block mb-1">Model</label>
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full bg-[var(--bg)] border border-[var(--gray)] rounded px-3 py-2 text-sm focus:border-[var(--accent)] outline-none"
            />
          </div>
        </div>
      </section>

      <button
        onClick={save}
        className="px-6 py-2 rounded bg-[var(--accent)] text-[var(--bg)] font-semibold hover:opacity-90 transition-opacity"
      >
        {saved ? 'Zapisano!' : 'Zapisz ustawienia'}
      </button>
    </div>
  );
}
