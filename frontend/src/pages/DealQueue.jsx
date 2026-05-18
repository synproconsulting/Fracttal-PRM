import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

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

const TABS = [
  { key: 'all', label: 'All', filter: null },
  { key: 'submitted', label: 'Submitted', filter: 'submitted' },
  { key: 'under_review', label: 'Under review', filter: 'under_review' },
  { key: 'approved', label: 'Approved', filter: 'approved' },
  { key: 'rejected', label: 'Rejected', filter: 'rejected' },
]

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

export default function DealQueue() {
  const token = localStorage.getItem('token')
  const [tab, setTab] = useState('submitted')
  const [deals, setDeals] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actionSaving, setActionSaving] = useState(false)

  const activeFilter = useMemo(() => TABS.find((t) => t.key === tab)?.filter, [tab])

  function reload() {
    if (!token) return
    setLoading(true)
    setError(null)
    const url = activeFilter
      ? `${API}/internal/deals?status=${activeFilter}&limit=200`
      : `${API}/internal/deals?limit=200`
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
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
  }

  useEffect(() => { reload() /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [tab])

  async function startReview(deal) {
    setActionSaving(true)
    try {
      const r = await fetch(`${API}/internal/deals/${deal.id}/start-review`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${r.status}`)
      }
      reload()
    } catch (e) {
      setError(e.message)
    } finally {
      setActionSaving(false)
    }
  }

  return (
    <div className="fp-page">
      <div className="fp-page-header">
        <h1 className="fp-page-title">Deal Queue</h1>
      </div>

      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid var(--fp-border)' }}>
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            style={{
              border: 'none',
              background: 'transparent',
              padding: '10px 16px',
              cursor: 'pointer',
              fontSize: 'var(--fp-fs-base)',
              fontWeight: tab === t.key ? 'var(--fp-fw-semibold)' : 'var(--fp-fw-medium)',
              color: tab === t.key ? 'var(--fp-primary)' : 'var(--fp-text-secondary)',
              borderBottom: tab === t.key ? '2px solid var(--fp-primary)' : '2px solid transparent',
              marginBottom: -1,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {error && <div className="fp-alert fp-alert--danger">{error}</div>}

      {loading && <div className="fp-card" style={{ color: 'var(--fp-text-secondary)' }}>Loading deals…</div>}

      {!loading && deals.length === 0 && !error && (
        <div className="fp-card" style={{ textAlign: 'center', padding: 40, color: 'var(--fp-text-secondary)' }}>
          No deals in this view.
        </div>
      )}

      {!loading && deals.length > 0 && (
        <table className="fp-table">
          <thead>
            <tr>
              <th>Deal</th>
              <th>Partner org</th>
              <th>Customer</th>
              <th>Status</th>
              <th>Est. value</th>
              <th>Submitted</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {deals.map((d) => (
              <tr key={d.id}>
                <td>
                  <Link to={`/internal/deals/${d.id}`}
                        style={{ color: 'var(--fp-primary)', fontWeight: 600, textDecoration: 'none' }}>
                    {d.deal_name || '(unnamed)'}
                  </Link>
                </td>
                <td style={{ fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>
                  {d.partner_legal_name || (d.partner_org_id ? `${d.partner_org_id.slice(0, 8)}…` : '—')}
                </td>
                <td>{d.customer_name || '—'}</td>
                <td><StatusBadge status={d.status} /></td>
                <td>{formatMoney(d.estimated_deal_value)}</td>
                <td>{formatDate(d.submitted_at)}</td>
                <td>
                  {d.status === 'submitted' && (
                    <button
                      type="button"
                      className="fp-btn fp-btn--primary fp-btn--sm"
                      disabled={actionSaving}
                      onClick={() => startReview(d)}
                    >
                      Start review
                    </button>
                  )}
                  {d.status !== 'submitted' && (
                    <Link to={`/internal/deals/${d.id}`}
                          className="fp-btn fp-btn--ghost fp-btn--sm"
                          style={{ textDecoration: 'none' }}>
                      Open
                    </Link>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

    </div>
  )
}
