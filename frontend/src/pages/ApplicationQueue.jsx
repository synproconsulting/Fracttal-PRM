import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { SortableTh } from '../components/SortableTh.jsx'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

// Tinted-background scheme per AD-27. Tokens match PROJECT_CONTEXT.md §7
// (success / warning / danger families). InternalQuotes.jsx is the canonical
// reference.
const STATUS_TONE = {
  draft:         { bg: '#F5F7FA', fg: '#555' },
  submitted:     { bg: '#E6EEF7', fg: '#1A6EBB' },
  under_review:  { bg: '#FEFCE8', fg: '#B7791F' },
  info_required: { bg: '#FEFCE8', fg: '#B7791F' },
  approved:      { bg: '#E6F4EA', fg: '#2E7D32' },
  rejected:      { bg: '#FEECEC', fg: '#C62828' },
}

const STATUS_LABELS = {
  draft: 'Draft',
  submitted: 'Submitted',
  under_review: 'Under Review',
  info_required: 'Info Required',
  approved: 'Approved',
  rejected: 'Rejected',
}

function StatusBadge({ status }) {
  const tone = STATUS_TONE[status] || { bg: '#F5F7FA', fg: '#555' }
  return (
    <span
      style={{
        background: tone.bg,
        color: tone.fg,
        padding: '2px 10px',
        borderRadius: 12,
        fontSize: 12,
        fontWeight: 600,
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
  const [exporting, setExporting] = useState(false)
  const [sort, setSort] = useState({ field: 'created_at', dir: 'desc' })
  const navigate = useNavigate()
  const token = localStorage.getItem('token')

  function toggleSort(field) {
    setSort((s) => s.field === field
      ? { field, dir: s.dir === 'asc' ? 'desc' : 'asc' }
      : { field, dir: 'asc' })
  }

  useEffect(() => {
    setLoading(true)
    setError(null)
    const params = new URLSearchParams()
    if (statusFilter) params.set('status', statusFilter)
    params.set('sort_by', sort.field)
    params.set('sort_dir', sort.dir)
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
  }, [statusFilter, token, sort])

  const filtered = applications.filter((a) => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      (a.legal_name || '').toLowerCase().includes(q) ||
      (a.applicant_email || '').toLowerCase().includes(q) ||
      (a.applicant_name || '').toLowerCase().includes(q)
    )
  })

  async function exportCSV() {
    setExporting(true)
    try {
      const r = await fetch(`${API}/applications?export=csv`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'applications_export.csv'
      document.body.appendChild(a); a.click(); document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('CSV export error:', e); setError(e.message)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div style={{ padding: '24px 32px', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h1 style={{ margin: 0 }}>Partner Applications</h1>
        <button type="button" onClick={exportCSV} disabled={exporting}
                style={{ fontSize: '0.75rem', padding: '4px 10px', border: '1px solid #CBD5E0', borderRadius: 4, backgroundColor: 'white', color: '#718096', cursor: 'pointer', fontWeight: 400 }}>
          {exporting ? 'Exporting...' : 'Export CSV'}
        </button>
      </div>

      <section className="fp-card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }}
          >
            <option value="">All statuses</option>
            <option value="submitted">Submitted</option>
            <option value="under_review">Under Review</option>
            <option value="info_required">Info Required</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>
          <input
            placeholder="Search by company, applicant, or email…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ flex: 1, minWidth: 200, padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }}
          />
        </div>
      </section>

      {loading && <p>Loading…</p>}
      {error && <p style={{ color: '#c0392b' }}>Could not load applications: {error}</p>}

      {!loading && !error && filtered.length === 0 && (
        <p style={{ color: '#777' }}>No applications pending review.</p>
      )}

      {!loading && !error && filtered.length > 0 && (
        <section className="fp-card">
          <table className="fp-table">
            <thead>
              <tr>
                <SortableTh field="company_name" sort={sort} onSort={toggleSort}>Company</SortableTh>
                <SortableTh field="applicant_name" sort={sort} onSort={toggleSort}>Applicant</SortableTh>
                <SortableTh field="contact_email" sort={sort} onSort={toggleSort}>Email</SortableTh>
                <th>Categories</th>
                <SortableTh field="submitted_at" sort={sort} onSort={toggleSort}>Submitted</SortableTh>
                <SortableTh field="status" sort={sort} onSort={toggleSort}>Status</SortableTh>
                <th>Days</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((a) => (
                <tr
                  key={a.id}
                  onClick={() => navigate(`/internal/applications/${a.id}`)}
                  style={{ cursor: 'pointer' }}
                >
                  <td>{a.legal_name || '—'}</td>
                  <td>{a.applicant_name || '—'}</td>
                  <td>{a.applicant_email || '—'}</td>
                  <td>
                    {Array.isArray(a.requested_categories) && a.requested_categories.length > 0
                      ? a.requested_categories.join(', ')
                      : '—'}
                  </td>
                  <td>
                    {a.submitted_at ? new Date(a.submitted_at).toLocaleDateString() : '—'}
                  </td>
                  <td>
                    <StatusBadge status={a.status} />
                  </td>
                  <td>{daysSince(a.submitted_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}
