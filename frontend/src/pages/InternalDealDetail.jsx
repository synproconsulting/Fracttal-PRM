import { useEffect, useMemo, useState } from 'react'

import { Link, useNavigate, useParams } from 'react-router-dom'

import QuoteForm from './QuoteForm.jsx'
import QuoteDetail from './QuoteDetail.jsx'



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

  lost: 'fp-badge--danger',

  withdrawn: 'fp-badge--neutral',

}



const STATUS_LABEL = {

  draft: 'Draft',

  submitted: 'Submitted',

  under_review: 'Under review',

  info_required: 'Info required',

  approved: 'Approved',

  rejected: 'Rejected',

  expired: 'Expired',

  lost: 'Lost',

  withdrawn: 'Withdrawn',

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



// Read-only field maps shared between the Customer State and Needs Assessment
// section below. Labels mirror the partner-portal deal form.

const _DI_SYSTEMS = [

  { key: 'current_system',    label: 'Current System' },

  { key: 'old_system',        label: 'Old System' },

  { key: 'inventory_stores',  label: 'Inventory / Stores' },

  { key: 'work_orders_prs',   label: 'Work Orders & PRs' },

  { key: 'monitoring_system', label: 'Monitoring' },

]

const _DI_FEATURES = [

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

const _DI_NARRATIVES = [

  { key: 'about_client',   label: 'About the Client' },

  { key: 'pain',           label: 'Pain (P)' },

  { key: 'impact',         label: 'Impact (I)' },

  { key: 'critical_event', label: 'Critical Event (CE)' },

  { key: 'decision',       label: 'Decision (D)' },

  { key: 'next_steps',     label: 'Next Steps' },

]

function _featureIcon(v) {

  if (v === true) return '✅'

  if (v === false) return '❌'

  return '—'

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
  // Post-Sprint 20 PR B -- Edit Deal modal state. Only system_admin /
  // channel_ops_admin see the entry point; both modal open and save are
  // gated by that check on the server too.
  const [editOpen, setEditOpen] = useState(false)
  const [editSaving, setEditSaving] = useState(false)
  const [editError, setEditError] = useState(null)

  // FPRM-274 / Sprint 17 — role of the logged-in reviewer, used to gate the
  // Approve button when multi-step workflow has a role-specific step.
  const [currentUserRole, setCurrentUserRole] = useState(null)
  const canEditDeal = currentUserRole === 'system_admin' || currentUserRole === 'channel_ops_admin'
  const canRerunConflict = (
    currentUserRole === 'system_admin'
    || currentUserRole === 'channel_ops_admin'
    || currentUserRole === 'channel_manager'
  )
  // Mark Lost / Mark Withdrawn buttons are gated to the review roles
  // (channel_manager + channel_ops_admin + system_admin) and only shown
  // when the deal is in a status the backend permits transitioning out of.
  const canTerminate = (
    currentUserRole === 'system_admin'
    || currentUserRole === 'channel_ops_admin'
    || currentUserRole === 'channel_manager'
  )
  const [conflictRerunning, setConflictRerunning] = useState(false)

  useEffect(() => {
    if (!token) return
    fetch(`${API}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then((me) => { if (me?.role) setCurrentUserRole(me.role) })
      .catch(() => {})
  }, [token])



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



  async function saveDealEdits(patchPayload) {
    setEditSaving(true)
    setEditError(null)
    try {
      const r = await fetch(`${API}/deal-registrations/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(patchPayload),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) {
        const msg = typeof body.detail === 'string'
          ? body.detail
          : JSON.stringify(body.detail || body)
        throw new Error(msg || `HTTP ${r.status}`)
      }
      setEditOpen(false)
      setToast('Deal updated')
      setReloadKey((k) => k + 1)
      window.setTimeout(() => setToast(null), 4000)
      return true
    } catch (e) {
      setEditError(e.message)
      return false
    } finally {
      setEditSaving(false)
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



  async function rerunConflictCheck() {
    if (conflictRerunning) return
    setConflictRerunning(true)
    setError(null)
    try {
      const r = await fetch(`${API}/internal/deals/${id}/conflict-check`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) {
        const msg = typeof body.detail === 'string'
          ? body.detail
          : JSON.stringify(body.detail || body)
        throw new Error(msg || `HTTP ${r.status}`)
      }
      const verdict = body.conflict_status === 'clear'
        ? 'clear'
        : body.conflict_status === 'conflict_detected'
          ? 'conflict detected'
          : body.conflict_status
      setToast(`Conflict check complete — ${verdict}`)
      setReloadKey((k) => k + 1)
      window.setTimeout(() => setToast(null), 4000)
    } catch (e) {
      setError(e.message)
    } finally {
      setConflictRerunning(false)
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



  async function setTerminalStatus(newStatus) {
    setActionSaving(true); setError(null)
    try {
      const r = await fetch(`${API}/deal-registrations/${id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status: newStatus }),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) {
        const msg = typeof body.detail === 'string'
          ? body.detail
          : JSON.stringify(body.detail || body)
        throw new Error(msg || `HTTP ${r.status}`)
      }
      const label = newStatus === 'lost' ? 'Lost' : 'Withdrawn'
      setToast(`Deal marked as ${label}`)
      setReloadKey((k) => k + 1)
      window.setTimeout(() => setToast(null), 4000)
    } catch (e) {
      setError(e.message)
    } finally {
      setActionSaving(false)
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



      <div className="fp-page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>

        <div>

          <h1 className="fp-page-title">{deal.deal_name || '(unnamed)'}</h1>

          <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 6, flexWrap: 'wrap' }}>

            <span className={`fp-badge ${STATUS_TONE[deal.status] || 'fp-badge--neutral'}`}>

              {STATUS_LABEL[deal.status] || deal.status}

            </span>

            <span className="fp-badge fp-badge--neutral" title="Commission snapshot at submission">

              {commissionLabel}

            </span>

            {deal.created_on_behalf_of && (

              <span className="fp-badge fp-badge--neutral" title="Created by a channel manager on behalf of the partner">

                Created by Channel Manager

              </span>

            )}

            <span style={{ fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>

              Partner: {deal.partner_legal_name || deal.partner_org_id}

            </span>

            <DealHeaderQuoteBadge dealId={deal.id} />

          </div>

        </div>

        {canEditDeal && (
          <button
            type="button"
            className="fp-btn fp-btn--secondary"
            onClick={() => { setEditError(null); setEditOpen(true) }}
            title="Edit deal fields (system_admin / channel_ops_admin)"
          >
            Edit Deal
          </button>
        )}

      </div>



      {error && <div className="fp-alert fp-alert--danger" style={{ marginBottom: 16 }}>{error}</div>}



      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 13fr) minmax(0, 7fr)', gap: 24 }}>

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

              <DisplayField label="Industry sector" value={deal.industry_sector} />

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



          <section className="fp-card" style={{ marginBottom: 16 }}>

            <h2 className="fp-section-title">Current State and Needs Assessment</h2>

            {/* About the Client -- full-width narrative */}

            <div style={{ marginBottom: 20 }}>

              <div style={{ fontSize: 'var(--fp-fs-xs)', fontWeight: 600, color: 'var(--fp-text-secondary)', marginBottom: 2 }}>About the Client</div>

              <div style={{ whiteSpace: 'pre-wrap', fontSize: 'var(--fp-fs-sm)' }}>{deal.about_client || '—'}</div>

            </div>

            <h3 style={{ margin: '0 0 8px', fontSize: 'var(--fp-fs-md)', fontWeight: 600 }}>Situation (S) — Current Systems</h3>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>

              {_DI_SYSTEMS.map((f) => (

                <DisplayField key={f.key} label={f.label} value={deal[f.key]} />

              ))}

            </div>

            <h3 style={{ margin: '0 0 8px', fontSize: 'var(--fp-fs-md)', fontWeight: 600 }}>Features Required</h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px 16px', marginBottom: 12, fontSize: 'var(--fp-fs-sm)' }}>

              {_DI_FEATURES.map((f) => (

                <div key={f.key}>{_featureIcon(deal[f.key])} {f.label}</div>

              ))}

            </div>

            {(deal.integration_with || deal.languages_required) && (

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>

                {deal.integration_with && <DisplayField label="Integrate with" value={deal.integration_with} />}

                {deal.languages_required && <DisplayField label="Languages required" value={deal.languages_required} />}

              </div>

            )}

            {/* SPICED narrative fields rendered directly, no sub-heading */}

            <div style={{ display: 'grid', gap: 12 }}>

              {_DI_NARRATIVES.filter((f) => f.key !== 'about_client').map((f) => (

                <div key={f.key}>

                  <div style={{ fontSize: 'var(--fp-fs-xs)', fontWeight: 600, color: 'var(--fp-text-secondary)', marginBottom: 2 }}>{f.label}</div>

                  <div style={{ whiteSpace: 'pre-wrap', fontSize: 'var(--fp-fs-sm)' }}>{deal[f.key] || '—'}</div>

                </div>

              ))}

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

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, gap: 12 }}>

              <h2 className="fp-section-title" style={{ margin: 0 }}>Conflict Check</h2>

              {canRerunConflict && (
                <button
                  type="button"
                  className="fp-btn fp-btn--secondary fp-btn--sm"
                  onClick={rerunConflictCheck}
                  disabled={conflictRerunning}
                  title="Re-evaluate against currently active deals on the same customer domain"
                >
                  {conflictRerunning ? 'Checking…' : 'Re-run Conflict Check'}
                </button>
              )}

            </div>

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

            {deal.status === 'under_review' && (() => {
              const ap = deal.approval_progress
              const roleMismatch = (
                ap && ap.current_required_role && currentUserRole &&
                currentUserRole !== ap.current_required_role
              )
              const approveTitle = roleMismatch
                ? `This step requires role: ${ap.current_required_role}`
                : undefined
              return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

                {ap && (
                  <div style={{
                    padding: 10, borderRadius: 6, background: 'var(--fp-bg, #f5f7fa)',
                    fontSize: 'var(--fp-fs-sm)',
                  }}>
                    <div style={{ fontWeight: 600 }}>
                      {ap.current_step_order
                        ? `Step ${ap.current_step_order} of ${ap.total_steps} — ${ap.current_step_name}`
                        : `All ${ap.total_steps} steps complete`}
                    </div>
                    {ap.current_required_role && (
                      <div style={{ color: 'var(--fp-text-secondary)', marginTop: 2 }}>
                        Requires role: <code>{ap.current_required_role}</code>
                      </div>
                    )}
                    <div style={{ display: 'flex', gap: 4, marginTop: 6 }}>
                      {Array.from({ length: ap.total_steps }, (_, i) => (
                        <span key={i} style={{
                          width: 18, height: 6, borderRadius: 3,
                          background: i < ap.completed_steps ? '#22c55e' : '#cbd5e1',
                        }} />
                      ))}
                    </div>
                  </div>
                )}

                <button type="button" className="fp-btn fp-btn--ghost"

                        onClick={() => setActionMode('request-info')} disabled={actionSaving}>

                  Request info

                </button>

                <button type="button" className="fp-btn fp-btn--success"

                        onClick={() => setActionMode('approve')}
                        disabled={actionSaving || roleMismatch}
                        title={approveTitle}>

                  {roleMismatch ? `Approve (requires ${ap.current_required_role})` : 'Approve'}

                </button>

                <button type="button" className="fp-btn fp-btn--danger"

                        onClick={() => setActionMode('reject')} disabled={actionSaving}>

                  Reject

                </button>

              </div>
              )
            })()}

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

            {deal.status === 'lost' && (

              <div className="fp-alert fp-alert--danger" style={{ margin: 0 }}>

                <div><strong>Lost</strong></div>

              </div>

            )}

            {deal.status === 'withdrawn' && (

              <div className="fp-alert fp-alert--neutral" style={{ margin: 0 }}>

                <div><strong>Withdrawn</strong></div>

              </div>

            )}

            {canTerminate && (deal.status === 'submitted' || deal.status === 'under_review' || deal.status === 'approved') && (

              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 10 }}>

                {deal.status === 'approved' && (

                  <button type="button" className="fp-btn fp-btn--danger"

                          disabled={actionSaving}

                          onClick={() => {

                            if (window.confirm('Mark this deal as Lost? This cannot be undone.')) {

                              setTerminalStatus('lost')

                            }

                          }}>

                    Mark as Lost

                  </button>

                )}

                <button type="button" className="fp-btn fp-btn--ghost"

                        disabled={actionSaving}

                        onClick={() => {

                          if (window.confirm('Mark this deal as Withdrawn? This cannot be undone.')) {

                            setTerminalStatus('withdrawn')

                          }

                        }}>

                  Mark as Withdrawn

                </button>

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




      <QuotesSection
        dealId={deal.id}
        dealQtyTransactional={deal.qty_transactional_users ?? 1}
        dealQtyLimitedTech={deal.qty_limited_tech_users ?? 0}
        currentUserRole={currentUserRole}
        setToast={setToast}
      />

      <ChangeLogSection dealId={deal.id} reloadKey={reloadKey} />

      {editOpen && (
        <EditDealModal
          deal={deal}
          saving={editSaving}
          error={editError}
          onClose={() => { if (!editSaving) { setEditOpen(false); setEditError(null) } }}
          onSave={saveDealEdits}
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

function QuotesSection({ dealId, dealQtyTransactional, dealQtyLimitedTech, currentUserRole, setToast }) {
  const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
    || 'https://fracttal-prm-backend-production.up.railway.app'
  const token = localStorage.getItem('token')
  const [quotes, setQuotes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [viewQuoteId, setViewQuoteId] = useState(null)
  const [versionFormFor, setVersionFormFor] = useState(null) // {quoteId, initialValues}
  const [reloadKey, setReloadKey] = useState(0)
  const [pipelineSaving, setPipelineSaving] = useState(() => new Set())
  const canTogglePipeline = (
    currentUserRole === 'system_admin'
    || currentUserRole === 'channel_ops_admin'
    || currentUserRole === 'channel_manager'
  )

  async function togglePipeline(q) {
    const next = !q.include_in_pipeline
    setQuotes((prev) => prev.map((x) => (x.id === q.id ? { ...x, include_in_pipeline: next } : x)))
    setPipelineSaving((prev) => { const s = new Set(prev); s.add(q.id); return s })
    try {
      const r = await fetch(`${API}/quotes/${q.id}/pipeline-inclusion`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ include_in_pipeline: next }),
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      refresh()
    } catch (e) {
      setQuotes((prev) => prev.map((x) => (x.id === q.id ? { ...x, include_in_pipeline: !next } : x)))
      if (typeof setToast === 'function') {
        setToast('Failed to update pipeline inclusion')
        window.setTimeout(() => setToast(null), 4000)
      }
    } finally {
      setPipelineSaving((prev) => { const s = new Set(prev); s.delete(q.id); return s })
    }
  }

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
      .then((q) => setQuotes(q))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [dealId, token, reloadKey])

  function refresh() { setReloadKey((k) => k + 1) }

  function fmtMoney(v) {
    if (v === null || v === undefined || v === '') return '—'
    const n = Number(v); if (!Number.isFinite(n)) return '—'
    return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }

  return (
    <section className="fp-card" style={{ marginTop: 24 }}>
      <style>{`@keyframes fp-quote-pipeline-spin { to { transform: rotate(360deg); } }`}</style>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h2 className="fp-section-title" style={{ margin: 0 }}>Quotes</h2>
        <button type="button" onClick={() => setShowForm(true)} className="fp-btn fp-btn--primary">
          + New Quote
        </button>
      </div>
      {loading && <div style={{ color: '#64748B' }}>Loading quotes…</div>}
      {error && <div className="fp-alert fp-alert--danger">{error}</div>}
      {!loading && !error && quotes.length === 0 && (
        <div style={{ color: '#94A3B8', padding: 16, textAlign: 'center' }}>
          No quotes yet — click <strong>New Quote</strong> to create one.
        </div>
      )}
      {!loading && quotes.length > 0 && (
        <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: '#F5F7FA' }}>
              <th style={{ textAlign: 'left', padding: 8 }}>Name</th>
              <th style={{ textAlign: 'left', padding: 8 }}>Currency</th>
              <th style={{ textAlign: 'right', padding: 8 }}>Active Ver.</th>
              <th style={{ textAlign: 'left', padding: 8 }}>Status</th>
              <th style={{ textAlign: 'center', padding: 8 }}>Pipeline</th>
              <th style={{ textAlign: 'right', padding: 8 }}>Grand Total</th>
              <th style={{ textAlign: 'left', padding: 8 }}>Created</th>
              <th style={{ textAlign: 'right', padding: 8 }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {quotes.map((q) => (
              <tr key={q.id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                <td style={{ padding: 8 }}>{q.quote_name || 'Untitled'}</td>
                <td style={{ padding: 8 }}>{q.currency_code}</td>
                <td style={{ padding: 8, textAlign: 'right' }}>v{q.active_version}</td>
                <td style={{ padding: 8 }}>{q.status}</td>
                <td style={{ padding: 8, textAlign: 'center' }}>
                  {canTogglePipeline ? (
                    pipelineSaving.has(q.id) ? (
                      <span
                        aria-label="Saving"
                        style={{
                          display: 'inline-block',
                          width: 14,
                          height: 14,
                          border: '2px solid #CBD5E1',
                          borderTopColor: '#1A6EBB',
                          borderRadius: '50%',
                          animation: 'fp-quote-pipeline-spin 0.8s linear infinite',
                          verticalAlign: 'middle',
                        }}
                      />
                    ) : (
                      <input
                        type="checkbox"
                        checked={!!q.include_in_pipeline}
                        onChange={() => togglePipeline(q)}
                        aria-label="Include in pipeline"
                      />
                    )
                  ) : (
                    <span aria-label={q.include_in_pipeline ? 'In pipeline' : 'Not in pipeline'}>
                      {q.include_in_pipeline ? '✅' : '—'}
                    </span>
                  )}
                </td>
                <td style={{ padding: 8, textAlign: 'right' }}>{fmtMoney(q.grand_total_after_discount)}</td>
                <td style={{ padding: 8 }}>{q.created_at ? new Date(q.created_at).toLocaleDateString() : '—'}</td>
                <td style={{ padding: 8, textAlign: 'right' }}>
                  <button type="button" onClick={() => setViewQuoteId(q.id)} className="fp-btn fp-btn--ghost" style={{ marginRight: 6 }}>View</button>
                  <button type="button" onClick={() => setVersionFormFor({ quoteId: q.id, initialValues: null })} className="fp-btn fp-btn--ghost">+ Version</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {showForm && (
        <div className="fp-modal-overlay" role="dialog" aria-modal="true">
          <div className="fp-modal" style={{ maxWidth: 1100, width: '90vw', maxHeight: '90vh', overflowY: 'auto' }}>
            <h3 className="fp-modal__title">New Quote</h3>
            <QuoteForm
              dealId={dealId}
              quoteId={null}
              dealQtyTransactional={dealQtyTransactional}
              dealQtyLimitedTech={dealQtyLimitedTech}
              onSuccess={() => { setShowForm(false); refresh() }}
              onCancel={() => setShowForm(false)}
            />
          </div>
        </div>
      )}

      {versionFormFor && (
        <div className="fp-modal-overlay" role="dialog" aria-modal="true">
          <div className="fp-modal" style={{ maxWidth: 1100, width: '90vw', maxHeight: '90vh', overflowY: 'auto' }}>
            <h3 className="fp-modal__title">New Version</h3>
            <QuoteForm
              dealId={dealId}
              quoteId={versionFormFor.quoteId}
              dealQtyTransactional={dealQtyTransactional}
              dealQtyLimitedTech={dealQtyLimitedTech}
              initialValues={versionFormFor.initialValues}
              onSuccess={() => { setVersionFormFor(null); refresh() }}
              onCancel={() => setVersionFormFor(null)}
            />
          </div>
        </div>
      )}

      {viewQuoteId && (
        <div className="fp-modal-overlay" role="dialog" aria-modal="true">
          <div className="fp-modal" style={{ maxWidth: 1200, width: '90vw', maxHeight: '90vh', overflowY: 'auto' }}>
            <QuoteDetail
              quoteId={viewQuoteId}
              includeInPipeline={!!quotes.find((x) => x.id === viewQuoteId)?.include_in_pipeline}
              onPipelineChange={refresh}
              onClose={() => { setViewQuoteId(null); refresh() }}
              onAddVersion={(quote) => {
                const active = quote.active_version_data
                const init = active ? {
                  featurePlan: active.feature_plan,
                  featurePlanDiscountPct: Number(active.feature_plan_discount_pct) || 0,
                  qtyTransactional: active.qty_transactional_users,
                  qtyLimitedTech: active.qty_limited_tech_users,
                  selectedAddonKeys: active.selected_addons || [],
                  scenarioLabel: active.scenario_label || '',
                } : null
                setViewQuoteId(null)
                setVersionFormFor({ quoteId: quote.id, initialValues: init })
              }}
            />
          </div>
        </div>
      )}
    </section>
  )
}


function DealHeaderQuoteBadge({ dealId }) {
  const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
    || 'https://fracttal-prm-backend-production.up.railway.app'
  const token = localStorage.getItem('token')
  const [primary, setPrimary] = useState(null)
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    if (!dealId || !token) return
    fetch(`${API}/deals/${dealId}/quotes`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (r) => (r.ok ? r.json() : []))
      .then((quotes) => {
        if (!Array.isArray(quotes) || quotes.length === 0) { setPrimary(null); return }
        const priority = { accepted: 3, sent: 2, draft: 1, expired: 0 }
        const sorted = [...quotes].sort((a, b) => (priority[b.status] || 0) - (priority[a.status] || 0))
        setPrimary(sorted[0])
      })
      .catch(() => setPrimary(null))
      .finally(() => setLoaded(true))
  }, [dealId, token])

  if (!loaded) return null

  if (!primary) {
    return (
      <span style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        padding: '4px 10px', borderRadius: 6,
        border: '1px dashed #1A6EBB', color: '#1A6EBB',
        fontSize: 12, fontWeight: 600,
      }}>
        No quote yet
      </span>
    )
  }

  const tone = primary.status === 'accepted'
    ? { bg: '#E6F4EA', fg: '#1B8743', border: '#4CAF50' }
    : primary.status === 'sent'
    ? { bg: '#EBF4FF', fg: '#1A6EBB', border: '#1A6EBB' }
    : { bg: '#F5F7FA', fg: '#475569', border: '#CBD5E1' }
  const sym = (primary.currency_code && primary.currency_code !== 'USD') ? `${primary.currency_code} ` : '$'
  const totalNum = Number(primary.grand_total_after_discount)
  const totalStr = Number.isFinite(totalNum)
    ? `${sym}${totalNum.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
    : '—'

  return (
    <span title="Most relevant quote on this deal" style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '4px 10px', borderRadius: 6,
      background: tone.bg, color: tone.fg, border: `1px solid ${tone.border}`,
      fontSize: 12, fontWeight: 600,
    }}>
      <span style={{ textTransform: 'capitalize' }}>
        {primary.status === 'accepted' ? '✓ ' : ''}Quote: {primary.status}
      </span>
      <span style={{ opacity: 0.75 }}>·</span>
      <span>v{primary.active_version}</span>
      <span style={{ opacity: 0.75 }}>·</span>
      <span style={{ fontVariantNumeric: 'tabular-nums' }}>{totalStr}</span>
    </span>
  )
}


// ============================================================================
// Post-Sprint 20 PR B -- Edit Deal modal + Change Log section
// ============================================================================

const EDIT_SECTIONS = [
  {
    title: 'Customer information',
    fields: [
      { key: 'customer_name', label: 'Company name', type: 'text', required: true },
      { key: 'customer_domain', label: 'Customer domain', type: 'text' },
      { key: 'customer_contact_name', label: 'Contact name', type: 'text' },
      { key: 'customer_contact_position', label: 'Contact title', type: 'text' },
      { key: 'customer_contact_email', label: 'Contact email', type: 'email' },
      { key: 'customer_contact_phone', label: 'Contact phone', type: 'tel' },
      { key: 'customer_region', label: 'Region / state', type: 'text' },
      {
        key: 'customer_industry', label: 'Industry', type: 'select',
        options: [
          '', 'Manufacturing', 'Mining', 'Energy & Utilities', 'Healthcare',
          'Hospitality', 'Logistics & Transportation', 'Real Estate',
          'Food & Beverage', 'Education', 'Retail', 'Government', 'Other',
        ],
      },
      { key: 'industry_sector', label: 'Industry sector', type: 'text' },
      {
        key: 'customer_country', label: 'Country', type: 'select',
        options: [
          '', 'Argentina', 'Brazil', 'Chile', 'Colombia', 'Costa Rica', 'Ecuador',
          'Mexico', 'Panama', 'Paraguay', 'Peru', 'Uruguay', 'United States', 'Other',
        ],
      },
      {
        key: 'company_size', label: 'Company size', type: 'select',
        options: ['', '1-10', '11-50', '51-200', '201-500', '500+'],
      },
    ],
  },
  {
    title: 'Partner contact information',
    fields: [
      { key: 'prospect_contact_name', label: 'Partner contact name', type: 'text' },
      { key: 'prospect_contact_position', label: 'Partner contact title', type: 'text' },
      { key: 'prospect_phone', label: 'Partner contact phone', type: 'tel' },
      { key: 'prospect_website', label: 'Partner website / LinkedIn', type: 'url' },
      { key: 'compiled_by', label: 'Compiled by', type: 'text' },
    ],
  },
  {
    title: 'Deal information',
    fields: [
      { key: 'deal_name', label: 'Deal name', type: 'text', required: true },
      { key: 'estimated_deal_value', label: 'Estimated deal value (USD)', type: 'number' },
      { key: 'estimated_close_date', label: 'Estimated close date', type: 'date' },
      { key: 'engagement_date', label: 'Engagement date', type: 'date' },
      { key: 'qty_transactional_users', label: 'Requested Qty Transactional User Licenses', type: 'number', min: 0 },
      { key: 'qty_limited_tech_users', label: 'Requested Qty Limited Technician User Licenses', type: 'number', min: 0 },
      {
        key: 'feature_plan_preference', label: 'Indicative feature plan', type: 'select',
        options: ['', 'starter', 'professional', 'enterprise'],
      },
      { key: 'deal_notes', label: 'Deal notes', type: 'textarea' },
    ],
  },
  {
    title: 'Current State and Needs Assessment',
    fields: [
      { key: 'about_client', label: 'About the Client', type: 'textarea' },
      { key: 'current_system', label: 'Current System', type: 'text' },
      { key: 'old_system', label: 'Old System', type: 'text' },
      { key: 'inventory_stores', label: 'Inventory / Stores', type: 'text' },
      { key: 'work_orders_prs', label: 'Work Orders & PRs', type: 'text' },
      { key: 'monitoring_system', label: 'Monitoring', type: 'text' },
      { key: 'integration_with', label: 'Integrate with', type: 'text' },
      { key: 'languages_required', label: 'Languages required', type: 'text' },
      { key: 'pain', label: 'Pain (P)', type: 'textarea' },
      { key: 'impact', label: 'Impact (I)', type: 'textarea' },
      { key: 'critical_event', label: 'Critical Event (CE)', type: 'textarea' },
      { key: 'decision', label: 'Decision (D)', type: 'textarea' },
      { key: 'next_steps', label: 'Next Steps', type: 'textarea' },
    ],
  },
]

const NUMERIC_EDIT_KEYS = new Set([
  'estimated_deal_value', 'qty_transactional_users', 'qty_limited_tech_users',
])

function EditDealModal({ deal, saving, error, onClose, onSave }) {
  // Local form state seeded from the current deal -- the modal is the source
  // of truth while it's open. Cancel discards by simply unmounting.
  const initial = useMemo(() => {
    const out = {}
    for (const section of EDIT_SECTIONS) {
      for (const f of section.fields) {
        const v = deal[f.key]
        out[f.key] = v === null || v === undefined ? '' : v
      }
    }
    return out
  }, [deal])
  const [values, setValues] = useState(initial)

  function setField(key, v) {
    setValues((cur) => ({ ...cur, [key]: v }))
  }

  function buildPatchPayload() {
    const payload = {}
    for (const section of EDIT_SECTIONS) {
      for (const f of section.fields) {
        const v = values[f.key]
        const before = deal[f.key]
        // Only send fields that actually changed -- avoids spurious audit
        // events for fields the admin opened in the modal but didn't touch.
        const norm = (x) => (x === '' || x === null || x === undefined ? null : x)
        const beforeNorm = norm(before)
        let afterNorm = norm(v)
        if (afterNorm !== null && NUMERIC_EDIT_KEYS.has(f.key)) {
          const num = Number(afterNorm)
          afterNorm = Number.isFinite(num) ? num : null
        }
        if (String(beforeNorm) !== String(afterNorm)) {
          payload[f.key] = afterNorm
        }
      }
    }
    return payload
  }

  async function handleSave() {
    const payload = buildPatchPayload()
    if (Object.keys(payload).length === 0) {
      onClose()
      return
    }
    await onSave(payload)
  }

  return (
    <div className="fp-modal-overlay" role="dialog" aria-modal="true">
      <div className="fp-modal" style={{ maxWidth: 1100, width: '92vw', maxHeight: '92vh', overflowY: 'auto' }}>
        <h3 className="fp-modal__title">Edit deal</h3>
        <p className="fp-modal__subtitle">
          {deal.deal_name} — {deal.customer_name}
        </p>
        {error && <div className="fp-alert fp-alert--danger" style={{ marginBottom: 12 }}>{error}</div>}

        {EDIT_SECTIONS.map((section) => (
          <section key={section.title} style={{ marginBottom: 20 }}>
            <h4 style={{ margin: '0 0 8px', fontSize: 'var(--fp-fs-md)', fontWeight: 600 }}>
              {section.title}
            </h4>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              {section.fields.map((f) => {
                const isFullWidth = f.type === 'textarea'
                return (
                  <div key={f.key} style={isFullWidth ? { gridColumn: '1 / -1' } : undefined}>
                    <label style={{ display: 'block', fontSize: 12, color: '#64748B', fontWeight: 600, marginBottom: 4 }}>
                      {f.label}{f.required ? ' *' : ''}
                    </label>
                    {f.type === 'textarea' ? (
                      <textarea
                        rows={3}
                        value={values[f.key] ?? ''}
                        onChange={(e) => setField(f.key, e.target.value)}
                        style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', borderRadius: 6, border: '1px solid #E0E4EA' }}
                      />
                    ) : f.type === 'select' ? (
                      <select
                        value={values[f.key] ?? ''}
                        onChange={(e) => setField(f.key, e.target.value)}
                        style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #E0E4EA' }}
                      >
                        {f.options.map((opt) => (
                          <option key={opt} value={opt}>{opt === '' ? '(none)' : opt}</option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type={f.type}
                        min={f.min}
                        required={f.required}
                        value={values[f.key] ?? ''}
                        onChange={(e) => setField(f.key, e.target.value)}
                        style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', borderRadius: 6, border: '1px solid #E0E4EA' }}
                      />
                    )}
                  </div>
                )
              })}
            </div>
          </section>
        ))}

        <div className="fp-modal__actions">
          <button type="button" onClick={onClose} disabled={saving} className="fp-btn fp-btn--ghost">
            Cancel
          </button>
          <button type="button" onClick={handleSave} disabled={saving} className="fp-btn fp-btn--primary">
            {saving ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  )
}


// Human-friendly labels for the Change Log. Keys not in this map fall back
// to the raw column name so newly-added fields still render correctly.
const CHANGE_LOG_FIELD_LABELS = {
  customer_name: 'Company name',
  customer_domain: 'Customer domain',
  customer_contact_name: 'Contact name',
  customer_contact_position: 'Contact title',
  customer_contact_email: 'Contact email',
  customer_contact_phone: 'Contact phone',
  customer_industry: 'Industry',
  industry_sector: 'Industry sector',
  customer_country: 'Country',
  customer_region: 'Region / state',
  company_size: 'Company size',
  deal_name: 'Deal name',
  estimated_deal_value: 'Estimated value',
  estimated_close_date: 'Estimated close date',
  engagement_date: 'Engagement date',
  qty_transactional_users: 'Qty Transactional Users',
  qty_limited_tech_users: 'Qty Limited Tech Users',
  feature_plan_preference: 'Indicative feature plan',
  deal_notes: 'Deal notes',
  commission_type: 'Commission type',
  prospect_contact_name: 'Partner contact name',
  prospect_contact_position: 'Partner contact title',
  prospect_phone: 'Partner contact phone',
  prospect_website: 'Partner website',
  compiled_by: 'Compiled by',
  about_client: 'About the Client',
  pain: 'Pain', impact: 'Impact', critical_event: 'Critical Event',
  decision: 'Decision', next_steps: 'Next Steps',
  current_system: 'Current System', old_system: 'Old System',
  inventory_stores: 'Inventory / Stores',
  work_orders_prs: 'Work Orders & PRs',
  monitoring_system: 'Monitoring',
  integration_with: 'Integrate with',
  languages_required: 'Languages required',
}

function formatChangeValue(v) {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'boolean') return v ? '✅' : '❌'
  return String(v)
}

function ChangeLogSection({ dealId, reloadKey }) {
  const API_BASE = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
    || 'https://fracttal-prm-backend-production.up.railway.app'
  const token = localStorage.getItem('token')
  const [open, setOpen] = useState(false)
  const [rows, setRows] = useState(null) // null = not yet fetched
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!open || !dealId || !token) return
    setLoading(true); setError(null)
    fetch(`${API_BASE}/internal/deals/${dealId}/change-log`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        if (!r.ok) {
          const body = await r.json().catch(() => ({}))
          throw new Error(body.detail || `HTTP ${r.status}`)
        }
        return r.json()
      })
      .then((data) => setRows(Array.isArray(data) ? data : []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [open, dealId, token, reloadKey])

  return (
    <section className="fp-card" style={{ marginTop: 24 }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, width: '100%', textAlign: 'left' }}
      >
        <h2 className="fp-section-title" style={{ margin: 0 }}>
          {open ? '▼' : '▶'} Change Log
        </h2>
      </button>
      {open && (
        <div style={{ marginTop: 12 }}>
          {loading && <div style={{ color: '#64748B' }}>Loading change log…</div>}
          {error && <div className="fp-alert fp-alert--danger">{error}</div>}
          {rows && rows.length === 0 && !loading && !error && (
            <div style={{ color: '#94A3B8', padding: 16, textAlign: 'center' }}>
              No internal edits recorded for this deal.
            </div>
          )}
          {rows && rows.length > 0 && (
            <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#F5F7FA' }}>
                  <th style={{ textAlign: 'left', padding: 8 }}>Timestamp</th>
                  <th style={{ textAlign: 'left', padding: 8 }}>Changed by</th>
                  <th style={{ textAlign: 'left', padding: 8 }}>Field</th>
                  <th style={{ textAlign: 'left', padding: 8 }}>Old value → New value</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} style={{ borderBottom: '1px solid #F1F5F9', verticalAlign: 'top' }}>
                    <td style={{ padding: 8, whiteSpace: 'nowrap' }}>
                      {row.timestamp ? new Date(row.timestamp).toLocaleString() : '—'}
                    </td>
                    <td style={{ padding: 8 }}>
                      {row.actor_email || row.actor_role || '—'}
                    </td>
                    <td style={{ padding: 8 }}>
                      {CHANGE_LOG_FIELD_LABELS[row.field_name] || row.field_name || '—'}
                    </td>
                    <td style={{ padding: 8 }}>
                      <span style={{ color: '#94A3B8' }}>{formatChangeValue(row.old_value)}</span>
                      <span style={{ margin: '0 6px', color: '#64748B' }}>→</span>
                      <strong>{formatChangeValue(row.new_value)}</strong>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </section>
  )
}

