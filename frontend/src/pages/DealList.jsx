import { useEffect, useMemo, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { SortableTh } from '../components/SortableTh.jsx'

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

const KANBAN_ORDER = ['draft', 'submitted', 'under_review', 'info_required', 'approved', 'rejected']
const COLUMN_ACCENT = {
  draft: '#94A3B8',
  submitted: '#3B82F6',
  under_review: '#F59E0B',
  info_required: '#8B5CF6',
  approved: '#22C55E',
  rejected: '#EF4444',
}

function decodeJwt(token) {
  try {
    const parts = token.split('.')
    if (parts.length < 2) return null
    const padded = parts[1] + '==='.slice((parts[1].length + 3) % 4)
    const json = atob(padded.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(json)
  } catch (_) { return null }
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

function readInitialView() {
  if (typeof window === 'undefined') return 'list'
  const params = new URLSearchParams(window.location.search)
  return params.get('view') === 'pipeline' ? 'pipeline' : 'list'
}

export default function DealList() {
  const ctx = useOutletContext() || {}
  const token = ctx.token || localStorage.getItem('token')
  const payload = ctx.payload || (token ? decodeJwt(token) : null)
  const partnerOrgId = payload && payload.partner_org_id

  const [viewMode, setViewMode] = useState(readInitialView)
  const [filters, setFilters] = useState({ status: '', from_date: '', to_date: '' })
  const [pipeline, setPipeline] = useState(null)
  const [deals, setDeals] = useState([])
  const [loadingPipeline, setLoadingPipeline] = useState(false)
  const [loadingList, setLoadingList] = useState(false)
  const [error, setError] = useState(null)
  const [toast, setToast] = useState(null)
  const [exporting, setExporting] = useState(false)
  const [sort, setSort] = useState({ field: 'created_at', dir: 'desc' })

  function toggleSort(field) {
    setSort((s) => s.field === field
      ? { field, dir: s.dir === 'asc' ? 'desc' : 'asc' }
      : { field, dir: 'asc' })
  }

  // URL sync (no navigation — just replace state).
  useEffect(() => {
    if (typeof window === 'undefined') return
    const params = new URLSearchParams(window.location.search)
    if (viewMode === 'pipeline') params.set('view', 'pipeline'); else params.delete('view')
    const qs = params.toString()
    window.history.replaceState({}, '', `${window.location.pathname}${qs ? `?${qs}` : ''}`)
  }, [viewMode])

  useEffect(() => {
    const msg = sessionStorage.getItem('deal_submitted_toast')
    if (msg) {
      setToast(msg); sessionStorage.removeItem('deal_submitted_toast')
      setTimeout(() => setToast(null), 4500)
    }
  }, [])

  // Filter-only query string (pipeline endpoint doesn't accept sort params --
  // it groups by status). The list-view fetch adds sort_by / sort_dir
  // separately.
  const queryStr = useMemo(() => {
    const p = new URLSearchParams()
    if (filters.status) p.set('status', filters.status)
    if (filters.from_date) p.set('from_date', filters.from_date)
    if (filters.to_date) p.set('to_date', filters.to_date)
    const q = p.toString(); return q ? `?${q}` : ''
  }, [filters])

  const listQueryStr = useMemo(() => {
    const p = new URLSearchParams()
    if (filters.status) p.set('status', filters.status)
    if (filters.from_date) p.set('from_date', filters.from_date)
    if (filters.to_date) p.set('to_date', filters.to_date)
    p.set('sort_by', sort.field)
    p.set('sort_dir', sort.dir)
    return `?${p.toString()}`
  }, [filters, sort])

  function fetchPipeline() {
    if (!token || !partnerOrgId) return
    setLoadingPipeline(true); setError(null)
    fetch(`${API}/partners/${partnerOrgId}/pipeline${queryStr}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        if (!r.ok) {
          const body = await r.json().catch(() => ({}))
          throw new Error(body.detail || `HTTP ${r.status}`)
        }
        return r.json()
      })
      .then((d) => setPipeline(d))
      .catch((e) => setError(e.message))
      .finally(() => setLoadingPipeline(false))
  }

  function fetchList() {
    if (!token) return
    setLoadingList(true); setError(null)
    fetch(`${API}/deal-registrations${listQueryStr}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (r) => {
        if (!r.ok) {
          const body = await r.json().catch(() => ({}))
          throw new Error(body.detail || `HTTP ${r.status}`)
        }
        return r.json()
      })
      .then((data) => setDeals(data.items || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoadingList(false))
  }

  // Both views need pipeline (for the summary strip); list view also fetches the list endpoint.
  useEffect(() => { fetchPipeline() /* eslint-disable-line */ }, [partnerOrgId, queryStr])
  useEffect(() => { if (viewMode === 'list') fetchList() /* eslint-disable-line */ }, [viewMode, listQueryStr])

  // Pipeline value for a deal = sum of `include_in_pipeline` quote totals
  // (server-aggregated as `pipeline_total`, excluding expired/cancelled
  // quotes per the helper in deal_registrations_router). NO fallback to
  // estimated_deal_value -- pipeline must reflect actual quoted-and-opted-in
  // value only; estimated_deal_value is the partner's guess at deal sign-on
  // and renders in its own column. Deals with no pipeline-included quote
  // contribute 0 to summary/column totals; list rows render '—'.
  function dealPipelineValue(d) {
    if (d && d.pipeline_total != null) return Number(d.pipeline_total) || 0
    return 0
  }

  function formatPipelineCell(d) {
    return d?.pipeline_total != null ? formatMoney(Number(d.pipeline_total)) : '—'
  }

  const summary = useMemo(() => {
    if (!pipeline) return { total: 0, totalValue: 0, totalEstValue: 0, anyEstValue: false, approvedValue: 0, infoRequired: 0 }
    const all = []
    // KANBAN_ORDER intentionally excludes lost/withdrawn/won/expired/cancelled
    // — those buckets are absent here, so summing across `all` already
    // honours the "exclude lost/withdrawn/won" rule the spec calls for.
    KANBAN_ORDER.forEach((s) => (pipeline[s] || []).forEach((d) => all.push(d)))
    const approved = pipeline.approved || []
    const infoRequired = (pipeline.info_required || []).length
    const totalValue = all.reduce((acc, d) => acc + dealPipelineValue(d), 0)
    const approvedValue = approved.reduce((acc, d) => acc + dealPipelineValue(d), 0)
    // Partner-entered estimate. Distinct from pipeline value (which is
    // derived from quotes); a deal can have one without the other. Track
    // whether ANY deal in the visible set had a value so the card can
    // render '—' when no estimates are set anywhere.
    let totalEstValue = 0
    let anyEstValue = false
    for (const d of all) {
      if (d?.estimated_deal_value != null) {
        const v = Number(d.estimated_deal_value)
        if (Number.isFinite(v)) {
          totalEstValue += v
          anyEstValue = true
        }
      }
    }
    return { total: all.length, totalValue, totalEstValue, anyEstValue, approvedValue, infoRequired }
  }, [pipeline])

  async function exportCSV() {
    setExporting(true)
    try {
      const r = await fetch(`${API}/deal-registrations?export=csv`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'deals_export.csv'
      document.body.appendChild(a); a.click(); document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('CSV export error:', e); setError(e.message)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div>
      <div className="fp-page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <h1 className="fp-page-title">My Pipeline</h1>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <div style={{ display: 'flex', border: '1px solid #E0E4EA', borderRadius: 6, overflow: 'hidden' }}>
            <button
              type="button"
              onClick={() => setViewMode('list')}
              style={{
                padding: '6px 12px',
                background: viewMode === 'list' ? '#1A6EBB' : '#fff',
                color: viewMode === 'list' ? '#fff' : '#64748B',
                border: 'none', cursor: 'pointer', fontWeight: 600,
              }}
            >List ☰</button>
            <button
              type="button"
              onClick={() => setViewMode('pipeline')}
              style={{
                padding: '6px 12px',
                background: viewMode === 'pipeline' ? '#1A6EBB' : '#fff',
                color: viewMode === 'pipeline' ? '#fff' : '#64748B',
                border: 'none', cursor: 'pointer', fontWeight: 600,
              }}
            >Pipeline ⬛</button>
          </div>
          <button type="button" onClick={exportCSV} disabled={exporting} style={{ fontSize: '0.75rem', padding: '4px 10px', border: '1px solid #CBD5E0', borderRadius: 4, backgroundColor: 'white', color: '#718096', cursor: 'pointer', fontWeight: 400 }}>{exporting ? 'Exporting...' : 'Export CSV'}</button>
          <Link to="/portal/deals/new" className="fp-btn fp-btn--primary">Register a deal</Link>
        </div>
      </div>

      {/* Filter bar */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center', margin: '12px 0' }}>
        <select value={filters.status} onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))} style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #E0E4EA' }}>
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="submitted">Submitted</option>
          <option value="under_review">Under review</option>
          <option value="info_required">Info required</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
        <input type="date" value={filters.from_date} onChange={(e) => setFilters((f) => ({ ...f, from_date: e.target.value }))} style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #E0E4EA' }} />
        <input type="date" value={filters.to_date} onChange={(e) => setFilters((f) => ({ ...f, to_date: e.target.value }))} style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #E0E4EA' }} />
        <button type="button" onClick={() => setFilters({ status: '', from_date: '', to_date: '' })} style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid #E0E4EA', background: '#fff', cursor: 'pointer' }}>Clear</button>
      </div>

      {/* Pipeline summary strip */}
      <div style={{ background: '#F8FAFC', borderBottom: '1px solid #E0E4EA', padding: '12px 20px', display: 'flex', gap: 32, marginBottom: 16, flexWrap: 'wrap' }}>
        {loadingPipeline ? (
          <div style={{ height: 24, background: 'linear-gradient(90deg, #F1F5F9 25%, #E2E8F0 50%, #F1F5F9 75%)', backgroundSize: '200% 100%', flex: 1, borderRadius: 4 }} />
        ) : (
          <>
            <div><div style={{ fontSize: 11, color: '#64748B', textTransform: 'uppercase', fontWeight: 600 }}>Total Deals</div><div style={{ fontSize: 20, fontWeight: 700 }}>{summary.total}</div></div>
            <div><div style={{ fontSize: 11, color: '#64748B', textTransform: 'uppercase', fontWeight: 600 }}>Total Est. Value</div><div style={{ fontSize: 20, fontWeight: 700 }}>{summary.anyEstValue ? formatMoney(summary.totalEstValue) : '—'}</div></div>
            <div><div style={{ fontSize: 11, color: '#64748B', textTransform: 'uppercase', fontWeight: 600 }}>Pipeline Value</div><div style={{ fontSize: 20, fontWeight: 700 }}>{formatMoney(summary.totalValue)}</div></div>
            <div><div style={{ fontSize: 11, color: '#64748B', textTransform: 'uppercase', fontWeight: 600 }}>Approved Pipeline</div><div style={{ fontSize: 20, fontWeight: 700, color: '#22C55E' }}>{formatMoney(summary.approvedValue)}</div></div>
            <div><div style={{ fontSize: 11, color: '#64748B', textTransform: 'uppercase', fontWeight: 600 }}>Info Required</div><div style={{ fontSize: 20, fontWeight: 700, color: '#8B5CF6' }}>{summary.infoRequired}</div></div>
          </>
        )}
      </div>

      {toast && (
        <div className="fp-alert fp-alert--success" style={{ marginBottom: 16 }}>{toast}</div>
      )}

      {error && (
        <div className="fp-alert fp-alert--danger">{error}</div>
      )}

      {/* Pipeline view */}
      {viewMode === 'pipeline' && (
        <>
          {loadingPipeline && (
            <div className="fp-card" style={{ color: 'var(--fp-text-secondary)' }}>Loading pipeline…</div>
          )}
          {!loadingPipeline && pipeline && (
            <div style={{ display: 'flex', flexDirection: 'row', gap: 12, overflowX: 'auto', paddingBottom: 8 }}>
              {KANBAN_ORDER.map((sk) => {
                const items = pipeline[sk] || []
                const colValue = items.reduce((acc, d) => acc + dealPipelineValue(d), 0)
                return (
                  <div key={sk} style={{ minWidth: 220, flexShrink: 0, background: '#fff', borderLeft: `4px solid ${COLUMN_ACCENT[sk]}`, border: '1px solid #E0E4EA', borderRadius: 6, padding: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <span style={{ fontWeight: 700, fontSize: 14 }}>
                        {STATUS_LABEL[sk]}
                        <span style={{ marginLeft: 6, padding: '2px 8px', background: '#E0E4EA', borderRadius: 12, fontSize: 11, fontWeight: 600 }}>{items.length}</span>
                      </span>
                      <span style={{ fontSize: 12, color: '#64748B' }}>{formatMoney(colValue)}</span>
                    </div>
                    {items.length === 0 ? (
                      <div style={{ fontSize: 12, color: '#94A3B8', fontStyle: 'italic', textAlign: 'center', padding: 16 }}>No deals</div>
                    ) : items.map((d) => (
                      <div key={d.id} style={{ background: '#fff', border: '1px solid #E0E4EA', borderRadius: 6, padding: 12, marginBottom: 8 }}>
                        <div style={{ fontWeight: 700, fontSize: 14, color: '#1E293B' }}>{d.deal_name}</div>
                        <div style={{ fontSize: 12, color: '#64748B' }}>{d.customer_name || '—'}</div>
                        <div style={{ fontSize: 13, color: '#1A6EBB', marginTop: 4 }} title="Pipeline value (sum of quotes opted into pipeline)">
                          Pipeline: {formatPipelineCell(d)}
                        </div>
                        <div style={{ fontSize: 11, color: '#94A3B8' }} title="Estimated deal value (partner's own estimate)">
                          Est: {d.estimated_deal_value != null ? formatMoney(Number(d.estimated_deal_value)) : '—'}
                        </div>
                        <div style={{ fontSize: 12, color: '#64748B' }}>{formatDate(d.estimated_close_date)}</div>
                      </div>
                    ))}
                  </div>
                )
              })}
            </div>
          )}
          {!loadingPipeline && pipeline && summary.total === 0 && (
            <div className="fp-card" style={{ textAlign: 'center', padding: 32, color: '#94A3B8' }}>No deals match your filters.</div>
          )}
        </>
      )}

      {/* List view (existing UI) */}
      {viewMode === 'list' && (
        <>
          {loadingList && <div className="fp-card" style={{ color: 'var(--fp-text-secondary)' }}>Loading deals…</div>}

          {!loadingList && deals.length === 0 && !error && (
            <div className="fp-card" style={{ textAlign: 'center', padding: 48 }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>🤝</div>
              <h2 className="fp-section-title" style={{ marginBottom: 6 }}>No deals yet</h2>
              <p style={{ color: 'var(--fp-text-secondary)', marginBottom: 20 }}>
                Register your first deal to start the protection and approval process.
              </p>
              <Link to="/portal/deals/new" className="fp-btn fp-btn--primary">Register your first deal</Link>
            </div>
          )}

          {!loadingList && deals.length > 0 && (
            <table className="fp-table">
              <thead>
                <tr>
                  <SortableTh field="deal_name" sort={sort} onSort={toggleSort}>Deal</SortableTh>
                  <th>Customer</th>
                  <SortableTh field="status" sort={sort} onSort={toggleSort}>Status</SortableTh>
                  <th>Pipeline</th>
                  <th>Estimated Value</th>
                  <th>Submitted</th>
                </tr>
              </thead>
              <tbody>
                {deals.map((d) => {
                  const linkTo = `/portal/deals/${d.id}`
                  return (
                    <tr key={d.id}>
                      <td>
                        <Link to={linkTo} style={{ color: 'var(--fp-primary)', fontWeight: 600, textDecoration: 'none' }}>
                          {d.deal_name || '(unnamed)'}
                        </Link>
                      </td>
                      <td>{d.customer_name || '—'}</td>
                      <td><StatusBadge status={d.status} /></td>
                      <td>{formatPipelineCell(d)}</td>
                      <td>{d.estimated_deal_value != null ? formatMoney(Number(d.estimated_deal_value)) : '—'}</td>
                      <td>{formatDate(d.submitted_at)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  )
}
