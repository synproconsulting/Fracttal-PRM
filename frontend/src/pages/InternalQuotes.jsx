import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { formatCurrency } from '../utils/currency.js'
import { SortableTh } from '../components/SortableTh.jsx'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const STATUS_TONE = {
  draft: '#64748B',
  sent: '#1A6EBB',
  accepted: '#1B8743',
  expired: '#C2410C',
}

// Sprint 21 hotfix FPRM-357: tinted-badge tones for the deal lifecycle
// surfaced on each quote row. Mirrors AD-27 with the same colour logic the
// deal list pages already use.
const DEAL_STATUS_TONE = {
  draft: '#64748B',
  submitted: '#1A6EBB',
  under_review: '#B7791F',
  info_required: '#B7791F',
  approved: '#1B8743',
  won: '#1B8743',
  rejected: '#C62828',
  cancelled: '#C62828',
  lost: '#C62828',
  withdrawn: '#94A3B8',
  expired: '#94A3B8',
}

function StatusBadge({ status }) {
  const color = STATUS_TONE[status] || '#64748B'
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 12,
      background: `${color}22`,
      color, fontSize: 12, fontWeight: 600,
      textTransform: 'capitalize',
    }}>{status}</span>
  )
}

function DealStatusBadge({ status }) {
  if (!status) return <span style={{ color: '#94A3B8' }}>—</span>
  const color = DEAL_STATUS_TONE[status] || '#64748B'
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 12,
      background: `${color}22`,
      color, fontSize: 12, fontWeight: 600,
      textTransform: 'capitalize',
    }}>{status.replace(/_/g, ' ')}</span>
  )
}

function SummaryCard({ label, value, color = '#1A6EBB' }) {
  return (
    <div className="fp-card" style={{ flex: 1, minWidth: 140, padding: 14 }}>
      <div style={{ fontSize: 11, color: '#64748B', textTransform: 'uppercase', fontWeight: 600, letterSpacing: 0.5 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color, marginTop: 4 }}>{value}</div>
    </div>
  )
}

export default function InternalQuotes() {
  const token = localStorage.getItem('token')
  const [items, setItems] = useState([])
  const [summary, setSummary] = useState(null)
  const [total, setTotal] = useState(0)
  const [filters, setFilters] = useState({ status: '', search: '', feature_plan: '' })
  // Pipeline-only is a client-side filter — the backend endpoint doesn't
  // accept it as a query param yet, and include_in_pipeline is already on
  // every row (added in PR #155). Trade-off: the current paginated page may
  // briefly show fewer rows than page_size when the toggle is on; that's
  // acceptable for this small surface area.
  const [pipelineOnly, setPipelineOnly] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [sort, setSort] = useState({ field: 'created_at', dir: 'desc' })

  function toggleSort(field) {
    setSort((s) => s.field === field
      ? { field, dir: s.dir === 'asc' ? 'desc' : 'asc' }
      : { field, dir: 'asc' })
  }

  const fetchData = useCallback(async () => {
    if (!token) return
    setLoading(true); setError(null)
    try {
      const qs = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
        sort_by: sort.field,
        sort_dir: sort.dir,
      })
      if (filters.status) qs.set('status', filters.status)
      if (filters.feature_plan) qs.set('feature_plan', filters.feature_plan)
      if (filters.search) qs.set('search', filters.search)
      const r = await fetch(`${API}/internal/quotes?${qs.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
      setItems(body.items || [])
      setSummary(body.summary || null)
      setTotal(body.total || 0)
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setLoading(false)
    }
  }, [token, page, pageSize, filters, sort])

  useEffect(() => { fetchData() }, [fetchData])

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize])

  const [exporting, setExporting] = useState(false)
  async function exportCSV() {
    // Sprint 21 -- GET /internal/quotes/export. AD-20: fetch + Blob.
    setExporting(true)
    try {
      const qs = new URLSearchParams()
      if (filters.status) qs.set('status', filters.status)
      if (filters.feature_plan) qs.set('feature_plan', filters.feature_plan)
      if (filters.search) qs.set('search', filters.search)
      const r = await fetch(`${API}/internal/quotes/export?${qs.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'quotes_export.csv'
      document.body.appendChild(a); a.click(); document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setExporting(false)
    }
  }

  return (
    <div>
      <div className="fp-page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 className="fp-page-title">Quotes</h1>
        <button type="button" onClick={exportCSV} disabled={exporting}
                style={{ fontSize: '0.75rem', padding: '4px 10px', border: '1px solid #CBD5E0', borderRadius: 4, backgroundColor: 'white', color: '#718096', cursor: exporting ? 'wait' : 'pointer', fontWeight: 400 }}>
          {exporting ? 'Exporting…' : 'Export CSV'}
        </button>
      </div>

      {summary && (
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
          <SummaryCard label="Total Quotes" value={summary.total_quotes} />
          <SummaryCard label="Draft" value={summary.draft} color="#64748B" />
          <SummaryCard label="Sent" value={summary.sent} color="#1A6EBB" />
          <SummaryCard label="Accepted" value={summary.accepted} color="#1B8743" />
          <SummaryCard label="Won" value={summary.won_deals ?? 0} color="#1B8743" />
          <SummaryCard label="Active Pipeline Value" value={formatCurrency(summary.pipeline_total, 'USD')} />
          <SummaryCard label="Closed Won" value={formatCurrency(summary.closed_won_value ?? 0, 'USD')} color="#1B8743" />
        </div>
      )}

      <section className="fp-card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <select value={filters.status} onChange={(e) => { setPage(1); setFilters((f) => ({ ...f, status: e.target.value })) }}
            style={{ padding: '8px 10px', borderRadius: 6, border: '1px solid #E0E4EA' }}>
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="sent">Sent</option>
            <option value="accepted">Accepted</option>
            <option value="expired">Expired</option>
          </select>
          <select value={filters.feature_plan} onChange={(e) => { setPage(1); setFilters((f) => ({ ...f, feature_plan: e.target.value })) }}
            style={{ padding: '8px 10px', borderRadius: 6, border: '1px solid #E0E4EA' }}>
            <option value="">All plans</option>
            <option value="starter">Starter</option>
            <option value="professional">Professional</option>
            <option value="enterprise">Enterprise</option>
          </select>
          <input type="search" placeholder="Search by quote or deal name…"
            value={filters.search}
            onChange={(e) => { setPage(1); setFilters((f) => ({ ...f, search: e.target.value })) }}
            style={{ flex: 1, minWidth: 200, padding: '8px 10px', borderRadius: 6, border: '1px solid #E0E4EA' }} />
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', whiteSpace: 'nowrap' }}
                 title="Show only quotes currently counted toward the pipeline total">
            <input type="checkbox" checked={pipelineOnly} onChange={(e) => setPipelineOnly(e.target.checked)} />
            <span style={{ fontSize: 13, color: '#64748B', fontWeight: 600 }}>Pipeline only</span>
          </label>
        </div>
      </section>

      {error && <div className="fp-alert fp-alert--danger" style={{ marginBottom: 12 }}>{error}</div>}
      {loading && <div style={{ color: '#64748B', padding: 12 }}>Loading quotes…</div>}

      {!loading && (() => {
        const visibleItems = pipelineOnly ? items.filter((q) => q.include_in_pipeline === true) : items
        return (
        <section className="fp-card">
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#F5F7FA', textAlign: 'left' }}>
                <SortableTh field="quote_name" sort={sort} onSort={toggleSort} style={{ padding: 10 }}>Quote</SortableTh>
                <SortableTh field="deal_name" sort={sort} onSort={toggleSort} style={{ padding: 10 }}>Deal</SortableTh>
                <SortableTh field="partner_org" sort={sort} onSort={toggleSort} style={{ padding: 10 }}>Partner</SortableTh>
                <SortableTh field="feature_plan" sort={sort} onSort={toggleSort} style={{ padding: 10 }}>Plan</SortableTh>
                <th style={{ padding: 10 }}>Currency</th>
                <SortableTh field="grand_total_after_discount" sort={sort} onSort={toggleSort} style={{ padding: 10 }} align="right">Grand Total</SortableTh>
                <SortableTh field="status" sort={sort} onSort={toggleSort} style={{ padding: 10 }}>Status</SortableTh>
                <th style={{ padding: 10 }}>Deal Status</th>
                <th style={{ padding: 10, textAlign: 'center' }}>Pipeline</th>
                <SortableTh field="created_at" sort={sort} onSort={toggleSort} style={{ padding: 10 }}>Created</SortableTh>
              </tr>
            </thead>
            <tbody>
              {visibleItems.length === 0 && (
                <tr><td colSpan={10} style={{ textAlign: 'center', padding: 32, color: '#94A3B8' }}>
                  No quotes match the current filters.
                </td></tr>
              )}
              {visibleItems.map((q) => (
                <tr key={q.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                  <td style={{ padding: 10 }}>
                    <Link to={`/internal/deals/${q.deal_id}?openQuote=${q.id}`} style={{ color: '#1A6EBB', fontWeight: 600 }}>
                      {q.quote_name}
                    </Link>
                    {q.active_scenario && (
                      <span style={{ marginLeft: 6, fontSize: 11, color: '#64748B', textTransform: 'capitalize' }}>
                        ({q.active_scenario})
                      </span>
                    )}
                  </td>
                  <td style={{ padding: 10 }}>
                    <Link to={`/internal/deals/${q.deal_id}`} style={{ color: '#1A6EBB' }}>{q.deal_name}</Link>
                  </td>
                  <td style={{ padding: 10 }}>{q.partner_org_name}</td>
                  <td style={{ padding: 10, textTransform: 'capitalize' }}>{q.feature_plan}</td>
                  <td style={{ padding: 10 }}>{q.currency_code}</td>
                  <td style={{ padding: 10, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {formatCurrency(q.grand_total_after_discount, q.currency_code)}
                  </td>
                  <td style={{ padding: 10 }}><StatusBadge status={q.status} /></td>
                  <td style={{ padding: 10 }}><DealStatusBadge status={q.deal_status} /></td>
                  <td style={{ padding: 10, textAlign: 'center' }}>
                    <span aria-label={q.include_in_pipeline ? 'In pipeline' : 'Not in pipeline'}>
                      {q.include_in_pipeline ? '✅' : '—'}
                    </span>
                  </td>
                  <td style={{ padding: 10, color: '#64748B' }}>
                    {q.created_at ? new Date(q.created_at).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {total > pageSize && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12, fontSize: 13 }}>
              <span style={{ color: '#64748B' }}>Page {page} of {totalPages} — {total} quotes</span>
              <div style={{ display: 'flex', gap: 8 }}>
                <button type="button" className="fp-btn fp-btn--ghost" disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}>Previous</button>
                <button type="button" className="fp-btn fp-btn--ghost" disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>Next</button>
              </div>
            </div>
          )}
        </section>
        )
      })()}
    </div>
  )
}
