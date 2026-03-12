import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useState } from 'react'

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const navCls = ({ isActive }) =>
    `text-sm font-medium transition-colors px-1 py-0.5 ${
      isActive ? 'text-emerald-400' : 'text-slate-400 hover:text-slate-100'
    }`

  const fantasyNavCls = ({ isActive }) =>
    `text-sm font-semibold transition-colors px-2.5 py-1 rounded-md ${
      isActive
        ? 'bg-emerald-500/15 text-emerald-400'
        : 'text-slate-300 hover:text-white hover:bg-white/[0.06]'
    }`

  return (
    <div className="min-h-screen bg-pitch flex flex-col">
      {/* Navbar */}
      <header className="sticky top-0 z-50 bg-pitch/90 backdrop-blur-md border-b border-white/[0.07]">
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center gap-5">
          {/* Logo */}
          <Link to="/matches" className="flex items-center gap-2 shrink-0">
            <span className="text-xl">🏏</span>
            <span className="font-bold text-white text-sm hidden sm:block">T20 DataHub</span>
          </Link>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-1 flex-1">
            <NavLink to="/matches" className={navCls} end>
              <span className="px-1">Matches</span>
            </NavLink>
            <NavLink to="/fantasy" className={fantasyNavCls}>
              ✨ Fantasy
            </NavLink>
            <NavLink to="/fantasy/leaderboard" className={navCls}>
              <span className="px-1">Leaderboards</span>
            </NavLink>
            {user && (
              <>
                <NavLink to="/me/dashboard" className={navCls}>
                  <span className="px-1">Dashboard</span>
                </NavLink>
                <NavLink to="/me/profile" className={navCls}>
                  <span className="px-1">Profile</span>
                </NavLink>
              </>
            )}
            {user?.role === 'admin' && (
              <NavLink to="/admin/matches" className={({ isActive }) =>
                `text-sm font-medium transition-colors px-2 py-0.5 rounded ${
                  isActive ? 'text-amber-400' : 'text-amber-500/70 hover:text-amber-400'
                }`
              }>Admin</NavLink>
            )}
          </nav>

          <div className="flex-1 md:flex-none" />

          {/* Auth */}
          <div className="flex items-center gap-2">
            {user ? (
              <>
                <span className="text-xs text-slate-400 hidden sm:block">
                  <span className="text-emerald-400 font-semibold">{user.username}</span>
                </span>
                <button onClick={handleLogout} className="btn-secondary text-xs py-1.5 px-3">
                  Logout
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="btn-secondary text-xs py-1.5 px-3">Login</Link>
                <Link to="/register" className="btn-primary text-xs py-1.5 px-3">Sign up</Link>
              </>
            )}

            {/* Mobile menu toggle */}
            <button
              className="md:hidden ml-1 text-slate-400 hover:text-white p-1"
              onClick={() => setMenuOpen(v => !v)}
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {menuOpen
                  ? <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  : <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                }
              </svg>
            </button>
          </div>
        </div>

        {/* Mobile dropdown */}
        {menuOpen && (
          <div className="md:hidden border-t border-white/[0.07] bg-surface px-4 py-3 flex flex-col gap-1">
            <NavLink to="/matches" className={navCls} end onClick={() => setMenuOpen(false)}>
              <span className="block py-1">Matches</span>
            </NavLink>
            <NavLink to="/fantasy" className={fantasyNavCls} onClick={() => setMenuOpen(false)}>
              ✨ Fantasy
            </NavLink>
            <NavLink to="/fantasy/leaderboard" className={navCls} onClick={() => setMenuOpen(false)}>
              <span className="block py-1">Leaderboards</span>
            </NavLink>
            {user && (
              <>
                <NavLink to="/me/dashboard" className={navCls} onClick={() => setMenuOpen(false)}>
                  <span className="block py-1">Dashboard</span>
                </NavLink>
                <NavLink to="/me/profile" className={navCls} onClick={() => setMenuOpen(false)}>
                  <span className="block py-1">Profile</span>
                </NavLink>
              </>
            )}
            {user?.role === 'admin' && (
              <NavLink to="/admin/matches" className={navCls} onClick={() => setMenuOpen(false)}>
                <span className="block py-1">Admin</span>
              </NavLink>
            )}
          </div>
        )}
      </header>

      {/* Page content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 py-6">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t border-white/[0.07] py-4 text-center text-xs text-slate-600">
        T20 DataHub · Ball-by-ball data 2014–2026 ·{' '}
        <a href="/api/docs" target="_blank" className="hover:text-slate-400">API Docs</a>
      </footer>
    </div>
  )
}
