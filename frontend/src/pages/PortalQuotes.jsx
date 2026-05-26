import { useEffect, useMemo, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { formatCurrency } from '../utils/currency.js'
import { SortableTh } from '../components/SortableTh.jsx'
import QuoteDetail from './QuoteDetail.jsx'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const STATUS_TONE = {
  draft: '#64748B',
  sent: '#1A6EBB',
  accepted: '#1B8743',
  expired: '#C2410C',
  cancelled: '#C62828',
}

function StatusBadge({ status }) {
  const color = STATUS_TONE[status] || '#64748B'
  return (
    <span style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: 12,
      background: `${color}22`, color, fontSize: 12, fontWeight: 600,
      textTransform: 'capitalize',
    }}>{status}</span>
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

function decodeJwt(token) {
  try {
    const parts = token.split('.')
    if (parts.length < 2) return null
    const padded = parts[1] + '==='.slice((parts[1].length + 3) % 4)
    const json = atob(padded.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(json)
  } catch (_) { return null }
}

export default function PortalQuotes() {
  const ctx = useOutletContext() || {}
  const token = ctx.token || localStorage.getItem('token')
  const payload = ctx.payload || (token ? decodeJwt(token) : null)
  const partnerOrgId = payload && payload.partner_org_id

  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [planFilter, setPlanFilter] = useState('')
  const [search, setSearch] = useState('')
  const [pipelineOnly, setPipelineOnly] = useState(false)
  const [sort, setSort] = useState({ field: 'created_at', dir: 'desc' })
  const [exporting, setExporting] = useState(false)
  const [openQuoteId, setOpenQuoteId] = useState(null)

  function toggleSort(field) {
    setSort((s) => s.field === field
      ? { field, dir: s.dir === 'asc' ? 'desc' : 'asc' }
      : { field, dir: 'asc' })
  }

  useEffect(() => {
    if (!partnerOrgId || !token) return
    setLoading(true); setError(null)
    // Backend GET /partners/{id}/quotes only accepts status / sort_by / sort_dir.
    // Plan, search, and pipeline_only are client-side filters below.
    const qs = new URLSearchParams({ sort_by: sort.field, sort_dir: sort.dir })
    if (statusFilter) qs.set('status', statusFilter)
    fetch(`${API}/partners/${partnerOrgId}/quotes?${qs.toString()}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        const body = await r.json().catch(() => ({}))
        if (!r.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
        return body
      })
      .then((body) => setItems(body.items || []))
      .catch((e) => setError(e.message || String(e)))
      .finally(() => setLoading(false))
  }, [partnerOrgId, token, statusFilter, sort])

  async function exportCSV() {
    if (!partnerOrgId || !token) return
    setExporting(true)
    try {
      const qs = new URLSearchParams({ export: 'csv' })
      if (statusFilter) qs.set('status', statusFilter)
      const r = await fetch(`${API}/partners/${partnerOrgId}/quotes?${qs.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'my_quotes_export.csv'
      document.body.appendChild(a); a.click(); document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('CSV export error:', e)
      setError(e.message)
    } finally {
      setExporting(false)
    }
  }

  // Summary mirrors the shape of the InternalQuotes backend `summary` block,
  // but is computed client-side because GET /partners/{id}/quotes does not
  // return one. Operates over `items` (already filtered by backend status if
  // statusFilter is set), matching the spec.
  //
  // TODO Sprint 21: backend GET /partners/{id}/quotes missing field: deal_status.
  // Without deal status, "Won" and "Closed Won" cannot strictly mirror the
  // /internal/quotes summary (which counts accepted quotes on deals where
  // deal.status === 'won'). We fall back to quote.status === 'accepted' as a
  // best-effort approximation. Add deal_status to the partner response and
  // re-derive these two cards once available.
  const summary = useMemo(() => {
    let draft = 0, sent = 0, accepted = 0
    let pipelineTotal = 0
    let closedWon = 0
    for (const q of items) {
      const s = q.status
      if (s === 'draft') draft++
      else if (s === 'sent') sent++
      else if (s === 'accepted') accepted++

      const total = Number(q.grand_total_after_discount) || 0
      if (q.include_in_pipeline && s !== 'expired' && s !== 'cancelled') {
        pipelineTotal += total
      }
      if (s === 'accepted') {
        closedWon += total
      }
    }
    return {
      total_quotes: items.length,
      draft, sent, accepted,
      won_deals: accepted,
      pipeline_total: pipelineTotal,
      closed_won_value: closedWon,
    }
  }, [items])

  const visibleItems = useMemo(() => {
    const q = search.trim().toLowerCase()
    return items.filter((it) => {
      if (planFilter && it.feature_plan !== planFilter) return false
      if (pipelineOnly && it.include_in_pipeline !== true) return false
      if (q && !(
        (it.quote_name || '').toLowerCase().includes(q) ||
        (it.deal_name || '').toLowerCase().includes(q)
      )) return false
      return true
    })
  }, [items, planFilter, pipelineOnly, search])

  return (
    <div>
      <div className="fp-page-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <h1 className="fp-page-title">My Quotes</h1>
        <button type="button" onClick={exportCSV} disabled={exporting}
                style={{ fontSize: '0.75rem', padding: '4px 10px', border: '1px solid #CBD5E0', borderRadius: 4, backgroundColor: 'white', color: '#718096', cursor: 'pointer', fontWeight: 400 }}>
          {exporting ? 'Exporting...' : 'Export CSV'}
        </button>
      </div>

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
        <SummaryCard label="Total Quotes" value={summary.total_quotes} />
        <SummaryCard label="Draft" value={summary.draft} color="#64748B" />
        <SummaryCard label="Sent" value={summary.sent} color="#1A6EBB" />
        <SummaryCard label="Accepted" value={summary.accepted} color="#1A6EBB" />
        <SummaryCard label="Won" value={summary.won_deals} color="#2E7D32" />
        <SummaryCard label="Active Pipeline Value" value={formatCurrency(summary.pipeline_total, 'USD')} />
        <SummaryCard label="Closed Won" value={formatCurrency(summary.closed_won_value, 'USD')} color="#2E7D32" />
      </div>

      <section className="fp-card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
            style={{ padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }}>
            <option value="">All statuses</option>
            <option value="draft">Draft</option>
            <option value="sent">Sent</option>
            <option value="accepted">Accepted</option>
            <option value="expired">Expired</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <select value={planFilter} onChange={(e) => setPlanFilter(e.target.value)}
            style={{ padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }}>
            <option value="">All plans</option>
            <option value="starter">Starter</option>
            <option value="professional">Professional</option>
            <option value="enterprise">Enterprise</option>
          </select>
          <input type="search" placeholder="Search by quote or deal name…"
            value={search} onChange={(e) => setSearch(e.target.value)}
            style={{ flex: 1, minWidth: 200, padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }} />
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', whiteSpace: 'nowrap' }}
                 title="Show only quotes currently counted toward the pipeline total">
            <input type="checkbox" checked={pipelineOnly} onChange={(e) => setPipelineOnly(e.target.checked)} />
            <span style={{ fontSize: 13, color: '#64748B', fontWeight: 600 }}>Pipeline only</span>
          </label>
        </div>
      </section>

      {error && <div className="fp-alert fp-alert--danger" style={{ marginBottom: 12 }}>{error}</div>}
      {loading && <div style={{ color: '#64748B', padding: 12 }}>Loading quotes…</div>}

      {!loading && (
        <section className="fp-card">
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#F5F7FA', textAlign: 'left' }}>
                <SortableTh field="quote_name" sort={sort} onSort={toggleSort} style={{ padding: 10 }}>Quote</SortableTh>
                <SortableTh field="deal_name" sort={sort} onSort={toggleSort} style={{ padding: 10 }}>Deal</SortableTh>
                <SortableTh field="feature_plan" sort={sort} onSort={toggleSort} style={{ padding: 10 }}>Plan</SortableTh>
                <th style={{ padding: 10 }}>Currency</th>
                <SortableTh field="grand_total_after_discount" sort={sort} onSort={toggleSort} style={{ padding: 10 }} align="right">Grand Total</SortableTh>
                <SortableTh field="status" sort={sort} onSort={toggleSort} style={{ padding: 10 }}>Status</SortableTh>
                <th style={{ padding: 10, textAlign: 'center' }}>Pipeline</th>
                <SortableTh field="created_at" sort={sort} onSort={toggleSort} style={{ padding: 10 }}>Created</SortableTh>
              </tr>
            </thead>
            <tbody>
              {visibleItems.length === 0 && (
                <tr><td colSpan={8} style={{ textAlign: 'center', padding: 32, color: '#94A3B8' }}>
                  <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>No quotes found</div>
                  <div style={{ fontSize: 12 }}>Quotes will appear here once your deals have quotes created.</div>
                </td></tr>
              )}
              {visibleItems.map((q) => (
                <tr key={q.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                  <td style={{ padding: 10 }}>
                    <button type="button" onClick={() => setOpenQuoteId(q.id)}
                            style={{ background: 'none', border: 'none', padding: 0, color: '#1A6EBB', fontWeight: 600, cursor: 'pointer', font: 'inherit', textAlign: 'left' }}>
                      {q.quote_name}
                    </button>
                    {q.active_scenario && (
                      <span style={{ marginLeft: 6, fontSize: 11, color: '#64748B', textTransform: 'capitalize' }}>
                        ({q.active_scenario})
                      </span>
                    )}
                  </td>
                  <td style={{ padding: 10 }}>
                    <Link to={`/portal/deals/${q.deal_id}`} style={{ color: '#1A6EBB' }}>{q.deal_name}</Link>
                  </td>
                  <td style={{ padding: 10, textTransform: 'capitalize' }}>{q.feature_plan}</td>
                  <td style={{ padding: 10 }}>{q.currency_code}</td>
                  <td style={{ padding: 10, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {formatCurrency(q.grand_total_after_discount, q.currency_code)}
                  </td>
                  <td style={{ padding: 10 }}><StatusBadge status={q.status} /></td>
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
        </section>
      )}

      {openQuoteId && (
        <QuoteDetail
          quoteId={openQuoteId}
          isReadOnly
          onClose={() => setOpenQuoteId(null)}
          includeInPipeline={items.find((q) => q.id === openQuoteId)?.include_in_pipeline}
        />
      )}
    </div>
  )
}
