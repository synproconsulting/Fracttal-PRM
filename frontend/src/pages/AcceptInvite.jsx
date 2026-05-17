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
    <div className="fp-auth-page">
      <div className="fp-auth-card">
        <div className="fp-auth-card__brand">
          <span className="fp-auth-card__brand-mark">F</span>
          <span className="fp-auth-card__brand-text">Fracttal PRM</span>
        </div>
        <h1 className="fp-auth-card__title">Accept your invitation</h1>
        <p className="fp-auth-card__subtitle">
          Set a password to activate your Fracttal partner portal account.
        </p>
        <form onSubmit={onSubmit} noValidate>
          <div className="fp-field">
            <input
              id="invite-name"
              type="text"
              placeholder=" "
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
            />
            <label htmlFor="invite-name">Full name</label>
          </div>
          <div className="fp-field">
            <input
              id="invite-password"
              type="password"
              required
              placeholder=" "
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <label htmlFor="invite-password">Password</label>
          </div>
          <div className="fp-field">
            <input
              id="invite-confirm"
              type="password"
              required
              placeholder=" "
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
            <label htmlFor="invite-confirm">Confirm password</label>
          </div>
          {error && (
            <div className="fp-alert fp-alert--danger">{error}</div>
          )}
          <button
            type="submit"
            disabled={loading || !token}
            className="fp-btn fp-btn--primary fp-btn--block"
          >
            {loading ? 'Activating…' : 'Activate account'}
          </button>
        </form>
      </div>
    </div>
  )
}
