import { useEffect, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
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

  useEffect(() => {
    if (!partnerOrgId || !token) return
    setLoading(true); setError(null)
    const qs = new URLSearchParams()
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
  }, [partnerOrgId, token, statusFilter])

  return (
    <div>
      <div className="fp-page-header">
        <h1 className="fp-page-title">My Quotes</h1>
      </div>

      <section className="fp-card" style={{ marginBottom: 16 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 13, color: '#64748B', fontWeight: 600 }}>Status</span>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
            style={{ padding: '8px 10px', borderRadius: 6, border: '1px solid #E0E4EA' }}>
            <option value="">All</option>
            <option value="draft">Draft</option>
            <option value="sent">Sent</option>
            <option value="accepted">Accepted</option>
            <option value="expired">Expired</option>
          </select>
        </label>
      </section>

      {error && <div className="fp-alert fp-alert--danger" style={{ marginBottom: 12 }}>{error}</div>}
      {loading && <div style={{ color: '#64748B', padding: 12 }}>Loading quotes…</div>}

      {!loading && (
        <section className="fp-card">
          {items.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 48, color: '#94A3B8' }}>
              No quotes have been created for your deals yet.
            </div>
          ) : (
            <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#F5F7FA', textAlign: 'left' }}>
                  <th style={{ padding: 10 }}>Quote</th>
                  <th style={{ padding: 10 }}>Deal</th>
                  <th style={{ padding: 10 }}>Plan</th>
                  <th style={{ padding: 10 }}>Currency</th>
                  <th style={{ padding: 10, textAlign: 'right' }}>Grand Total</th>
                  <th style={{ padding: 10 }}>Status</th>
                  <th style={{ padding: 10 }}>Created</th>
                </tr>
              </thead>
              <tbody>
                {items.map((q) => (
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
                    <td style={{ padding: 10, color: '#64748B' }}>
                      {q.created_at ? new Date(q.created_at).toLocaleDateString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </div>
  )
}
