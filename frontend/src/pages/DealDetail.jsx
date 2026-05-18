import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useOutletContext, useParams } from 'react-router-dom'

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
              <DisplayField label="Customer name" value={deal.customer_name} />
              <DisplayField label="Customer domain" value={deal.customer_domain} />
              <DisplayField label="Contact name" value={deal.customer_contact_name} />
              <DisplayField label="Contact email" value={deal.customer_contact_email} />
              <DisplayField label="Contact phone" value={deal.customer_contact_phone} />
              <DisplayField label="Industry" value={deal.customer_industry} />
              <DisplayField label="Country" value={deal.customer_country} />
              <DisplayField label="Region / state" value={deal.customer_region} />
            </div>
          </section>

          <section className="fp-card">
            <h2 className="fp-section-title">Deal information</h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <DisplayField label="Deal name" value={deal.deal_name} />
              <DisplayField label="Estimated value (USD)" value={formatMoney(deal.estimated_deal_value)} />
              <DisplayField label="Estimated close date" value={formatDate(deal.estimated_close_date)} />
              <DisplayField label="Commission type" value={deal.commission_type} />
              <div style={{ gridColumn: '1 / -1' }}>
                <DisplayField label="Deal notes" value={deal.deal_notes} />
              </div>
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
    </div>
  )
}
