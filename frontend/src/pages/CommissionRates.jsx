import { useEffect, useMemo, useState } from 'react'
import { useOutletContext } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const COMMISSION_TYPE_LABELS = {
  autonomous_sell: 'Autonomous Sell',
  indirect_sell: 'Indirect Sell',
  direct_sell: 'Direct Sell',
  co_sell_shared: 'Co-Sell (Shared)',
}

const YEAR_LABELS = {
  year_1: 'Year 1',
  year_2_plus: 'Year 2+',
}

function formatLabel(map, value) {
  if (!value) return ''
  return map[value] || value
}

export default function CommissionRates() {
  const ctx = useOutletContext() || {}
  const token = ctx.token || localStorage.getItem('token')
  const payload = ctx.payload || null
  const partnerOrgId = payload?.partner_org_id

  const [loading, setLoading] = useState(true)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!partnerOrgId || !token) {
      setLoading(false)
      return
    }
    fetch(`${API}/partners/${partnerOrgId}/commission-rates`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        if (!r.ok) {
          const body = await r.json().catch(() => ({}))
          throw new Error(body.detail || `HTTP ${r.status}`)
        }
        return r.json()
      })
      .then((d) => setData(d))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [partnerOrgId, token])

  const sortedItems = useMemo(() => {
    if (!data?.items) return []
    return [...data.items].sort((a, b) => {
      const ta = formatLabel(COMMISSION_TYPE_LABELS, a.commission_type)
      const tb = formatLabel(COMMISSION_TYPE_LABELS, b.commission_type)
      if (ta !== tb) return ta.localeCompare(tb)
      return (a.year || '').localeCompare(b.year || '')
    })
  }, [data])

  if (loading) {
    return <div className="fp-card" style={{ color: 'var(--fp-text-secondary)' }}>Loading commission rates…</div>
  }
  if (error) {
    return <div className="fp-alert fp-alert--danger">{error}</div>
  }

  const categoryLabel = data?.partner_category_code
    ? data.partner_category_code.charAt(0).toUpperCase() + data.partner_category_code.slice(1)
    : ''

  return (
    <div>
      <div className="fp-page-header">
        <div>
          <h1 className="fp-page-title">
            Your Commission Rates{categoryLabel ? ` — ${categoryLabel}` : ''}
          </h1>
          <p style={{ margin: '6px 0 0', fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>
            Applicable commission percentages for your partner category, sourced from the current Fracttal Distributor Agreement.
          </p>
        </div>
      </div>

      {sortedItems.length === 0 ? (
        <div className="fp-card" style={{ color: 'var(--fp-text-secondary)' }}>
          No commission rates found for your partner category.
        </div>
      ) : (
        <section className="fp-card">
          <table className="fp-table">
            <thead>
              <tr>
                <th>Commission Type</th>
                <th>Year</th>
                <th style={{ textAlign: 'right' }}>Rate</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {sortedItems.map((item, idx) => (
                <tr key={idx}>
                  <td>{formatLabel(COMMISSION_TYPE_LABELS, item.commission_type)}</td>
                  <td>{formatLabel(YEAR_LABELS, item.year)}</td>
                  <td style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {item.percentage != null ? `${item.percentage}%` : '—'}
                  </td>
                  <td style={{ color: 'var(--fp-text-secondary)', fontSize: 'var(--fp-fs-sm)' }}>
                    {item.notes || ''}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}
