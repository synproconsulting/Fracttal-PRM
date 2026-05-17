import { useEffect, useState } from 'react'
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

const NAV_ITEMS = [
  { label: 'Home', to: '/portal/home', enabled: true },
  { label: 'My Profile', to: '/portal/profile', enabled: true },
  { label: 'Documents', to: '/portal/documents', enabled: true },
  { label: 'My Pipeline', to: '/portal/pipeline', enabled: false },
  { label: 'Register Deal', to: '/portal/deals/new', enabled: false },
  { label: 'Training', to: '/portal/training', enabled: false },
  { label: 'Assets', to: '/portal/assets', enabled: false },
  { label: 'Support', to: '/portal/support', enabled: false },
]

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
    <div style={{ fontFamily: 'system-ui, sans-serif', minHeight: '100vh', background: '#fafafa' }}>
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: '#102a43',
          color: 'white',
          padding: '12px 24px',
          gap: 16,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <button
            aria-label="Toggle navigation"
            onClick={() => setMenuOpen((v) => !v)}
            style={{
              display: 'none',
              background: 'transparent',
              color: 'white',
              border: '1px solid rgba(255,255,255,0.4)',
              padding: '6px 10px',
              borderRadius: 4,
              cursor: 'pointer',
            }}
            className="fprm-hamburger"
          >
            ☰
          </button>
          <strong style={{ fontSize: 18, letterSpacing: 0.5 }}>Fracttal PRM</strong>
          {orgName && (
            <span style={{ opacity: 0.85, fontSize: 14 }}>
              {orgName}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <span style={{ fontSize: 13, opacity: 0.85 }}>{payload.email}</span>
          <button
            onClick={logout}
            style={{
              background: 'transparent',
              border: '1px solid rgba(255,255,255,0.4)',
              color: 'white',
              padding: '6px 12px',
              borderRadius: 4,
              cursor: 'pointer',
              fontSize: 13,
            }}
          >
            Log out
          </button>
        </div>
      </header>

      <div style={{ display: 'flex', minHeight: 'calc(100vh - 56px)' }}>
        <aside
          style={{
            width: 220,
            background: 'white',
            borderRight: '1px solid #e0e0e0',
            padding: '20px 12px',
            display: menuOpen ? 'block' : undefined,
          }}
          className="fprm-sidebar"
        >
          <nav>
            <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {NAV_ITEMS.map((item) => {
                const active = location.pathname === item.to || location.pathname.startsWith(item.to + '/')
                if (!item.enabled) {
                  return (
                    <li key={item.to}>
                      <span
                        style={{
                          display: 'block',
                          padding: '10px 14px',
                          borderRadius: 4,
                          color: '#aaa',
                          fontSize: 14,
                          cursor: 'not-allowed',
                          marginBottom: 2,
                        }}
                        title="Coming soon"
                      >
                        {item.label}
                      </span>
                    </li>
                  )
                }
                return (
                  <li key={item.to}>
                    <Link
                      to={item.to}
                      onClick={() => setMenuOpen(false)}
                      style={{
                        display: 'block',
                        padding: '10px 14px',
                        borderRadius: 4,
                        color: active ? 'white' : '#102a43',
                        background: active ? '#1976d2' : 'transparent',
                        textDecoration: 'none',
                        fontSize: 14,
                        marginBottom: 2,
                      }}
                    >
                      {item.label}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </nav>
        </aside>

        <main style={{ flex: 1, padding: '24px 32px' }}>
          <Outlet context={{ payload, orgName, token }} />
        </main>
      </div>

      <style>{`
        @media (max-width: 720px) {
          .fprm-hamburger { display: inline-block !important; }
          .fprm-sidebar {
            position: absolute;
            z-index: 10;
            display: none;
          }
          .fprm-sidebar[style*="block"] { display: block !important; }
        }
      `}</style>
    </div>
  )
}
