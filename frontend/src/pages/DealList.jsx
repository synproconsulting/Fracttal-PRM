import { useEffect, useMemo, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { SortableTh } from '../components/SortableTh.jsx'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

// Tinted-background status palette per AD-27. StatusBadge renders the
// tint as `${color}22` (alpha) on top of the solid colour for the text.
const STATUS_TONE = {
  draft: '#64748B',
  submitted: '#1A6EBB',
  under_review: '#B7791F',
  info_required: '#B7791F',
  approved: '#2E7D32',
  rejected: '#C62828',
  expired: '#C2410C',
  won: '#2E7D32',
  lost: '#C62828',
  withdrawn: '#64748B',
  cancelled: '#C62828',
}

// "Approved" deals display as "Accepted" — the wording on the partner
// agreement is "accepted", not "approved".
const STATUS_LABEL = {
  draft: 'Draft',
  submitted: 'Submitted',
  under_review: 'Under Review',
  info_required: 'Info Required',
  approved: 'Accepted',
  rejected: 'Rejected',
  expired: 'Expired',
  won: 'Won',
  lost: 'Lost',
  withdrawn: 'Withdrawn',
  cancelled: 'Cancelled',
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
  const color = STATUS_TONE[status] || '#64748B'
  const label = STATUS_LABEL[status] || status
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 12,
      background: `${color}22`,
      color,
      fontSize: 12,
      fontWeight: 600,
    }}>{label}</span>
  )
}

function SummaryCard({ label, value, color = '#1E293B' }) {
  return (
    <div className="fp-card" style={{ flex: 1, minWidth: 140, padding: 14 }}>
      <div style={{ fontSize: 11, color: '#64748B', textTransform: 'uppercase', fontWeight: 600, letterSpacing: 0.5 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color, marginTop: 4 }}>{value}</div>
    </div>
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
  const [filters, setFilters] = useState({ status: '' })
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [search, setSearch] = useState('')
  const [pipeline, setPipeline] = useState(null)
  const [deals, setDeals] = useState([])
  const [loadingPipeline, setLoadingPipeline] = useState(false)
  const [loadingList, setLoadingList] = useState(false)
  const [error, setError] = useState(null)
  const [toast, setToast] = useState(null)
  const [exporting, setExporting] = useState(false)
  const [sort, setSort] = useState({ field: 'submitted_at', dir: 'desc' })

  function toggleSort(field) {
    setSort((s) => s.field === field
      ? { field, dir: s.dir === 'asc' ? 'desc' : 'asc' }
      : { field, dir: 'asc' })
  }

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

  // Filter-only query string for the pipeline endpoint. Both backends
  // support from_date / to_date applied to submitted_at (pipeline has had
  // them since Sprint 14; deal-registrations since PR #175). Date pickers
  // were re-added to the filter bar in PR #177.
  const queryStr = useMemo(() => {
    const p = new URLSearchParams()
    if (filters.status) p.set('status', filters.status)
    if (fromDate) p.set('from_date', fromDate)
    if (toDate) p.set('to_date', toDate)
    const q = p.toString(); return q ? `?${q}` : ''
  }, [filters, fromDate, toDate])

  const listQueryStr = useMemo(() => {
    const p = new URLSearchParams()
    if (filters.status) p.set('status', filters.status)
    if (fromDate) p.set('from_date', fromDate)
    if (toDate) p.set('to_date', toDate)
    p.set('sort_by', sort.field)
    p.set('sort_dir', sort.dir)
    return `?${p.toString()}`
  }, [filters, fromDate, toDate, sort])

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

  useEffect(() => { fetchPipeline() /* eslint-disable-line */ }, [partnerOrgId, queryStr])
  useEffect(() => { if (viewMode === 'list') fetchList() /* eslint-disable-line */ }, [viewMode, listQueryStr])

  function dealPipelineValue(d) {
    if (d && d.pipeline_total != null) return Number(d.pipeline_total) || 0
    return 0
  }

  function formatPipelineCell(d) {
    return d?.pipeline_total != null ? formatMoney(Number(d.pipeline_total)) : '—'
  }

  // Summary cards strip — six aggregates sourced from the list-view
  // `deals` array. Cards render in both views; when only Kanban has been
  // loaded they show 0/— until the user switches to list view (existing
  // fetch logic preserved per prompt).
  const listSummary = useMemo(() => {
    let totalEstValue = 0
    let pipelineValue = 0
    let approvedPipelineValue = 0
    // Won is the SUM of pipeline_total for won deals — not a count. PR #176.
    // anyWonWithPipeline lets the card distinguish "no data" (render '—')
    // from "every won deal has zero pipeline" (render $0).
    let wonPipelineValue = 0
    let anyWonWithPipeline = false
    let infoRequired = 0
    for (const d of deals) {
      if (d.estimated_deal_value != null) {
        const v = Number(d.estimated_deal_value)
        if (Number.isFinite(v)) totalEstValue += v
      }
      if (d.pipeline_total != null) {
        const p = Number(d.pipeline_total)
        if (Number.isFinite(p)) {
          pipelineValue += p
          if (d.status === 'approved') approvedPipelineValue += p
          if (d.status === 'won') {
            wonPipelineValue += p
            anyWonWithPipeline = true
          }
        }
      }
      if (d.status === 'info_required') infoRequired += 1
    }
    return {
      total: deals.length,
      totalEstValue,
      pipelineValue,
      approvedPipelineValue,
      wonPipelineValue,
      anyWonWithPipeline,
      infoRequired,
    }
  }, [deals])

  const pipelineSummary = useMemo(() => {
    if (!pipeline) return { total: 0 }
    const all = []
    KANBAN_ORDER.forEach((s) => (pipeline[s] || []).forEach((d) => all.push(d)))
    return { total: all.length }
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

      {/* Summary cards strip — six cards sourced from `deals`, ABOVE the
          filter bar per AD-31 (data-aggregation page). */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
        <SummaryCard label="Total Deals" value={listSummary.total} />
        <SummaryCard label="Total Est. Value" value={formatMoney(listSummary.totalEstValue)} />
        <SummaryCard label="Pipeline Value" value={formatMoney(listSummary.pipelineValue)} color="#1A6EBB" />
        <SummaryCard label="Accepted Pipeline" value={formatMoney(listSummary.approvedPipelineValue)} color="#2E7D32" />
        <SummaryCard label="Won" value={listSummary.anyWonWithPipeline ? formatMoney(listSummary.wonPipelineValue) : '—'} color="#2E7D32" />
        <SummaryCard label="Info Required" value={listSummary.infoRequired} color="#B7791F" />
      </div>

      {/* Filter bar — single horizontal fp-card per AD-26. Status + dates
          LEFT, free-text search RIGHT (client-side across deal_name +
          customer_name). Date pickers re-added in PR #177, wired to
          GET /partners/{id}/pipeline (already supported the params) and
          GET /deal-registrations (gained them in PR #175). */}
      <section className="fp-card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <select value={filters.status} onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))} style={{ padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }}>
            <option value="">All Statuses</option>
            <option value="draft">Draft</option>
            <option value="submitted">Submitted</option>
            <option value="under_review">Under Review</option>
            <option value="info_required">Info Required</option>
            <option value="approved">Accepted</option>
            <option value="rejected">Rejected</option>
            <option value="won">Won</option>
            <option value="lost">Lost</option>
            <option value="withdrawn">Withdrawn</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)}
            title="From date — filters submitted_at"
            style={{ padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }} />
          <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)}
            title="To date — filters submitted_at"
            style={{ padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }} />
          <input type="search" placeholder="Search by deal or customer..."
            value={search} onChange={(e) => setSearch(e.target.value)}
            style={{ flex: 1, minWidth: 200, padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }} />
        </div>
      </section>

      {toast && (
        <div className="fp-alert fp-alert--success" style={{ marginBottom: 16 }}>{toast}</div>
      )}

      {error && (
        <div className="fp-alert fp-alert--danger">{error}</div>
      )}

      {/* Pipeline view — UNCHANGED. */}
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
          {!loadingPipeline && pipeline && pipelineSummary.total === 0 && (
            <div className="fp-card" style={{ textAlign: 'center', padding: 32, color: '#94A3B8' }}>No deals match your filters.</div>
          )}
        </>
      )}

      {/* List view */}
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

          {!loadingList && deals.length > 0 && (() => {
            const q = search.trim().toLowerCase()
            const visibleDeals = q
              ? deals.filter((d) => (
                  (d.deal_name || '').toLowerCase().includes(q) ||
                  (d.customer_name || '').toLowerCase().includes(q)
                ))
              : deals
            if (visibleDeals.length === 0) {
              return (
                <div className="fp-card" style={{ textAlign: 'center', padding: 32, color: 'var(--fp-text-secondary)' }}>
                  No deals match the current search.
                </div>
              )
            }
            return (
              <section className="fp-card">
                <table className="fp-table">
                  <thead>
                    <tr>
                      <SortableTh field="deal_name" sort={sort} onSort={toggleSort}>Deal</SortableTh>
                      <SortableTh field="customer_name" sort={sort} onSort={toggleSort}>Customer</SortableTh>
                      <SortableTh field="status" sort={sort} onSort={toggleSort}>Status</SortableTh>
                      <SortableTh field="pipeline_total" sort={sort} onSort={toggleSort}>Pipeline</SortableTh>
                      <SortableTh field="estimated_deal_value" sort={sort} onSort={toggleSort}>Estimated Value</SortableTh>
                      <SortableTh field="submitted_at" sort={sort} onSort={toggleSort}>Submitted</SortableTh>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleDeals.map((d) => {
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
              </section>
            )
          })()}
        </>
      )}
    </div>
  )
}
