import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const PARTNER_ROLES = new Set(['partner_user', 'partner_admin'])
const INTERNAL_ROLES = new Set(['channel_manager', 'channel_ops_admin', 'system_admin'])

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

export function destinationForRole(role) {
  if (PARTNER_ROLES.has(role)) return '/portal/home'
  if (INTERNAL_ROLES.has(role)) return '/internal/home'
  return '/'
}

export default function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function onSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const resp = await fetch(`${API}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const data = await resp.json().catch(() => ({}))
      if (!resp.ok) {
        throw new Error(data.detail || `Login failed (HTTP ${resp.status})`)
      }
      localStorage.setItem('token', data.access_token)
      const payload = decodeJwt(data.access_token)
      const role = payload?.role
      const fromState = location.state && location.state.from
      const dest = fromState || destinationForRole(role)
      navigate(dest, { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fp-auth-page">
      <div className="fp-auth-card">
        <div className="fp-auth-card__brand">
          <span className="fp-auth-card__brand-mark">F</span>
          <span className="fp-auth-card__brand-text">Fracttal PRM</span>
        </div>
        <h1 className="fp-auth-card__title">Sign in</h1>
        <p className="fp-auth-card__subtitle">
          Use the credentials you set when accepting your invitation.
        </p>
        <form onSubmit={onSubmit} noValidate>
          <div className="fp-field">
            <input
              id="login-email"
              type="email"
              required
              autoComplete="email"
              placeholder=" "
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <label htmlFor="login-email">Email</label>
          </div>
          <div className="fp-field">
            <input
              id="login-password"
              type="password"
              required
              autoComplete="current-password"
              placeholder=" "
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <label htmlFor="login-password">Password</label>
          </div>
          {error && (
            <div className="fp-alert fp-alert--danger">{error}</div>
          )}
          <button
            type="submit"
            disabled={loading}
            className="fp-btn fp-btn--primary fp-btn--block"
          >
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <p style={{ marginTop: 24, fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)', textAlign: 'center' }}>
          Not yet a partner? <Link to="/register" style={{ color: 'var(--fp-primary)', textDecoration: 'none', fontWeight: 600 }}>Apply to become a Fracttal Distribution Partner</Link>
        </p>
      </div>
    </div>
  )
}
