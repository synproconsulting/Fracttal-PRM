import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { formatCurrency as fmtMoney } from '../utils/currency.js'

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

const BANNERS = {
  draft: { tone: 'fp-alert--info', text: 'This deal is a draft. Submit it for Fracttal review when ready.' },
  submitted: { tone: 'fp-alert--info', text: 'Your deal has been submitted and is awaiting review.' },
  under_review: { tone: 'fp-alert--warning', text: 'Your deal is currently being reviewed by the Fracttal team.' },
  info_required: { tone: 'fp-alert--warning', text: 'Additional information is required. Please respond below and resubmit.' },
  approved: { tone: 'fp-alert--success', text: 'Your deal has been approved.' },
  rejected: { tone: 'fp-alert--danger', text: 'Your deal was not approved.' },
  expired: { tone: 'fp-alert--neutral', text: 'This deal has expired.' },
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

function formatTimestamp(value) {
  if (!value) return '—'
  try { return new Date(value).toLocaleString() } catch { return value }
}

function DisplayField({ label, value }) {
  const v = value === null || value === undefined || value === '' ? '—' : value
  return (
    <div className="fp-field fp-field--filled">
      <input type="text" id={label} placeholder=" " value={v} readOnly disabled />
      <label htmlFor={label}>{label}</label>
    </div>
  )
}

// Field maps shared with InternalDealDetail. Labels mirror the partner-portal
// deal form so the read-only view reads back the same vocabulary the partner
// filled in.
const SYSTEMS = [
  { key: 'current_system',    label: 'Current System' },
  { key: 'old_system',        label: 'Old System' },
  { key: 'inventory_stores',  label: 'Inventory / Stores' },
  { key: 'work_orders_prs',   label: 'Work Orders & PRs' },
  { key: 'monitoring_system', label: 'Monitoring' },
]

const FEATURES = [
  { key: 'need_asset_depreciation',     label: 'Asset Depreciation' },
  { key: 'need_wo_wr',                  label: 'Work Orders / WR' },
  { key: 'need_reports',                label: 'Reports' },
  { key: 'need_tool_management',        label: 'Tool Management' },
  { key: 'need_purchasing',             label: 'Purchasing' },
  { key: 'need_integration',            label: 'Require Integration' },
  { key: 'need_multi_language',         label: 'Multi-language' },
  { key: 'need_asset_management',       label: 'Asset Management' },
  { key: 'need_document_management',    label: 'Document Management' },
  { key: 'need_cost_tracking',          label: 'Cost Tracking' },
  { key: 'need_monitoring',             label: 'Monitoring' },
  { key: 'need_schedule_third_parties', label: 'Schedule Third Parties' },
  { key: 'need_track_labour',           label: 'Track Labour Activities' },
]

const NARRATIVES = [
  { key: 'pain',           label: 'Pain (P)' },
  { key: 'impact',         label: 'Impact (I)' },
  { key: 'critical_event', label: 'Critical Event (CE)' },
  { key: 'decision',       label: 'Decision (D)' },
  { key: 'next_steps',     label: 'Next Steps' },
]

function featureIcon(v) {
  if (v === true) return '✅'
  if (v === false) return '❌'
  return '—'
}

export default function DealDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const ctx = useOutletContext() || {}
  const token = ctx.token || localStorage.getItem('token')
  const myEmail = ctx?.payload?.email

  const [deal, setDeal] = useState(null)
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [sending, setSending] = useState(false)
  const [resubmitting, setResubmitting] = useState(false)

  async function loadDeal() {
    const r = await fetch(`${API}/deal-registrations/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!r.ok) {
      const body = await r.json().catch(() => ({}))
      throw new Error(body.detail || `HTTP ${r.status}`)
    }
    return r.json()
  }

  async function loadMessages() {
    const r = await fetch(`${API}/deal-registrations/${id}/messages`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!r.ok) {
      // 404 here is treated as "no messages yet"
      return []
    }
    return r.json()
  }

  useEffect(() => {
    if (!id || !token) return
    setLoading(true)
    Promise.all([loadDeal(), loadMessages()])
      .then(([d, msgs]) => { setDeal(d); setMessages(msgs) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, token])

  const canResubmit = useMemo(() => {
    if (!deal) return false
    return deal.status === 'info_required'
      && (deal.customer_name || '').trim()
      && (deal.deal_name || '').trim()
  }, [deal])

  async function sendMessage() {
    if (!draft.trim() || sending) return
    setSending(true)
    setError(null)
    try {
      const r = await fetch(`${API}/deal-registrations/${id}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ message: draft.trim() }),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) {
        const msg = typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`
        throw new Error(msg)
      }
      setMessages((m) => [...m, body])
      setDraft('')
    } catch (e) {
      setError(e.message)
    } finally {
      setSending(false)
    }
  }

  async function resubmit() {
    if (!canResubmit || resubmitting) return
    setResubmitting(true)
    setError(null)
    try {
      const r = await fetch(`${API}/deal-registrations/${id}/submit`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) {
        const msg = typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`
        throw new Error(msg)
      }
      sessionStorage.setItem('deal_submitted_toast', `Deal "${body.deal_name}" resubmitted successfully`)
      navigate('/portal/deals', { replace: true })
    } catch (e) {
      setError(e.message)
    } finally {
      setResubmitting(false)
    }
  }

  if (loading) {
    return <div className="fp-card" style={{ color: 'var(--fp-text-secondary)' }}>Loading deal…</div>
  }

  if (error && !deal) {
    return (
      <div>
        <div className="fp-alert fp-alert--danger">{error}</div>
        <Link to="/portal/deals" className="fp-btn fp-btn--ghost" style={{ marginTop: 12 }}>Back to pipeline</Link>
      </div>
    )
  }

  if (!deal) return null

  const banner = BANNERS[deal.status]
  const showResubmitPanel = deal.status === 'info_required'

  return (
    <div>
      <div style={{ fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)', marginBottom: 8 }}>
        <Link to="/portal/deals" style={{ color: 'inherit' }}>My Pipeline</Link> &nbsp;›&nbsp; {deal.deal_name || '(unnamed)'}
      </div>

      <div className="fp-page-header">
        <div>
          <h1 className="fp-page-title">{deal.deal_name || '(unnamed)'}</h1>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 6 }}>
            <span className={`fp-badge ${STATUS_TONE[deal.status] || 'fp-badge--neutral'}`}>
              {STATUS_LABEL[deal.status] || deal.status}
            </span>
            <span style={{ fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>
              Submitted: {formatDate(deal.submitted_at)}
            </span>
          </div>
        </div>
        {deal.status === 'draft' && (
          <Link to={`/portal/deals/${deal.id}/edit`} className="fp-btn fp-btn--primary">
            Edit draft
          </Link>
        )}
      </div>

      {banner && (
        <div className={`fp-alert ${banner.tone}`} style={{ marginBottom: 16 }}>
          {banner.text}
          {deal.status === 'approved' && deal.reviewed_at && (
            <span style={{ marginLeft: 8 }}>Reviewed {formatDate(deal.reviewed_at)}.</span>
          )}
          {deal.status === 'rejected' && deal.review_notes && (
            <div style={{ marginTop: 4 }}>{deal.review_notes}</div>
          )}
        </div>
      )}

      {error && (
        <div className="fp-alert fp-alert--danger" style={{ marginBottom: 16 }}>{error}</div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 3fr) minmax(0, 2fr)', gap: 24 }}>
        <div>
          <section className="fp-card" style={{ marginBottom: 16 }}>
            <h2 className="fp-section-title">Customer information</h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <DisplayField label="Company name" value={deal.customer_name} />
              <DisplayField label="Customer domain" value={deal.customer_domain} />
              <DisplayField label="Contact name" value={deal.customer_contact_name} />
              <DisplayField label="Contact title" value={deal.customer_contact_position} />
              <DisplayField label="Contact email" value={deal.customer_contact_email} />
              <DisplayField label="Contact phone" value={deal.customer_contact_phone} />
              <DisplayField label="Industry" value={deal.customer_industry} />
              <DisplayField label="Country" value={deal.customer_country} />
              <DisplayField label="Region / state" value={deal.customer_region} />
              <DisplayField label="Company size" value={deal.company_size} />
            </div>
          </section>

          <section className="fp-card" style={{ marginBottom: 16 }}>
            <h2 className="fp-section-title">Partner contact information</h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <DisplayField label="Partner contact name" value={deal.prospect_contact_name} />
              <DisplayField label="Partner contact title" value={deal.prospect_contact_position} />
              <DisplayField label="Partner contact phone" value={deal.prospect_phone} />
              <DisplayField label="Partner website / LinkedIn" value={deal.prospect_website} />
              <DisplayField label="Compiled by" value={deal.compiled_by} />
            </div>
          </section>

          <section className="fp-card" style={{ marginBottom: 16 }}>
            <h2 className="fp-section-title">Deal information</h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <DisplayField label="Deal name" value={deal.deal_name} />
              <DisplayField label="Estimated value (USD)" value={formatMoney(deal.estimated_deal_value)} />
              <DisplayField label="Estimated close date" value={formatDate(deal.estimated_close_date)} />
              <DisplayField label="Engagement date" value={formatDate(deal.engagement_date)} />
              <DisplayField label="Requested Qty Transactional User Licenses" value={deal.qty_transactional_users} />
              <DisplayField label="Requested Qty Limited Technician User Licenses" value={deal.qty_limited_tech_users} />
              <DisplayField label="Indicative feature plan" value={deal.feature_plan_preference} />
              <DisplayField label="Commission type" value={deal.commission_type} />
              <div style={{ gridColumn: '1 / -1' }}>
                <DisplayField label="Deal notes" value={deal.deal_notes} />
              </div>
            </div>
          </section>

          <section className="fp-card">
            <h2 className="fp-section-title">Current State and Needs Assessment</h2>

            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 'var(--fp-fs-xs)', fontWeight: 600, color: 'var(--fp-text-secondary)', marginBottom: 2 }}>About the Client</div>
              <div style={{ whiteSpace: 'pre-wrap', fontSize: 'var(--fp-fs-sm)' }}>{deal.about_client || '—'}</div>
            </div>

            <h3 style={{ margin: '0 0 8px', fontSize: 'var(--fp-fs-md)', fontWeight: 600 }}>Situation (S) — Current Systems</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
              {SYSTEMS.map((f) => (
                <DisplayField key={f.key} label={f.label} value={deal[f.key]} />
              ))}
            </div>

            <h3 style={{ margin: '0 0 8px', fontSize: 'var(--fp-fs-md)', fontWeight: 600 }}>Features Required</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px 16px', marginBottom: 12, fontSize: 'var(--fp-fs-sm)' }}>
              {FEATURES.map((f) => (
                <div key={f.key}>{featureIcon(deal[f.key])} {f.label}</div>
              ))}
            </div>
            {(deal.integration_with || deal.languages_required) && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>
                {deal.integration_with && <DisplayField label="Integrate with" value={deal.integration_with} />}
                {deal.languages_required && <DisplayField label="Languages required" value={deal.languages_required} />}
              </div>
            )}

            <div style={{ display: 'grid', gap: 12 }}>
              {NARRATIVES.map((f) => (
                <div key={f.key}>
                  <div style={{ fontSize: 'var(--fp-fs-xs)', fontWeight: 600, color: 'var(--fp-text-secondary)', marginBottom: 2 }}>{f.label}</div>
                  <div style={{ whiteSpace: 'pre-wrap', fontSize: 'var(--fp-fs-sm)' }}>{deal[f.key] || '—'}</div>
                </div>
              ))}
            </div>
          </section>
        </div>

        <div>
          <section className="fp-card">
            <h2 className="fp-section-title">Collaboration</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 360, overflowY: 'auto', marginBottom: 16 }}>
              {messages.length === 0 && (
                <div style={{ color: 'var(--fp-text-secondary)', fontSize: 'var(--fp-fs-sm)' }}>
                  No messages yet.
                </div>
              )}
              {messages.map((m) => {
                const isMine = myEmail && m.sender_email === myEmail
                const senderLabel = m.sender_type === 'internal' ? 'Fracttal' : (isMine ? 'You' : m.sender_email)
                return (
                  <div key={m.id} style={{
                    background: m.sender_type === 'internal' ? 'var(--fp-bg-muted)' : '#eef5ff',
                    padding: 12, borderRadius: 8,
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--fp-fs-xs)', color: 'var(--fp-text-secondary)' }}>
                      <strong style={{ color: 'var(--fp-text-primary)' }}>{senderLabel}</strong>
                      <span>{formatTimestamp(m.created_at)}</span>
                    </div>
                    <div style={{ marginTop: 6, whiteSpace: 'pre-wrap' }}>{m.message}</div>
                  </div>
                )
              })}
            </div>

            {showResubmitPanel && (
              <div style={{ borderTop: '1px solid var(--fp-border)', paddingTop: 16 }}>
                <textarea
                  rows={4}
                  className="fp-textarea"
                  placeholder="Type your reply…"
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  style={{ width: '100%', boxSizing: 'border-box', marginBottom: 12 }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                  <button
                    type="button"
                    className="fp-btn fp-btn--secondary"
                    onClick={sendMessage}
                    disabled={sending || !draft.trim()}
                  >
                    {sending ? 'Sending…' : 'Send'}
                  </button>
                  <button
                    type="button"
                    className="fp-btn fp-btn--primary"
                    onClick={resubmit}
                    disabled={!canResubmit || resubmitting}
                  >
                    {resubmitting ? 'Resubmitting…' : 'Resubmit deal'}
                  </button>
                </div>
              </div>
            )}
          </section>
        </div>

      </div>
      <PortalQuoteSection dealId={deal.id} />
    </div>
  )
}

function PortalQuoteSection({ dealId }) {
  const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
    || 'https://fracttal-prm-backend-production.up.railway.app'
  const token = localStorage.getItem('token')
  const [quote, setQuote] = useState(null)
  const [scenarios, setScenarios] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!dealId || !token) return
    setLoading(true); setError(null)
    fetch(`${API}/deals/${dealId}/quotes`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (r) => {
        if (!r.ok) {
          const body = await r.json().catch(() => ({}))
          throw new Error(body.detail || `HTTP ${r.status}`)
        }
        return r.json()
      })
      .then(async (quotes) => {
        if (!quotes || quotes.length === 0) { setQuote(null); setScenarios([]); return }
        const picked = quotes[0] // most recent
        const [detailRes, scenariosRes] = await Promise.all([
          fetch(`${API}/quotes/${picked.id}`, { headers: { Authorization: `Bearer ${token}` } }),
          fetch(`${API}/quotes/${picked.id}/scenarios`, { headers: { Authorization: `Bearer ${token}` } }),
        ])
        if (!detailRes.ok) {
          const body = await detailRes.json().catch(() => ({}))
          throw new Error(body.detail || `HTTP ${detailRes.status}`)
        }
        setQuote(await detailRes.json())
        if (scenariosRes.ok) {
          const data = await scenariosRes.json()
          setScenarios(data.scenarios || [])
        }
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [dealId, token])

  // formatCurrency imported from ../utils/currency.js as fmtMoney

  async function handleDownloadPdf() {
    if (!quote?.active_version_data?.pdf_generated_at) return
    try {
      const r = await fetch(`${API}/quotes/${quote.id}/versions/${quote.active_version}/pdf`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${r.status}`)
      }
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `quote-v${quote.active_version}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e.message)
    }
  }

  if (loading) return null
  if (error) return <section className="fp-card" style={{ marginTop: 16 }}><div className="fp-alert fp-alert--danger">{error}</div></section>
  if (!quote) {
    return (
      <section className="fp-card" style={{ marginTop: 16 }}>
        <h2 className="fp-section-title">Quote</h2>
        <div style={{ color: '#64748B', fontSize: 14 }}>No quote has been created for this deal yet.</div>
      </section>
    )
  }

  const v = quote.active_version_data
  const currency = quote.currency_code || 'USD'
  const items = v?.line_items || []
  const pdfAvailable = !!v?.pdf_generated_at

  return (
    <section className="fp-card" style={{ marginTop: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
        <h2 className="fp-section-title" style={{ margin: 0 }}>Quote</h2>
        <button type="button" onClick={handleDownloadPdf} disabled={!pdfAvailable} className="fp-btn fp-btn--primary">
          Download Quote PDF
        </button>
      </div>
      {quote.active_scenario && (
        <div style={{
          background: '#EBF4FF', border: '1px solid #1A6EBB', borderRadius: 8,
          padding: '10px 14px', marginBottom: 12, fontSize: 14,
        }}>
          <strong>Your recommended option:</strong>{' '}
          <span style={{ color: '#1A6EBB', fontWeight: 700, textTransform: 'capitalize' }}>
            {quote.active_scenario}
          </span>
        </div>
      )}
      {scenarios.length > 1 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
          {scenarios.map((s) => {
            const isActive = s.scenario_label === quote.active_scenario
            return (
              <div key={s.scenario_label}
                title={isActive ? 'Currently selected' : 'Available alternative'}
                style={{
                  padding: '6px 12px',
                  borderRadius: 999,
                  fontSize: 12,
                  fontWeight: isActive ? 700 : 500,
                  background: isActive ? '#1A6EBB' : '#F5F7FA',
                  color: isActive ? '#fff' : '#475569',
                  border: isActive ? 'none' : '1px solid #E0E4EA',
                  textTransform: 'capitalize',
                }}>
                {isActive ? '⭐ ' : ''}{s.scenario_label} — {fmtMoney(s.grand_total_after_discount, currency)}
              </div>
            )
          })}
        </div>
      )}
      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', marginBottom: 12, fontSize: 13, color: '#64748B' }}>
        <div><strong>Plan:</strong> {v?.feature_plan || '—'}</div>
        <div><strong>Currency:</strong> {currency}</div>
        <div><strong>Version:</strong> v{quote.active_version}{v?.scenario_label ? ` (${v.scenario_label})` : ''}</div>
      </div>
      <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ background: '#1A6EBB', color: '#fff' }}>
            <th style={{ textAlign: 'left', padding: 8 }}>Description</th>
            <th style={{ textAlign: 'right', padding: 8 }}>Qty</th>
            <th style={{ textAlign: 'right', padding: 8 }}>Unit</th>
            <th style={{ textAlign: 'right', padding: 8 }}>Discount</th>
            <th style={{ textAlign: 'right', padding: 8 }}>Total</th>
          </tr>
        </thead>
        <tbody>
          {items.map((li) => (
            <tr key={li.id || `${li.line_order}-${li.line_type}`} style={{
              borderBottom: '1px solid #F1F5F9',
              background: li.line_type === 'free_allocation' ? '#F0FDF4' : 'transparent',
              color: li.line_type === 'free_allocation' ? '#15803D' : 'inherit',
              fontStyle: li.line_type === 'free_allocation' ? 'italic' : 'normal',
            }}>
              <td style={{ padding: 8 }}>{li.description}</td>
              <td style={{ padding: 8, textAlign: 'right' }}>{li.quantity}</td>
              <td style={{ padding: 8, textAlign: 'right' }}>{Number(li.unit_price) > 0 ? fmtMoney(li.unit_price, currency) : '—'}</td>
              <td style={{ padding: 8, textAlign: 'right' }}>{Number(li.discount_pct) > 0 ? `${Number(li.discount_pct).toFixed(0)}%` : '—'}</td>
              <td style={{ padding: 8, textAlign: 'right' }}>{fmtMoney(li.total_after_discount, currency)}</td>
            </tr>
          ))}
          <tr style={{ borderTop: '2px solid #1A6EBB', background: '#F5F7FA', fontWeight: 700 }}>
            <td style={{ padding: 8 }} colSpan={4}>Annual Total After Discount</td>
            <td style={{ padding: 8, textAlign: 'right' }}>{fmtMoney(v?.grand_total_after_discount, currency)}</td>
          </tr>
        </tbody>
      </table>
    </section>
  )
}

