import { useState } from 'react'
import { Link } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  async function onSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const resp = await fetch(`${API}/auth/password-reset/request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      })
      const data = await resp.json().catch(() => ({}))
      if (!resp.ok) {
        throw new Error(data.detail || `Request failed (HTTP ${resp.status})`)
      }
      setSubmitted(true)
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
        <h1 className="fp-auth-card__title">Forgot password</h1>
        <p className="fp-auth-card__subtitle">
          Enter your email and we'll send a link to reset your password.
        </p>
        {submitted ? (
          <div className="fp-alert fp-alert--success" style={{ marginTop: 16 }}>
            If that email is registered, a reset link has been sent. Check your inbox (and spam folder).
          </div>
        ) : (
          <form onSubmit={onSubmit} noValidate>
            <div className="fp-field">
              <input
                id="forgot-email"
                type="email"
                required
                autoComplete="email"
                placeholder=" "
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <label htmlFor="forgot-email">Email</label>
            </div>
            {error && <div className="fp-alert fp-alert--danger">{error}</div>}
            <button
              type="submit"
              disabled={loading || !email}
              className="fp-btn fp-btn--primary fp-btn--block"
            >
              {loading ? 'Sending…' : 'Send Reset Link'}
            </button>
          </form>
        )}
        <p style={{ marginTop: 24, fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)', textAlign: 'center' }}>
          <Link to="/login" style={{ color: 'var(--fp-primary)', textDecoration: 'none', fontWeight: 600 }}>
            ← Back to Login
          </Link>
        </p>
      </div>
    </div>
  )
}
