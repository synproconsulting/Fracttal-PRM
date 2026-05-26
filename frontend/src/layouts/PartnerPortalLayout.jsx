import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const PARTNER_ROLES = new Set(['partner_user', 'partner_admin'])

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
const IconUser = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </svg>
)
const IconDoc = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6" />
  </svg>
)
const IconDeal = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    <path d="M9 22V12h6v10" />
  </svg>
)
const IconPipeline = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M3 12h4l3-9 4 18 3-9h4" />
  </svg>
)
const IconCash = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="2" y="6" width="20" height="12" rx="2" />
    <circle cx="12" cy="12" r="2.5" />
  </svg>
)
const IconBook = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
  </svg>
)
const IconBox = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
    <path d="M3.27 6.96L12 12l8.73-5.04" />
    <path d="M12 22V12" />
  </svg>
)
const IconHelp = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="10" />
    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
)

const NAV_ITEMS = [
  { label: 'Home', to: '/portal/home', icon: IconHome, enabled: true },
  { label: 'My Profile', to: '/portal/profile', icon: IconUser, enabled: true },
  { label: 'Documents', to: '/portal/documents', icon: IconDoc, enabled: true },
  { label: 'Register a Deal', to: '/portal/deals/new', icon: IconDeal, enabled: true },
  { label: 'My Pipeline', to: '/portal/deals', icon: IconPipeline, enabled: true },
  { label: 'My Quotes', to: '/portal/quotes', icon: IconDoc, enabled: true },
  { label: 'Commissions', to: '/portal/commissions', icon: IconCash, enabled: true },
  { label: 'Training', to: '/portal/training', icon: IconBook, enabled: false },
  { label: 'Assets', to: '/portal/assets', icon: IconBox, enabled: false },
  { label: 'Support', to: '/portal/support', icon: IconHelp, enabled: false },
]

function breadcrumbFromPath(pathname) {
  const map = {
    '/portal/home': 'Home',
    '/portal/profile': 'My Profile',
    '/portal/documents': 'Documents',
    '/portal/deals': 'My Pipeline',
    '/portal/deals/new': 'Register a Deal',
    '/portal/commissions': 'Commissions',
    '/portal/quotes': 'My Quotes',
  }
  if (map[pathname]) return map[pathname]
  if (pathname.startsWith('/portal/deals/') && pathname.endsWith('/edit')) return 'Edit Deal'
  if (pathname.startsWith('/portal/deals/')) return 'Deal Detail'
  if (pathname.startsWith('/portal/')) {
    const seg = pathname.split('/').slice(-1)[0]
    return seg ? seg.charAt(0).toUpperCase() + seg.slice(1) : 'Portal'
  }
  return 'Portal'
}

export default function PartnerPortalLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const token = localStorage.getItem('token')
  const payload = token ? decodeJwt(token) : null
  const [orgName, setOrgName] = useState(null)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    if (!payload?.partner_org_id) return
    fetch(`${API}/partners/${payload.partner_org_id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) setOrgName(data.legal_name || data.dba_name || null)
      })
      .catch(() => {})
  }, [payload?.partner_org_id, token])

  // Close mobile menu when navigating
  useEffect(() => { setMenuOpen(false) }, [location.pathname])

  const breadcrumb = useMemo(() => breadcrumbFromPath(location.pathname), [location.pathname])

  if (!token || !payload) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  if (!PARTNER_ROLES.has(payload.role)) {
    return <Navigate to="/internal/applications" replace />
  }

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
        <nav className="fp-shell__nav" aria-label="Partner portal">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            const active = location.pathname === item.to ||
              (item.to !== '/portal/home' && location.pathname.startsWith(item.to + '/'))
            if (!item.enabled) {
              return (
                <span key={item.label} className="fp-nav-item fp-nav-item--disabled" title="Coming soon">
                  <span className="fp-nav-item__icon"><Icon /></span>
                  {item.label}
                </span>
              )
            }
            return (
              <Link
                key={item.label}
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
              <span>Partner Portal</span>
              <span className="fp-breadcrumb__sep">/</span>
              <span className="fp-breadcrumb__current">{breadcrumb}</span>
            </div>
          </div>
          <div className="fp-shell__header-right">
            {orgName && (
              <span className="fp-shell__user-email" style={{ fontWeight: 600, color: 'var(--fp-text)' }}>
                {orgName}
              </span>
            )}
            <span className="fp-shell__user-email">{payload.email}</span>
            <button type="button" className="fp-btn fp-btn--ghost fp-btn--sm" onClick={logout}>
              Log out
            </button>
          </div>
        </header>

        <main className="fp-shell__content">
          <Outlet context={{ payload, orgName, token }} />
        </main>
      </div>
    </div>
  )
}
