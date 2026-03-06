import { useEffect, useState } from 'react';
import { getAdminUsers, getAdminActivity, getAdminStats } from '../api/admin';
import { APP_TIMEZONE } from '../config';

interface AdminUser {
  id: number;
  email: string;
  display_name: string;
  is_admin: boolean;
  created_at: string;
  last_login: string | null;
  action_count: number;
  tokens: {
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
    requests: number;
  };
}

interface Activity {
  id: number;
  user_id: number;
  email: string;
  display_name: string;
  action: string;
  detail: string | null;
  ip_address: string | null;
  created_at: string;
}

interface GlobalStats {
  total_users: number;
  total_actions: number;
  tokens: {
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
    requests: number;
  };
}

const fmtDate = (iso: string | null) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('pl-PL', { timeZone: APP_TIMEZONE });
};

const fmtNum = (n: number) => n.toLocaleString('pl-PL');

const actionLabels: Record<string, string> = {
  login: 'Logowanie',
  analysis: 'Analiza',
  chat: 'Chat',
};

export default function Admin() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [activity, setActivity] = useState<Activity[]>([]);
  const [stats, setStats] = useState<GlobalStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'users' | 'activity'>('users');

  useEffect(() => {
    Promise.all([
      getAdminUsers().then((r) => setUsers(r.data)),
      getAdminActivity(100).then((r) => setActivity(r.data)),
      getAdminStats().then((r) => setStats(r.data)),
    ]).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="text-[var(--overlay)] text-center py-12">Ladowanie...</div>;
  }

  return (
    <div>
      <h1 className="text-xl md:text-2xl font-bold mb-4 md:mb-6">Panel Administracyjny</h1>

      {/* Global stats cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <StatCard label="Uzytkownicy" value={stats.total_users} />
          <StatCard label="Akcje" value={stats.total_actions} />
          <StatCard label="Zapytania AI" value={stats.tokens.requests} />
          <StatCard label="Koszt USD" value={`$${stats.tokens.cost_usd.toFixed(2)}`} />
        </div>
      )}

      {/* Token summary */}
      {stats && (
        <div className="bg-[var(--bg2)] rounded-lg p-4 border border-[var(--gray)] mb-6">
          <div className="flex flex-wrap gap-6 text-sm">
            <div>
              <span className="text-[var(--overlay)]">Tokeny wejsciowe: </span>
              <span className="text-[var(--fg)] font-mono">{fmtNum(stats.tokens.input_tokens)}</span>
            </div>
            <div>
              <span className="text-[var(--overlay)]">Tokeny wyjsciowe: </span>
              <span className="text-[var(--fg)] font-mono">{fmtNum(stats.tokens.output_tokens)}</span>
            </div>
            <div>
              <span className="text-[var(--overlay)]">Suma tokenow: </span>
              <span className="text-[var(--fg)] font-mono">
                {fmtNum(stats.tokens.input_tokens + stats.tokens.output_tokens)}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Tab switcher */}
      <div className="flex gap-2 mb-4">
        <button
          onClick={() => setTab('users')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === 'users'
              ? 'bg-[var(--accent)] text-[var(--bg)]'
              : 'bg-[var(--gray)] text-[var(--fg)] hover:bg-[var(--overlay)]'
          }`}
        >
          Uzytkownicy ({users.length})
        </button>
        <button
          onClick={() => setTab('activity')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            tab === 'activity'
              ? 'bg-[var(--accent)] text-[var(--bg)]'
              : 'bg-[var(--gray)] text-[var(--fg)] hover:bg-[var(--overlay)]'
          }`}
        >
          Aktywnosc ({activity.length})
        </button>
      </div>

      {/* Users table */}
      {tab === 'users' && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--gray)] text-[var(--overlay)] text-left">
                <th className="py-2 px-3">Uzytkownik</th>
                <th className="py-2 px-3 hidden md:table-cell">Rejestracja</th>
                <th className="py-2 px-3">Ostatnie logowanie</th>
                <th className="py-2 px-3 text-right">Akcje</th>
                <th className="py-2 px-3 text-right hidden sm:table-cell">Zapytania AI</th>
                <th className="py-2 px-3 text-right">Tokeny</th>
                <th className="py-2 px-3 text-right hidden sm:table-cell">Koszt</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-[var(--gray)]/50 hover:bg-[var(--gray)]/30 transition-colors">
                  <td className="py-2.5 px-3">
                    <div className="font-medium text-[var(--fg)]">
                      {u.display_name || u.email.split('@')[0]}
                      {u.is_admin && (
                        <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded bg-[var(--accent)]/20 text-[var(--accent)]">
                          ADMIN
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-[var(--overlay)]">{u.email}</div>
                  </td>
                  <td className="py-2.5 px-3 text-[var(--overlay)] text-xs hidden md:table-cell">
                    {fmtDate(u.created_at)}
                  </td>
                  <td className="py-2.5 px-3 text-[var(--overlay)] text-xs">
                    {fmtDate(u.last_login)}
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono">{u.action_count}</td>
                  <td className="py-2.5 px-3 text-right font-mono hidden sm:table-cell">{u.tokens.requests}</td>
                  <td className="py-2.5 px-3 text-right font-mono text-xs">
                    {fmtNum(u.tokens.input_tokens + u.tokens.output_tokens)}
                  </td>
                  <td className="py-2.5 px-3 text-right font-mono text-[var(--green)] hidden sm:table-cell">
                    ${u.tokens.cost_usd.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Activity log */}
      {tab === 'activity' && (
        <div className="flex flex-col gap-2">
          {activity.length === 0 ? (
            <div className="text-[var(--overlay)] text-center py-8">Brak aktywnosci.</div>
          ) : (
            activity.map((a) => (
              <div
                key={a.id}
                className="bg-[var(--bg2)] rounded-lg px-4 py-3 border border-[var(--gray)]/50 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`text-xs font-bold px-2 py-0.5 rounded ${
                      a.action === 'login'
                        ? 'bg-[var(--accent)]/20 text-[var(--accent)]'
                        : a.action === 'analysis'
                        ? 'bg-[var(--green)]/20 text-[var(--green)]'
                        : 'bg-[var(--yellow)]/20 text-[var(--yellow)]'
                    }`}
                  >
                    {actionLabels[a.action] || a.action}
                  </span>
                  <span className="text-sm text-[var(--fg)]">
                    {a.display_name || a.email.split('@')[0]}
                  </span>
                  {a.detail && (
                    <span className="text-xs text-[var(--overlay)]">{a.detail}</span>
                  )}
                </div>
                <div className="flex items-center gap-3 text-xs text-[var(--overlay)]">
                  {a.ip_address && <span>{a.ip_address}</span>}
                  <span>{fmtDate(a.created_at)}</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-[var(--bg2)] rounded-lg p-4 border border-[var(--gray)]">
      <div className="text-xs text-[var(--overlay)] mb-1">{label}</div>
      <div className="text-xl md:text-2xl font-bold text-[var(--fg)]">{value}</div>
    </div>
  );
}
