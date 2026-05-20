import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { formatCurrency } from '../utils/currency.js'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const STATUS_TONE = {
  draft: '#64748B',
  sent: '#1A6EBB',
  accepted: '#1B8743',
  expired: '#C2410C',
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
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchData = useCallback(async () => {
    if (!token) return
    setLoading(true); setError(null)
    try {
      const qs = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
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
  }, [token, page, pageSize, filters])

  useEffect(() => { fetchData() }, [fetchData])

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize])

  return (
    <div>
      <div className="fp-page-header">
        <h1 className="fp-page-title">Quotes</h1>
      </div>

      {summary && (
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 16 }}>
          <SummaryCard label="Total Quotes" value={summary.total_quotes} />
          <SummaryCard label="Draft" value={summary.draft} color="#64748B" />
          <SummaryCard label="Sent" value={summary.sent} color="#1A6EBB" />
          <SummaryCard label="Accepted" value={summary.accepted} color="#1B8743" />
          <SummaryCard label="Pipeline Value" value={formatCurrency(summary.pipeline_total, 'USD')} />
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
        </div>
      </section>

      {error && <div className="fp-alert fp-alert--danger" style={{ marginBottom: 12 }}>{error}</div>}
      {loading && <div style={{ color: '#64748B', padding: 12 }}>Loading quotes…</div>}

      {!loading && (
        <section className="fp-card">
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#F5F7FA', textAlign: 'left' }}>
                <th style={{ padding: 10 }}>Quote</th>
                <th style={{ padding: 10 }}>Deal</th>
                <th style={{ padding: 10 }}>Partner</th>
                <th style={{ padding: 10 }}>Plan</th>
                <th style={{ padding: 10 }}>Currency</th>
                <th style={{ padding: 10, textAlign: 'right' }}>Grand Total</th>
                <th style={{ padding: 10 }}>Status</th>
                <th style={{ padding: 10 }}>Created</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 && (
                <tr><td colSpan={8} style={{ textAlign: 'center', padding: 32, color: '#94A3B8' }}>
                  No quotes match the current filters.
                </td></tr>
              )}
              {items.map((q) => (
                <tr key={q.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                  <td style={{ padding: 10 }}>
                    <Link to={`/internal/deals/${q.deal_id}`} style={{ color: '#1A6EBB', fontWeight: 600 }}>
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
      )}
    </div>
  )
}
