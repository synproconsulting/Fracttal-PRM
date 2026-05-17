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
  if (INTERNAL_ROLES.has(role)) return '/internal/applications'
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
    <div style={{ maxWidth: 360, margin: '80px auto', padding: '0 20px', fontFamily: 'system-ui, sans-serif' }}>
      <h1 style={{ color: '#102a43', marginBottom: 8 }}>Sign in</h1>
      <p style={{ color: '#555', marginBottom: 24, fontSize: 14 }}>
        Use the credentials you set when accepting your invitation.
      </p>
      <form onSubmit={onSubmit}>
        <label style={{ display: 'block', marginBottom: 12, fontSize: 13, color: '#333' }}>
          Email
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{ width: '100%', padding: 10, marginTop: 4, fontSize: 14, border: '1px solid #ccc', borderRadius: 4 }}
          />
        </label>
        <label style={{ display: 'block', marginBottom: 16, fontSize: 13, color: '#333' }}>
          Password
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{ width: '100%', padding: 10, marginTop: 4, fontSize: 14, border: '1px solid #ccc', borderRadius: 4 }}
          />
        </label>
        {error && (
          <div style={{ color: '#c0392b', marginBottom: 12, fontSize: 13 }}>{error}</div>
        )}
        <button
          type="submit"
          disabled={loading}
          style={{
            width: '100%',
            padding: 12,
            background: loading ? '#90caf9' : '#1976d2',
            color: 'white',
            border: 'none',
            borderRadius: 4,
            fontSize: 14,
            fontWeight: 500,
            cursor: loading ? 'wait' : 'pointer',
          }}
        >
          {loading ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <p style={{ marginTop: 20, fontSize: 13, color: '#666' }}>
        Not yet a partner? <Link to="/register">Apply to become a Fracttal Distribution Partner</Link>
      </p>
    </div>
  )
}
