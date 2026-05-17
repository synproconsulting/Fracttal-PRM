import { useEffect, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const STATUS_TONE = {
  draft: 'fp-badge--neutral',
  submitted: 'fp-badge--info',
  under_review: 'fp-badge--warning',
  info_required: 'fp-badge--warning',
  approved: 'fp-badge--success',
  rejected: 'fp-badge--danger',
  expired: 'fp-badge--neutral',
}

const STATUS_LABEL = {
  draft: 'Draft',
  submitted: 'Submitted',
  under_review: 'Under review',
  info_required: 'Info required',
  approved: 'Approved',
  rejected: 'Rejected',
  expired: 'Expired',
}

function StatusBadge({ status }) {
  return (
    <span className={`fp-badge ${STATUS_TONE[status] || 'fp-badge--neutral'}`}>
      {STATUS_LABEL[status] || status}
    </span>
  )
}

function formatMoney(value) {
  if (value === null || value === undefined || value === '') return '—'
  const num = Number(value)
  if (!Number.isFinite(num)) return '—'
  return `$${num.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

function formatDate(value) {
  if (!value) return '—'
  try { return new Date(value).toLocaleDateString() } catch { return value }
}

export default function DealList() {
  const ctx = useOutletContext() || {}
  const token = ctx.token || localStorage.getItem('token')
  const [deals, setDeals] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [toast, setToast] = useState(null)

  useEffect(() => {
    const msg = sessionStorage.getItem('deal_submitted_toast')
    if (msg) {
      setToast(msg)
      sessionStorage.removeItem('deal_submitted_toast')
      setTimeout(() => setToast(null), 4500)
    }
  }, [])

  useEffect(() => {
    if (!token) return
    setLoading(true)
    fetch(`${API}/deal-registrations`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        if (!r.ok) {
          const body = await r.json().catch(() => ({}))
          throw new Error(body.detail || `HTTP ${r.status}`)
        }
        return r.json()
      })
      .then((data) => setDeals(data.items || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [token])

  return (
    <div>
      <div className="fp-page-header">
        <h1 className="fp-page-title">My Pipeline</h1>
        <Link to="/portal/deals/new" className="fp-btn fp-btn--primary">
          Register a deal
        </Link>
      </div>

      {toast && (
        <div className="fp-alert fp-alert--success" style={{ marginBottom: 16 }}>{toast}</div>
      )}

      {error && (
        <div className="fp-alert fp-alert--danger">{error}</div>
      )}

      {loading && <div className="fp-card" style={{ color: 'var(--fp-text-secondary)' }}>Loading deals…</div>}

      {!loading && deals.length === 0 && !error && (
        <div className="fp-card" style={{ textAlign: 'center', padding: 48 }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🤝</div>
          <h2 className="fp-section-title" style={{ marginBottom: 6 }}>No deals yet</h2>
          <p style={{ color: 'var(--fp-text-secondary)', marginBottom: 20 }}>
            Register your first deal to start the protection and approval process.
          </p>
          <Link to="/portal/deals/new" className="fp-btn fp-btn--primary">Register your first deal</Link>
        </div>
      )}

      {!loading && deals.length > 0 && (
        <table className="fp-table">
          <thead>
            <tr>
              <th>Deal</th>
              <th>Customer</th>
              <th>Status</th>
              <th>Est. value</th>
              <th>Submitted</th>
            </tr>
          </thead>
          <tbody>
            {deals.map((d) => {
              const editable = d.status === 'draft' || d.status === 'info_required'
              const linkTo = editable
                ? `/portal/deals/${d.id}/edit`
                : `/portal/deals/${d.id}/edit`
              return (
                <tr key={d.id}>
                  <td>
                    <Link to={linkTo} style={{ color: 'var(--fp-primary)', fontWeight: 600, textDecoration: 'none' }}>
                      {d.deal_name || '(unnamed)'}
                    </Link>
                  </td>
                  <td>{d.customer_name || '—'}</td>
                  <td><StatusBadge status={d.status} /></td>
                  <td>{formatMoney(d.estimated_deal_value)}</td>
                  <td>{formatDate(d.submitted_at)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}
