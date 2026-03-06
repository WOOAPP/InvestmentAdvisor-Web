import { useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { useAppStore } from '../stores/appStore';

const navItems = [
  { to: '/', label: 'Dashboard' },
  { to: '/charts', label: 'Wykresy' },
  { to: '/calendar', label: 'Kalendarz' },
  { to: '/portfolio', label: 'Portfel' },
  { to: '/history', label: 'Historia' },
  { to: '/settings', label: 'Ustawienia' },
];

export default function Layout() {
  const { user, logout } = useAuthStore();
  const { statusMsg } = useAppStore();
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();

  // Close menu on navigation
  const closeMenu = () => setMenuOpen(false);

  return (
    <div className="h-screen overflow-hidden flex flex-col">
      <nav className="bg-[var(--bg2)] border-b border-[var(--gray)] flex-shrink-0">
        {/* Top bar */}
        <div className="flex items-center justify-between px-4 md:px-6 py-2.5 md:py-3">
          <div className="flex items-center gap-4 md:gap-8">
            {/* Hamburger — mobile only */}
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="md:hidden flex flex-col gap-1 p-1.5 -ml-1"
              aria-label="Menu"
            >
              <span className={`block w-5 h-0.5 bg-[var(--fg)] transition-transform ${menuOpen ? 'rotate-45 translate-y-[3px]' : ''}`} />
              <span className={`block w-5 h-0.5 bg-[var(--fg)] transition-opacity ${menuOpen ? 'opacity-0' : ''}`} />
              <span className={`block w-5 h-0.5 bg-[var(--fg)] transition-transform ${menuOpen ? '-rotate-45 -translate-y-[3px]' : ''}`} />
            </button>

            <div className="flex items-center gap-1.5">
              <img src="/logo.png" alt="IAdvisor" className="h-12 md:h-[84px]" />
              <span className="text-[var(--overlay)] text-[10px] md:text-xs tracking-wide">by R.Dębski inc.</span>
            </div>

            {/* Desktop nav links */}
            <div className="hidden md:flex gap-1.5">
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
              {user?.is_admin && (
                <NavLink
                  to="/admin"
                  className={({ isActive }) =>
                    `px-5 py-2 rounded-lg text-base font-medium transition-colors ${
                      isActive
                        ? 'bg-[var(--red)] text-[var(--bg)]'
                        : 'text-[var(--red)] hover:bg-[var(--gray)]'
                    }`
                  }
                >
                  Admin
                </NavLink>
              )}
            </div>
          </div>

          {/* Right side: status + user */}
          <div className="flex items-center gap-2 md:gap-3 text-sm">
            {statusMsg && (() => {
              const isError   = statusMsg.toLowerCase().includes('blad') || statusMsg.toLowerCase().includes('błąd');
              const isReady   = statusMsg === 'Gotowy';
              return (
                <div className={`flex items-center gap-1.5 px-2 md:px-2.5 py-1 rounded-full text-[10px] md:text-[11px] font-bold border tracking-wide ${
                  isError   ? 'bg-[var(--red)]/10 border-[var(--red)]/40 text-[var(--red)]'
                  : isReady ? 'bg-[var(--green)]/10 border-[var(--green)]/30 text-[var(--green)]'
                            : 'bg-[var(--accent)]/15 border-[var(--accent)]/40 text-[var(--accent)]'
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                    isError   ? 'bg-[var(--red)]'
                    : isReady ? 'bg-[var(--green)]'
                              : 'bg-[var(--accent)] animate-pulse'
                  }`} />
                  <span className="hidden sm:inline">{statusMsg}</span>
                </div>
              );
            })()}
            <span className="text-[var(--overlay)] text-xs hidden sm:inline">{user?.display_name || user?.email}</span>
            <button
              onClick={logout}
              className="px-3 py-1 rounded bg-[var(--gray)] hover:bg-[var(--red)] transition-colors text-xs md:text-sm"
            >
              Wyloguj
            </button>
          </div>
        </div>

        {/* Mobile dropdown menu */}
        {menuOpen && (
          <div className="md:hidden border-t border-[var(--gray)] bg-[var(--bg2)] px-4 pb-3 pt-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={closeMenu}
                className={`block px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  location.pathname === item.to || (item.to !== '/' && location.pathname.startsWith(item.to))
                    ? 'bg-[var(--accent)] text-[var(--bg)]'
                    : 'text-[var(--fg)] hover:bg-[var(--gray)]'
                }`}
              >
                {item.label}
              </NavLink>
            ))}
            {user?.is_admin && (
              <NavLink
                to="/admin"
                onClick={closeMenu}
                className={`block px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  location.pathname === '/admin'
                    ? 'bg-[var(--red)] text-[var(--bg)]'
                    : 'text-[var(--red)] hover:bg-[var(--gray)]'
                }`}
              >
                Admin
              </NavLink>
            )}
            <div className="mt-2 pt-2 border-t border-[var(--gray)] text-xs text-[var(--overlay)]">
              {user?.display_name || user?.email}
            </div>
          </div>
        )}
      </nav>
      <main className="relative flex-1 overflow-y-auto min-h-0 p-3 md:p-6">
        <Outlet />
      </main>
    </div>
  );
}
