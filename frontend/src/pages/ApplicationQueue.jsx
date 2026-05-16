import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const STATUS_COLORS = {
  draft: '#9e9e9e',
  submitted: '#2196f3',
  in_review: '#ffc107',
  info_required: '#ff9800',
  approved: '#4caf50',
  rejected: '#f44336',
}

const STATUS_LABELS = {
  draft: 'Draft',
  submitted: 'Submitted',
  in_review: 'In Review',
  info_required: 'Info Required',
  approved: 'Approved',
  rejected: 'Rejected',
}

function StatusBadge({ status }) {
  return (
    <span
      style={{
        background: STATUS_COLORS[status] || '#9e9e9e',
        color: 'white',
        padding: '2px 10px',
        borderRadius: 12,
        fontSize: 12,
        fontWeight: 500,
      }}
    >
      {STATUS_LABELS[status] || status}
    </span>
  )
}

function daysSince(date) {
  if (!date) return '—'
  const ms = Date.now() - new Date(date).getTime()
  if (Number.isNaN(ms)) return '—'
  return Math.max(0, Math.floor(ms / 86400000))
}

export default function ApplicationQueue() {
  const [applications, setApplications] = useState([])
  const [statusFilter, setStatusFilter] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const navigate = useNavigate()
  const token = localStorage.getItem('token')

  useEffect(() => {
    setLoading(true)
    setError(null)
    const params = new URLSearchParams()
    if (statusFilter) params.set('status', statusFilter)
    fetch(`${API}/applications?${params.toString()}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data) => setApplications(Array.isArray(data) ? data : data.items || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [statusFilter, token])

  const filtered = applications.filter((a) => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      (a.legal_name || '').toLowerCase().includes(q) ||
      (a.applicant_email || '').toLowerCase().includes(q) ||
      (a.applicant_name || '').toLowerCase().includes(q)
    )
  })

  return (
    <div style={{ padding: '24px 32px', fontFamily: 'system-ui, sans-serif' }}>
      <h1>Partner Applications</h1>

      <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center' }}>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          style={{ padding: 8 }}
        >
          <option value="">All statuses</option>
          <option value="submitted">Submitted</option>
          <option value="in_review">In Review</option>
          <option value="info_required">Info Required</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
        <input
          placeholder="Search by company, applicant, or email…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ flex: 1, padding: 8 }}
        />
      </div>

      {loading && <p>Loading…</p>}
      {error && <p style={{ color: '#c0392b' }}>Could not load applications: {error}</p>}

      {!loading && !error && filtered.length === 0 && (
        <p style={{ color: '#777' }}>No applications pending review.</p>
      )}

      {!loading && !error && filtered.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
          <thead>
            <tr style={{ background: '#f5f5f5', textAlign: 'left' }}>
              <th style={{ padding: 10 }}>Company</th>
              <th style={{ padding: 10 }}>Applicant</th>
              <th style={{ padding: 10 }}>Email</th>
              <th style={{ padding: 10 }}>Categories</th>
              <th style={{ padding: 10 }}>Submitted</th>
              <th style={{ padding: 10 }}>Status</th>
              <th style={{ padding: 10 }}>Days</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((a) => (
              <tr
                key={a.id}
                onClick={() => navigate(`/internal/applications/${a.id}`)}
                style={{ cursor: 'pointer', borderBottom: '1px solid #eee' }}
              >
                <td style={{ padding: 10 }}>{a.legal_name || '—'}</td>
                <td style={{ padding: 10 }}>{a.applicant_name || '—'}</td>
                <td style={{ padding: 10 }}>{a.applicant_email || '—'}</td>
                <td style={{ padding: 10 }}>
                  {Array.isArray(a.requested_categories) && a.requested_categories.length > 0
                    ? a.requested_categories.join(', ')
                    : '—'}
                </td>
                <td style={{ padding: 10 }}>
                  {a.submitted_at ? new Date(a.submitted_at).toLocaleDateString() : '—'}
                </td>
                <td style={{ padding: 10 }}>
                  <StatusBadge status={a.status} />
                </td>
                <td style={{ padding: 10 }}>{daysSince(a.submitted_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
