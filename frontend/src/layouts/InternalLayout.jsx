import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'

const INTERNAL_ROLES = new Set([
  'system_admin',
  'channel_ops_admin',
  'channel_manager',
  'sales_rep',
  'sales_ops',
  'finance_approver',
])

const ROLE_LABEL = {
  system_admin: 'System Admin',
  channel_ops_admin: 'Channel Ops Admin',
  channel_manager: 'Channel Manager',
  sales_rep: 'Sales Rep',
  sales_ops: 'Sales Ops',
  finance_approver: 'Finance Approver',
}

function decodeJwt(token) {
  try {
    const parts = token.split('.')
    if (parts.length < 2) return null
    const padded = parts[1] + '==='.slice((parts[1].length + 3) % 4)
    const json = atob(padded.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(json)
  } catch (_) {
    return null
  }
}

const IconHome = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M3 11l9-8 9 8" />
    <path d="M5 10v10h14V10" />
  </svg>
)
const IconInbox = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="22 12 16 12 14 15 10 15 8 12 2 12" />
    <path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" />
  </svg>
)
const IconPartners = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </svg>
)
const IconDeal = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    <path d="M9 22V12h6v10" />
  </svg>
)
const IconUsers = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
)
const IconGear = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9c.39.41.99.61 1.51.51H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
  </svg>
)
const IconBarChart = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <line x1="12" y1="20" x2="12" y2="10" />
    <line x1="18" y1="20" x2="18" y2="4" />
    <line x1="6" y1="20" x2="6" y2="16" />
  </svg>
)

// Nav-item visibility per role and per-item "enabled" flag (disabled items
// render as greyed "Coming soon" placeholders until the target page lands in
// a later sprint).
// Disabled items in Sprint 11: Partners (FPRM-182), Users (Sprint 12),
// Program Config (Sprint 13), Reports (Sprint 14).
const NAV_ITEMS = [
  {
    key: 'home',
    label: 'Home',
    to: '/internal/home',
    icon: IconHome,
    enabled: true,
    roles: ['system_admin', 'channel_ops_admin', 'channel_manager', 'sales_rep', 'sales_ops', 'finance_approver'],
  },
  {
    key: 'applications',
    label: 'Applications',
    to: '/internal/applications',
    icon: IconInbox,
    enabled: true,
    roles: ['system_admin', 'channel_ops_admin', 'channel_manager'],
  },
  {
    key: 'partners',
    label: 'Partners',
    to: '/internal/partners',
    icon: IconPartners,
    enabled: true,
    roles: ['system_admin', 'channel_ops_admin', 'channel_manager'],
  },
  {
    key: 'partner-users',
    label: 'Partner Users',
    to: '/internal/partner-users',
    icon: IconUsers,
    enabled: true,
    roles: ['system_admin', 'channel_ops_admin'],
  },
  {
    key: 'deals',
    label: 'Deals',
    to: '/internal/deals',
    icon: IconDeal,
    enabled: true,
    roles: ['system_admin', 'channel_ops_admin', 'channel_manager', 'sales_rep', 'sales_ops', 'finance_approver'],
  },
  {
    key: 'users',
    label: 'Users',
    to: '/internal/users',
    icon: IconUsers,
    enabled: true,
    roles: ['system_admin'],
  },
  {
    key: 'config',
    label: 'Program Config',
    to: '/internal/config',
    icon: IconGear,
    enabled: true,
    roles: ['system_admin', 'channel_ops_admin'],
  },
  {
    key: 'reports',
    label: 'Reports',
    to: '/internal/reports',
    icon: IconBarChart,
    enabled: false,
    roles: ['system_admin', 'channel_ops_admin', 'channel_manager', 'sales_rep', 'sales_ops', 'finance_approver'],
  },
]

const BREADCRUMB_MAP = {
  '/internal/home': 'Home',
  '/internal/applications': 'Applications',
  '/internal/partners': 'Partners',
  '/internal/deals': 'Deals',
  '/internal/users': 'Users',
  '/internal/partner-users': 'Partner Users',
  '/internal/config': 'Program Config',
  '/internal/reports': 'Reports',
}

function breadcrumbFromPath(pathname) {
  if (BREADCRUMB_MAP[pathname]) return BREADCRUMB_MAP[pathname]
  if (pathname.startsWith('/internal/applications/')) return 'Application Review'
  if (pathname.startsWith('/internal/deals/')) return 'Deal Detail'
  if (pathname.startsWith('/internal/partners/') && pathname.endsWith('/profile')) return 'Partner Profile'
  if (pathname.startsWith('/internal/partners/') && pathname.endsWith('/documents')) return 'Partner Documents'
  if (pathname.startsWith('/internal/')) {
    const seg = pathname.split('/').slice(-1)[0]
    return seg ? seg.charAt(0).toUpperCase() + seg.slice(1) : 'Internal'
  }
  return 'Internal'
}

export default function InternalLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const token = localStorage.getItem('token')
  const payload = token ? decodeJwt(token) : null
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => { setMenuOpen(false) }, [location.pathname])

  const breadcrumb = useMemo(() => breadcrumbFromPath(location.pathname), [location.pathname])

  if (!token || !payload) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  if (!INTERNAL_ROLES.has(payload.role)) {
    return <Navigate to="/portal/home" replace />
  }

  const visibleItems = NAV_ITEMS.filter((item) => item.roles.includes(payload.role))

  function logout() {
    localStorage.removeItem('token')
    navigate('/login', { replace: true })
  }

  return (
    <div className="fp-shell">
      <aside className={`fp-shell__sidebar${menuOpen ? ' fp-shell__sidebar--open' : ''}`}>
        <div className="fp-shell__brand">
          <span className="fp-shell__brand-mark">F</span>
          <span className="fp-shell__brand-text">Fracttal PRM</span>
        </div>
        <nav className="fp-shell__nav" aria-label="Internal admin">
          {visibleItems.map((item) => {
            const Icon = item.icon
            const active = location.pathname === item.to ||
              (item.to !== '/internal/home' && location.pathname.startsWith(item.to + '/'))
            if (!item.enabled) {
              return (
                <span
                  key={item.key}
                  className="fp-nav-item fp-nav-item--disabled"
                  title="Coming soon"
                >
                  <span className="fp-nav-item__icon"><Icon /></span>
                  {item.label}
                  <span style={{ marginLeft: 'auto', fontSize: '0.7em', opacity: 0.7 }}>soon</span>
                </span>
              )
            }
            return (
              <Link
                key={item.key}
                to={item.to}
                className={`fp-nav-item${active ? ' fp-nav-item--active' : ''}`}
              >
                <span className="fp-nav-item__icon"><Icon /></span>
                {item.label}
              </Link>
            )
          })}
        </nav>
      </aside>

      <div className="fp-shell__main">
        <header className="fp-shell__header">
          <div className="fp-shell__header-left">
            <button
              type="button"
              className="fp-shell__hamburger"
              aria-label="Toggle navigation"
              onClick={() => setMenuOpen((v) => !v)}
            >
              ☰
            </button>
            <div className="fp-breadcrumb">
              <span>Channel Ops</span>
              <span className="fp-breadcrumb__sep">/</span>
              <span className="fp-breadcrumb__current">{breadcrumb}</span>
            </div>
          </div>
          <div className="fp-shell__header-right">
            <span
              style={{
                fontSize: 'var(--fp-fs-xs)',
                padding: '2px 8px',
                borderRadius: 12,
                background: 'var(--fp-primary, #1A6EBB)',
                color: '#fff',
                fontWeight: 600,
              }}
              title={payload.role}
            >
              {ROLE_LABEL[payload.role] || payload.role}
            </span>
            <span className="fp-shell__user-email">{payload.email}</span>
            <button type="button" className="fp-btn fp-btn--ghost fp-btn--sm" onClick={logout}>
              Log out
            </button>
          </div>
        </header>

        <main className="fp-shell__content">
          <Outlet context={{ payload, token }} />
        </main>
      </div>
    </div>
  )
}
