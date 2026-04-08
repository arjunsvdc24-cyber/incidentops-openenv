import { NavLink } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useUIStore, useAuthStore } from '../stores/episodeStore';
import { getHealth } from '../api/client';

interface LayoutProps {
  children: React.ReactNode;
}

const NAV_ITEMS = [
  { path: '/', label: 'Dashboard', icon: 'dashboard' },
  { path: '/episode', label: 'Episode', icon: 'play' },
  { path: '/tasks', label: 'Tasks', icon: 'tasks' },
  { path: '/leaderboard', label: 'Leaderboard', icon: 'trophy' },
  { path: '/episodes', label: 'Episodes', icon: 'list' },
  { path: '/replay', label: 'Replay', icon: 'replay' },
  { path: '/validate', label: 'Validate', icon: 'validate' },
  { path: '/profile', label: 'Profile', icon: 'user' },
];

const ICONS: Record<string, JSX.Element> = {
  dashboard: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
    </svg>
  ),
  play: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  tasks: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
    </svg>
  ),
  trophy: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
    </svg>
  ),
  list: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
    </svg>
  ),
  replay: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  ),
  user: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
    </svg>
  ),
  validate: (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
    </svg>
  ),
};

export function Layout({ children }: LayoutProps) {
  const { sidebarOpen, toggleSidebar } = useUIStore();
  const { isAuthenticated, username, logout } = useAuthStore();
  const { data: healthData } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 10000,
    retry: 1,
  });

  const apiHealthy = healthData?.status === 'ok';

  return (
    <div className="flex h-screen bg-bg overflow-hidden">
      {/* Mobile Header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-50 bg-surface border-b border-border px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={toggleSidebar} className="text-text-secondary hover:text-text-primary">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <span className="text-sm font-semibold font-mono text-text-primary">IncidentOps</span>
        </div>
        {isAuthenticated && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-secondary font-mono">{username}</span>
            <button onClick={logout} className="text-text-secondary hover:text-danger">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
          </div>
        )}
      </div>

      {/* Sidebar Overlay on mobile */}
      {sidebarOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/60 z-30"
          onClick={toggleSidebar}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed lg:static inset-y-0 left-0 z-40 w-56 bg-surface border-r border-border transform transition-transform duration-200 pointer-events-auto ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        }`}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="px-4 py-4 border-b border-border">
            <div className="flex items-center gap-2">
              {/* API health dot */}
              <span
                className={`w-2 h-2 rounded-full shrink-0 ${
                  apiHealthy ? 'bg-success' : 'bg-text-muted'
                }`}
                title={apiHealthy ? 'API healthy' : 'API unreachable'}
              />
              <span className="text-sm font-bold font-mono text-text-primary tracking-tight">IncidentOps</span>
              <span className="text-2xs text-text-muted font-mono ml-auto">v15</span>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto overscroll-contain">
            <ul className="space-y-0.5 p-2">
              {NAV_ITEMS.map((item) => (
                <li key={item.path}>
                  <NavLink
                    to={item.path}
                    onClick={() => {
                      if (window.innerWidth < 1024) toggleSidebar();
                    }}
                    className={({ isActive }) =>
                      `flex items-center gap-2.5 px-3 py-2 rounded text-xs transition-colors font-mono ${
                        isActive
                          ? 'bg-accent/10 text-accent border-l-2 border-accent'
                          : 'text-text-secondary hover:bg-bg hover:text-text-primary border-l-2 border-transparent'
                      }`
                    }
                  >
                    {ICONS[item.icon]}
                    <span>{item.label}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>

          {/* User Section */}
          <div className="p-3 border-t border-border">
            {isAuthenticated ? (
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded border border-border flex items-center justify-center bg-bg shrink-0">
                  <span className="text-2xs font-bold text-text-secondary font-mono">
                    {username?.charAt(0).toUpperCase()}
                  </span>
                </div>
                <span className="text-xs text-text-secondary font-mono truncate flex-1">{username}</span>
                <button
                  onClick={logout}
                  className="p-1 text-text-muted hover:text-danger transition-colors"
                  title="Logout"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                  </svg>
                </button>
              </div>
            ) : (
              <NavLink
                to="/profile"
                className="flex items-center justify-center gap-1.5 px-3 py-2 rounded text-xs font-mono bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
                Sign In
              </NavLink>
            )}
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto overscroll-contain pt-14 lg:pt-0">
        <div className="p-4 lg:p-6 min-h-full">{children}</div>
      </main>
    </div>
  );
}
