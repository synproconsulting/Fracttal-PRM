import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

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

const CONFLICT_TONE = {
  not_checked: 'fp-badge--neutral',
  clear: 'fp-badge--success',
  conflict_detected: 'fp-badge--danger',
}

const CONFLICT_LABEL = {
  not_checked: 'Not Checked',
  clear: 'Clear ✅',
  conflict_detected: 'Conflict Detected ⚠️',
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

function ActionModal({ mode, deal, onClose, onConfirm, saving }) {
  const [text, setText] = useState('')
  const titles = {
    approve: 'Approve deal',
    reject: 'Reject deal',
    'request-info': 'Request additional information',
  }
  const labels = {
    approve: 'Approval notes (visible to partner)',
    reject: 'Reason for rejection (visible to partner)',
    'request-info': 'Message to partner (what is needed?)',
  }
  const confirmLabel = {
    approve: 'Confirm approve',
    reject: 'Confirm reject',
    'request-info': 'Send request',
  }[mode]
  const verb = {
    approve: 'Approving…',
    reject: 'Rejecting…',
    'request-info': 'Sending…',
  }[mode]
  const tone = mode === 'approve' ? 'fp-btn--success' : (mode === 'reject' ? 'fp-btn--solid-danger' : 'fp-btn--primary')

  return (
    <div className="fp-modal-overlay" role="dialog" aria-modal="true">
      <div className="fp-modal">
        <h3 className="fp-modal__title">{titles[mode]}</h3>
        <p className="fp-modal__subtitle">{deal.deal_name} — {deal.customer_name}</p>
        <div className="fp-field fp-field--filled">
          <textarea id="action-text" rows={5} placeholder=" "
                    value={text} onChange={(e) => setText(e.target.value)} />
          <label htmlFor="action-text">{labels[mode]}</label>
        </div>
        <div className="fp-modal__actions">
          <button type="button" onClick={onClose} disabled={saving} className="fp-btn fp-btn--ghost">Cancel</button>
          <button type="button" onClick={() => onConfirm(text)}
                  disabled={saving || !text.trim()} className={`fp-btn ${tone}`}>
            {saving ? verb : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}

function CancelInfoRequestModal({ deal, onClose, onConfirm, saving, error }) {
  return (
    <div className="fp-modal-overlay" role="dialog" aria-modal="true">
      <div className="fp-modal">
        <h3 className="fp-modal__title">Cancel info request?</h3>
        <p className="fp-modal__subtitle">{deal.deal_name} — {deal.customer_name}</p>
        {error && <div className="fp-alert fp-alert--danger" style={{ marginBottom: 12 }}>{error}</div>}
        <p style={{ margin: '8px 0 0', fontSize: 'var(--fp-fs-sm)' }}>
          Cancel the info request? The partner will no longer be prompted to provide
          additional information. The deal returns to Under Review and a system note is
          posted to the deal thread.
        </p>
        <div className="fp-modal__actions">
          <button type="button" onClick={onClose} disabled={saving} className="fp-btn fp-btn--ghost">Cancel</button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={saving}
            className="fp-btn fp-btn--primary"
          >
            {saving ? 'Cancelling…' : 'Cancel Info Request'}
          </button>
        </div>
      </div>
    </div>
  )
}


function ConflictOverrideModal({ deal, onClose, onConfirm, saving, error }) {
  const [notes, setNotes] = useState('')
  const tooShort = notes.trim().length < 10
  return (
    <div className="fp-modal-overlay" role="dialog" aria-modal="true">
      <div className="fp-modal">
        <h3 className="fp-modal__title">Override Conflict Decision</h3>
        <p className="fp-modal__subtitle">{deal.deal_name} — {deal.customer_name}</p>
        {error && <div className="fp-alert fp-alert--danger" style={{ marginBottom: 12 }}>{error}</div>}
        <div className="fp-field fp-field--filled">
          <textarea
            id="override-notes"
            rows={5}
            placeholder=" "
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
          <label htmlFor="override-notes">Override notes (min. 10 chars)</label>
        </div>
        <p style={{ margin: '4px 0 0', fontSize: 'var(--fp-fs-xs)', color: 'var(--fp-text-secondary)' }}>
          Explain why this conflict should be overridden. Appended to the deal's audit trail.
        </p>
        <div className="fp-modal__actions">
          <button type="button" onClick={onClose} disabled={saving} className="fp-btn fp-btn--ghost">Cancel</button>
          <button
            type="button"
            onClick={() => onConfirm(notes.trim())}
            disabled={saving || tooShort}
            className="fp-btn fp-btn--solid-danger"
          >
            {saving ? 'Overriding…' : 'Override — Mark as Clear'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function InternalDealDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const token = localStorage.getItem('token')

  const [deal, setDeal] = useState(null)
  const [messages, setMessages] = useState([])
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [sending, setSending] = useState(false)
  const [actionMode, setActionMode] = useState(null) // 'approve' | 'reject' | 'request-info'
  const [actionSaving, setActionSaving] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [overrideOpen, setOverrideOpen] = useState(false)
  const [overrideSaving, setOverrideSaving] = useState(false)
  const [overrideError, setOverrideError] = useState(null)
  const [cancelInfoOpen, setCancelInfoOpen] = useState(false)
  const [cancelInfoSaving, setCancelInfoSaving] = useState(false)
  const [cancelInfoError, setCancelInfoError] = useState(null)
  const [toast, setToast] = useState(null)

  async function fetchDeal() {
    const r = await fetch(`${API}/deal-registrations/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!r.ok) {
      const body = await r.json().catch(() => ({}))
      throw new Error(body.detail || `HTTP ${r.status}`)
    }
    return r.json()
  }

  async function fetchMessages() {
    const r = await fetch(`${API}/deal-registrations/${id}/messages`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!r.ok) return []
    return r.json()
  }

  useEffect(() => {
    if (!id || !token) return
    setLoading(true)
    Promise.all([fetchDeal(), fetchMessages()])
      .then(([d, msgs]) => { setDeal(d); setMessages(msgs) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, token, reloadKey])

  async function sendMessage() {
    if (!draft.trim() || sending) return
    setSending(true); setError(null)
    try {
      const r = await fetch(`${API}/deal-registrations/${id}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ message: draft.trim() }),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(body.detail || `HTTP ${r.status}`)
      setMessages((m) => [...m, body])
      setDraft('')
    } catch (e) {
      setError(e.message)
    } finally {
      setSending(false)
    }
  }

  async function startReview() {
    setActionSaving(true); setError(null)
    try {
      const r = await fetch(`${API}/internal/deals/${id}/start-review`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${r.status}`)
      }
      setReloadKey((k) => k + 1)
    } catch (e) {
      setError(e.message)
    } finally {
      setActionSaving(false)
    }
  }

  async function overrideConflict(notes) {
    setOverrideSaving(true)
    setOverrideError(null)
    try {
      const r = await fetch(`${API}/internal/deals/${id}/override-conflict`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ override_notes: notes }),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(body.detail || `HTTP ${r.status}`)
      setOverrideOpen(false)
      setToast('Conflict overridden')
      setReloadKey((k) => k + 1)
      window.setTimeout(() => setToast(null), 4000)
    } catch (e) {
      setOverrideError(e.message)
    } finally {
      setOverrideSaving(false)
    }
  }

  async function cancelInfoRequest() {
    setCancelInfoSaving(true); setCancelInfoError(null)
    try {
      const r = await fetch(`${API}/internal/deals/${id}/cancel-info-request`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(body.detail || `HTTP ${r.status}`)
      setCancelInfoOpen(false)
      setToast('Info request cancelled')
      setReloadKey((k) => k + 1)
      window.setTimeout(() => setToast(null), 4000)
    } catch (e) {
      setCancelInfoError(e.message)
    } finally {
      setCancelInfoSaving(false)
    }
  }

  async function submitAction(mode, text) {
    setActionSaving(true); setError(null)
    try {
      const isRequestInfo = mode === 'request-info'
      const body = isRequestInfo ? { message: text } : { review_notes: text }
      const r = await fetch(`${API}/internal/deals/${id}/${mode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      })
      const respBody = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(respBody.detail || `HTTP ${r.status}`)
      setActionMode(null)
      setReloadKey((k) => k + 1)
    } catch (e) {
      setError(e.message)
    } finally {
      setActionSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="fp-page" style={{ maxWidth: 1280, margin: '32px auto', padding: '0 32px' }}>
        <div className="fp-card" style={{ color: 'var(--fp-text-secondary)' }}>Loading deal…</div>
      </div>
    )
  }

  if (error && !deal) {
    return (
      <div className="fp-page" style={{ maxWidth: 1280, margin: '32px auto', padding: '0 32px' }}>
        <div className="fp-alert fp-alert--danger">{error}</div>
        <Link to="/internal/deals" className="fp-btn fp-btn--ghost" style={{ marginTop: 12 }}>Back to queue</Link>
      </div>
    )
  }

  if (!deal) return null

  const commissionLabel = deal.commission_rate_snapshot != null
    ? `${deal.commission_type || 'Commission'} — ${deal.commission_rate_snapshot}%`
    : 'Rate: Not resolved'

  return (
    <div className="fp-page" style={{ maxWidth: 1280, margin: '32px auto', padding: '0 32px' }}>
      <div style={{ fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)', marginBottom: 8 }}>
        <Link to="/internal/deals" style={{ color: 'inherit' }}>Deal Queue</Link> &nbsp;›&nbsp; {deal.deal_name || '(unnamed)'}
      </div>

      <div className="fp-page-header">
        <div>
          <h1 className="fp-page-title">{deal.deal_name || '(unnamed)'}</h1>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 6, flexWrap: 'wrap' }}>
            <span className={`fp-badge ${STATUS_TONE[deal.status] || 'fp-badge--neutral'}`}>
              {STATUS_LABEL[deal.status] || deal.status}
            </span>
            <span className="fp-badge fp-badge--neutral" title="Commission snapshot at submission">
              {commissionLabel}
            </span>
            <span style={{ fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>
              Partner: {deal.partner_legal_name || deal.partner_org_id}
            </span>
          </div>
        </div>
      </div>

      {error && <div className="fp-alert fp-alert--danger" style={{ marginBottom: 16 }}>{error}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 13fr) minmax(0, 7fr)', gap: 24 }}>
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

          <section className="fp-card" style={{ marginBottom: 16 }}>
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

          <section className="fp-card" style={{ marginBottom: 16 }}>
            <h2 className="fp-section-title">Commission snapshot</h2>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <DisplayField label="Commission type" value={deal.commission_type} />
              <DisplayField label="Rate at submission"
                            value={deal.commission_rate_snapshot != null ? `${deal.commission_rate_snapshot}%` : null} />
              <DisplayField label="Structure ID" value={deal.commission_structure_id} />
            </div>
            {deal.commission_rate_snapshot == null && deal.commission_structure_id == null && (
              <div style={{ marginTop: 12, fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>
                Commission rate not resolved at submission.
              </div>
            )}
          </section>

          <section className="fp-card">
            <h2 className="fp-section-title">Conflict Check</h2>
            <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 12 }}>
              <span className={`fp-badge ${CONFLICT_TONE[deal.conflict_status] || 'fp-badge--neutral'}`}>
                {CONFLICT_LABEL[deal.conflict_status] || deal.conflict_status}
              </span>
              {deal.conflict_checked_at && (
                <span style={{ fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>
                  Checked: {formatTimestamp(deal.conflict_checked_at)}
                </span>
              )}
            </div>
            {deal.conflict_status === 'not_checked' && (
              <div style={{ fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>
                No customer domain provided — conflict check skipped.
              </div>
            )}
            {deal.conflict_status === 'conflict_detected' && (
              <>
                {deal.conflict_notes && (
                  <div style={{ fontSize: 'var(--fp-fs-sm)', marginBottom: 12, whiteSpace: 'pre-wrap' }}>
                    {deal.conflict_notes}
                  </div>
                )}
                <button
                  type="button"
                  className="fp-btn fp-btn--solid-danger"
                  onClick={() => setOverrideOpen(true)}
                  disabled={overrideSaving}
                >
                  Override Conflict
                </button>
              </>
            )}
            {deal.conflict_status === 'clear' && deal.conflict_notes && (
              <div style={{ fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)', whiteSpace: 'pre-wrap' }}>
                {deal.conflict_notes}
              </div>
            )}
          </section>
        </div>

        <div>
          <section className="fp-card" style={{ marginBottom: 16 }}>
            <h2 className="fp-section-title">Collaboration</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 320, overflowY: 'auto', marginBottom: 16 }}>
              {messages.length === 0 && (
                <div style={{ color: 'var(--fp-text-secondary)', fontSize: 'var(--fp-fs-sm)' }}>No messages yet.</div>
              )}
              {messages.map((m) => (
                <div key={m.id} style={{
                  background: m.sender_type === 'internal' ? 'var(--fp-bg-muted)' : '#eef5ff',
                  padding: 12, borderRadius: 8,
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 'var(--fp-fs-xs)', color: 'var(--fp-text-secondary)' }}>
                    <strong style={{ color: 'var(--fp-text-primary)' }}>
                      {m.sender_type === 'internal' ? `Fracttal (${m.sender_email})` : `Partner (${m.sender_email})`}
                    </strong>
                    <span>{formatTimestamp(m.created_at)}</span>
                  </div>
                  <div style={{ marginTop: 6, whiteSpace: 'pre-wrap' }}>{m.message}</div>
                </div>
              ))}
            </div>

            <div style={{ borderTop: '1px solid var(--fp-border)', paddingTop: 16 }}>
              <textarea rows={3} placeholder="Type a message…" value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        style={{ width: '100%', boxSizing: 'border-box', marginBottom: 12 }} />
              <button type="button" className="fp-btn fp-btn--secondary"
                      onClick={sendMessage} disabled={sending || !draft.trim()}>
                {sending ? 'Sending…' : 'Send message'}
              </button>
            </div>
          </section>

          <section className="fp-card">
            <h2 className="fp-section-title">Quick actions</h2>
            {deal.status === 'submitted' && (
              <button type="button" className="fp-btn fp-btn--primary"
                      disabled={actionSaving} onClick={startReview}>
                {actionSaving ? 'Starting…' : 'Start review'}
              </button>
            )}
            {deal.status === 'under_review' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <button type="button" className="fp-btn fp-btn--ghost"
                        onClick={() => setActionMode('request-info')} disabled={actionSaving}>
                  Request info
                </button>
                <button type="button" className="fp-btn fp-btn--success"
                        onClick={() => setActionMode('approve')} disabled={actionSaving}>
                  Approve
                </button>
                <button type="button" className="fp-btn fp-btn--danger"
                        onClick={() => setActionMode('reject')} disabled={actionSaving}>
                  Reject
                </button>
              </div>
            )}
            {deal.status === 'info_required' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ color: 'var(--fp-text-secondary)', fontSize: 'var(--fp-fs-sm)' }}>
                  Awaiting partner response.
                </div>
                <button
                  type="button"
                  className="fp-btn fp-btn--ghost"
                  onClick={() => setCancelInfoOpen(true)}
                  disabled={cancelInfoSaving}
                >
                  Cancel Info Request
                </button>
              </div>
            )}
            {deal.status === 'approved' && (
              <div className="fp-alert fp-alert--success" style={{ margin: 0 }}>
                <div><strong>Approved</strong> {deal.reviewed_at && `on ${formatDate(deal.reviewed_at)}`}</div>
                {deal.review_notes && <div style={{ marginTop: 6 }}>{deal.review_notes}</div>}
              </div>
            )}
            {deal.status === 'rejected' && (
              <div className="fp-alert fp-alert--danger" style={{ margin: 0 }}>
                <div><strong>Rejected</strong> {deal.reviewed_at && `on ${formatDate(deal.reviewed_at)}`}</div>
                {deal.review_notes && <div style={{ marginTop: 6 }}>{deal.review_notes}</div>}
              </div>
            )}
            {(deal.status === 'draft' || deal.status === 'expired') && (
              <div style={{ color: 'var(--fp-text-muted)', fontSize: 'var(--fp-fs-sm)' }}>
                No actions available in this status.
              </div>
            )}
          </section>
        </div>
      </div>

      {actionMode && (
        <ActionModal
          mode={actionMode}
          deal={deal}
          saving={actionSaving}
          onClose={() => setActionMode(null)}
          onConfirm={(text) => submitAction(actionMode, text)}
        />
      )}

      {overrideOpen && (
        <ConflictOverrideModal
          deal={deal}
          saving={overrideSaving}
          error={overrideError}
          onClose={() => { setOverrideOpen(false); setOverrideError(null) }}
          onConfirm={overrideConflict}
        />
      )}

      {cancelInfoOpen && (
        <CancelInfoRequestModal
          deal={deal}
          saving={cancelInfoSaving}
          error={cancelInfoError}
          onClose={() => { setCancelInfoOpen(false); setCancelInfoError(null) }}
          onConfirm={cancelInfoRequest}
        />
      )}

      {toast && (
        <div
          role="status"
          style={{
            position: 'fixed',
            bottom: 24,
            right: 24,
            background: '#1b8743',
            color: '#fff',
            padding: '12px 18px',
            borderRadius: 8,
            boxShadow: '0 6px 24px rgba(0,0,0,0.15)',
            fontSize: 'var(--fp-fs-sm)',
            zIndex: 50,
          }}
        >
          {toast}
        </div>
      )}
    </div>
  )
}
