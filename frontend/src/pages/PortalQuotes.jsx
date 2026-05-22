import { useEffect, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
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

export default function PortalQuotes() {
  const ctx = useOutletContext() || {}
  const token = ctx.token || localStorage.getItem('token')
  const partnerOrgId = ctx?.payload?.partner_org_id
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [pipelineOnly, setPipelineOnly] = useState(false)
  const [sort, setSort] = useState({ field: 'created_at', dir: 'desc' })
  const [exporting, setExporting] = useState(false)

  function toggleSort(field) {
    setSort((s) => s.field === field
      ? { field, dir: s.dir === 'asc' ? 'desc' : 'asc' }
      : { field, dir: 'asc' })
  }

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

  useEffect(() => {
    if (!partnerOrgId || !token) return
    setLoading(true); setError(null)
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

  return (
    <div>
      <div className="fp-page-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <h1 className="fp-page-title">My Quotes</h1>
        <button type="button" onClick={exportCSV} disabled={exporting}
                style={{ fontSize: '0.75rem', padding: '4px 10px', border: '1px solid #CBD5E0', borderRadius: 4, backgroundColor: 'white', color: '#718096', cursor: 'pointer', fontWeight: 400 }}>
          {exporting ? 'Exporting...' : 'Export CSV'}
        </button>
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
          </select>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', marginLeft: 'auto' }}
                 title="Show only quotes currently counted toward the pipeline total">
            <input
              type="checkbox"
              checked={pipelineOnly}
              onChange={(e) => setPipelineOnly(e.target.checked)}
            />
            <span style={{ fontSize: 13, color: '#64748B', fontWeight: 600 }}>Pipeline only</span>
          </label>
        </div>
      </section>

      {error && <div className="fp-alert fp-alert--danger" style={{ marginBottom: 12 }}>{error}</div>}
      {loading && <div style={{ color: '#64748B', padding: 12 }}>Loading quotes…</div>}

      {!loading && (
        <section className="fp-card">
          {(() => {
            // "Pipeline only" toggle filters in-memory -- the backend doesn't
            // expose an include_in_pipeline query param yet and the dataset is
            // small enough that paginating client-side is fine.
            const visibleItems = pipelineOnly ? items.filter((q) => q.include_in_pipeline === true) : items
            if (items.length === 0) {
              return (
                <div style={{ textAlign: 'center', padding: 48, color: '#94A3B8' }}>
                  No quotes have been created for your deals yet.
                </div>
              )
            }
            if (visibleItems.length === 0) {
              return (
                <div style={{ textAlign: 'center', padding: 48, color: '#94A3B8' }}>
                  No quotes match the current filters.
                </div>
              )
            }
            return (
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
                  {visibleItems.map((q) => (
                    <tr key={q.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                      <td style={{ padding: 10 }}>
                        <Link to={`/portal/deals/${q.deal_id}`} style={{ color: '#1A6EBB', fontWeight: 600 }}>
                          {q.quote_name}
                        </Link>
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
            )
          })()}
        </section>
      )}
    </div>
  )
}
