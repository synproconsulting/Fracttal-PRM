import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

// FPRM-456 — keep in sync with backend/password_policy.py (server enforces 422).
export const PASSWORD_POLICY_HINT =
  'Password must be at least 12 characters and include an uppercase letter, a lowercase letter, and a digit.'

export function isPasswordCompliant(pw) {
  return (
    typeof pw === 'string' && pw.length >= 12 &&
    /[A-Z]/.test(pw) && /[a-z]/.test(pw) && /\d/.test(pw)
  )
}

export default function ResetPassword() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const [newPassword, setNewPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [missingToken, setMissingToken] = useState(false)

  useEffect(() => {
    if (!token) setMissingToken(true)
  }, [token])

  async function onSubmit(e) {
    e.preventDefault()
    setError(null)
    // FPRM-456 — mirror the server-side policy (final enforcement is the API's 422).
    if (!isPasswordCompliant(newPassword)) {
      setError(PASSWORD_POLICY_HINT)
      return
    }
    if (newPassword !== confirm) {
      setError('Passwords do not match.')
      return
    }
    setLoading(true)
    try {
      const resp = await fetch(`${API}/auth/password-reset/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: newPassword }),
      })
      const data = await resp.json().catch(() => ({}))
      if (!resp.ok) {
        throw new Error(data.detail || `Reset failed (HTTP ${resp.status})`)
      }
      navigate('/login', {
        replace: true,
        state: { resetSuccess: 'Password reset successfully. Please log in.' },
      })
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
        <h1 className="fp-auth-card__title">Reset password</h1>
        {missingToken ? (
          <div className="fp-alert fp-alert--danger" style={{ marginTop: 16 }}>
            Missing reset token. Use the link from your reset email.
          </div>
        ) : (
          <form onSubmit={onSubmit} noValidate>
            <div className="fp-field">
              <input
                id="reset-new"
                type="password"
                required
                autoComplete="new-password"
                placeholder=" "
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
              <label htmlFor="reset-new">New password</label>
            </div>
            <p style={{ marginTop: -6, marginBottom: 12, fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>
              {PASSWORD_POLICY_HINT}
            </p>
            <div className="fp-field">
              <input
                id="reset-confirm"
                type="password"
                required
                autoComplete="new-password"
                placeholder=" "
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
              />
              <label htmlFor="reset-confirm">Confirm password</label>
            </div>
            {error && <div className="fp-alert fp-alert--danger">{error}</div>}
            <button
              type="submit"
              disabled={loading || !newPassword || !confirm}
              className="fp-btn fp-btn--primary fp-btn--block"
            >
              {loading ? 'Resetting…' : 'Reset Password'}
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
