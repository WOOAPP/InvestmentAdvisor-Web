import { NavLink, Outlet } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';

const navItems = [
  { to: '/', label: 'Dashboard' },
  { to: '/reports', label: 'Raporty' },
  { to: '/portfolio', label: 'Portfel' },
  { to: '/chat', label: 'Chat AI' },
  { to: '/settings', label: 'Ustawienia' },
];

export default function Layout() {
  const { user, logout } = useAuthStore();

  return (
    <div className="min-h-screen flex flex-col">
      <nav className="flex items-center justify-between px-6 py-3 bg-[var(--bg2)] border-b border-[var(--gray)]">
        <div className="flex items-center gap-6">
          <span className="text-[var(--accent)] font-bold text-lg">InvestmentAdvisor</span>
          <div className="flex gap-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded text-sm transition-colors ${
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
        <div className="flex items-center gap-4 text-sm">
          <span className="text-[var(--overlay)]">{user?.display_name || user?.email}</span>
          <button
            onClick={logout}
            className="px-3 py-1 rounded bg-[var(--gray)] hover:bg-[var(--red)] transition-colors text-sm"
          >
            Wyloguj
          </button>
        </div>
      </nav>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </div>
  );
}
