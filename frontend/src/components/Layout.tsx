import { NavLink, Outlet } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { useAppStore } from '../stores/appStore';

const navItems = [
  { to: '/', label: 'Dashboard' },
  { to: '/portfolio', label: 'Portfel' },
  { to: '/calendar', label: 'Kalendarz' },
  { to: '/charts', label: 'Wykresy' },
  { to: '/history', label: 'Historia' },
  { to: '/settings', label: 'Ustawienia' },
];

export default function Layout() {
  const { user, logout } = useAuthStore();
  const { statusMsg } = useAppStore();

  return (
    <div className="h-screen overflow-hidden flex flex-col">
      <nav className="flex items-center justify-between px-6 py-3 bg-[var(--bg2)] border-b border-[var(--gray)] flex-shrink-0">
        <div className="flex items-center gap-8">
          <div className="flex flex-col leading-tight">
            <span className="text-[var(--accent)] font-bold text-2xl tracking-tight">InvestmentAdvisor</span>
            <span className="text-[var(--overlay)] text-xs tracking-wide">by R.Dębski inc.</span>
          </div>
          <div className="flex gap-1.5">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `px-5 py-2 rounded-lg text-base font-medium transition-colors ${
                    isActive
                      ? 'bg-[var(--accent)] text-[var(--bg)]'
                      : 'text-[var(--fg)] hover:bg-[var(--gray)]'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-3 text-sm">
          {statusMsg && (() => {
            const isRunning = statusMsg !== 'Gotowy' && !statusMsg.toLowerCase().includes('blad') && !statusMsg.toLowerCase().includes('błąd');
            const isError   = statusMsg.toLowerCase().includes('blad') || statusMsg.toLowerCase().includes('błąd');
            const isReady   = statusMsg === 'Gotowy';
            return (
              <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold border tracking-wide ${
                isError   ? 'bg-[var(--red)]/10 border-[var(--red)]/40 text-[var(--red)]'
                : isReady ? 'bg-[var(--green)]/10 border-[var(--green)]/30 text-[var(--green)]'
                          : 'bg-[var(--accent)]/15 border-[var(--accent)]/40 text-[var(--accent)]'
              }`}>
                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                  isError   ? 'bg-[var(--red)]'
                  : isReady ? 'bg-[var(--green)]'
                            : 'bg-[var(--accent)] animate-pulse'
                }`} />
                {statusMsg}
              </div>
            );
          })()}
          <span className="text-[var(--overlay)] text-xs">{user?.display_name || user?.email}</span>
          <button
            onClick={logout}
            className="px-3 py-1 rounded bg-[var(--gray)] hover:bg-[var(--red)] transition-colors text-sm"
          >
            Wyloguj
          </button>
        </div>
      </nav>
      <main className="relative flex-1 overflow-y-auto min-h-0 p-6">
        <Outlet />
      </main>
    </div>
  );
}
