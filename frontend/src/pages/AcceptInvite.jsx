import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

export default function AcceptInvite() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const token = params.get('token')

  const [fullName, setFullName] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!token) {
      setError('Missing invitation token. Please use the link from your invitation email.')
    }
  }, [token])

  async function onSubmit(e) {
    e.preventDefault()
    setError(null)
    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    setLoading(true)
    try {
      const resp = await fetch(`${API}/auth/accept-invite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, password, full_name: fullName || null }),
      })
      const data = await resp.json().catch(() => ({}))
      if (resp.status === 404) {
        throw new Error('This invitation is not recognised. Please request a new one from your Fracttal contact.')
      }
      if (resp.status === 400) {
        throw new Error('This invitation has expired or already been used.')
      }
      if (resp.status === 409) {
        throw new Error('An account already exists for this email. Please sign in instead.')
      }
      if (!resp.ok) {
        throw new Error(data.detail || `Could not accept invitation (HTTP ${resp.status})`)
      }
      localStorage.setItem('token', data.access_token)
      navigate('/portal/home', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 420, margin: '80px auto', padding: '0 20px', fontFamily: 'system-ui, sans-serif' }}>
      <h1 style={{ color: '#102a43', marginBottom: 8 }}>Accept your invitation</h1>
      <p style={{ color: '#555', marginBottom: 24, fontSize: 14 }}>
        Set a password to activate your Fracttal partner portal account.
      </p>
      <form onSubmit={onSubmit}>
        <label style={{ display: 'block', marginBottom: 12, fontSize: 13, color: '#333' }}>
          Full name
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            style={{ width: '100%', padding: 10, marginTop: 4, fontSize: 14, border: '1px solid #ccc', borderRadius: 4 }}
          />
        </label>
        <label style={{ display: 'block', marginBottom: 12, fontSize: 13, color: '#333' }}>
          Password
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{ width: '100%', padding: 10, marginTop: 4, fontSize: 14, border: '1px solid #ccc', borderRadius: 4 }}
          />
        </label>
        <label style={{ display: 'block', marginBottom: 16, fontSize: 13, color: '#333' }}>
          Confirm password
          <input
            type="password"
            required
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            style={{ width: '100%', padding: 10, marginTop: 4, fontSize: 14, border: '1px solid #ccc', borderRadius: 4 }}
          />
        </label>
        {error && (
          <div style={{ color: '#c0392b', marginBottom: 12, fontSize: 13 }}>{error}</div>
        )}
        <button
          type="submit"
          disabled={loading || !token}
          style={{
            width: '100%',
            padding: 12,
            background: loading || !token ? '#90caf9' : '#1976d2',
            color: 'white',
            border: 'none',
            borderRadius: 4,
            fontSize: 14,
            fontWeight: 500,
            cursor: loading || !token ? 'not-allowed' : 'pointer',
          }}
        >
          {loading ? 'Activating…' : 'Activate account'}
        </button>
      </form>
    </div>
  )
}
