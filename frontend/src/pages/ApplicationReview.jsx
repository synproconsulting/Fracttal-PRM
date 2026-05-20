import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const STATUS_COLORS = {
  draft: '#9e9e9e',
  submitted: '#2196f3',
  under_review: '#ffc107',
  info_required: '#ff9800',
  approved: '#4caf50',
  rejected: '#f44336',
}

const STATUS_LABELS = {
  draft: 'Draft',
  submitted: 'Submitted',
  under_review: 'Under Review',
  info_required: 'Info Required',
  approved: 'Approved',
  rejected: 'Rejected',
}

function StatusBadge({ status }) {
  return (
    <span style={{
      background: STATUS_COLORS[status] || '#9e9e9e',
      color: 'white',
      padding: '4px 12px',
      borderRadius: 12,
      fontSize: 13,
      fontWeight: 500,
    }}>
      {STATUS_LABELS[status] || status}
    </span>
  )
}

function Field({ label, value }) {
  let display = value
  if (value === null || value === undefined || value === '') display = '—'
  else if (Array.isArray(value)) display = value.length ? value.join(', ') : '—'
  else if (typeof value === 'object') display = JSON.stringify(value)
  else if (typeof value === 'boolean') display = value ? 'Yes' : 'No'
  return (
    <div style={{ display: 'flex', padding: '4px 0', borderBottom: '1px dotted #eee' }}>
      <div style={{ width: 220, color: '#555', fontSize: 13 }}>{label}</div>
      <div style={{ flex: 1, fontSize: 14 }}>{display}</div>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div style={{ marginBottom: 24, border: '1px solid #ddd', borderRadius: 6, padding: 16 }}>
      <h3 style={{ margin: '0 0 12px 0', fontSize: 16, color: '#333' }}>{title}</h3>
      {children}
    </div>
  )
}

function ConfirmModal({ title, body, confirmLabel, onConfirm, onCancel, submitting, danger }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10,
    }}>
      <div style={{ background: 'white', padding: 24, borderRadius: 8, minWidth: 420, maxWidth: 600 }}>
        <h3 style={{ marginTop: 0 }}>{title}</h3>
        <p style={{ color: '#555', fontSize: 14 }}>{body}</p>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
          <button onClick={onCancel} disabled={submitting}>Cancel</button>
          <button
            onClick={onConfirm}
            disabled={submitting}
            style={{ background: danger ? '#f44336' : '#1976d2', color: 'white', border: 'none', padding: '6px 16px', borderRadius: 4 }}
          >
            {submitting ? 'Submitting…' : (confirmLabel || 'Confirm')}
          </button>
        </div>
      </div>
    </div>
  )
}

function ActionModal({ title, label, placeholder, onSubmit, onCancel, submitting }) {
  const [value, setValue] = useState('')
  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10,
    }}>
      <div style={{ background: 'white', padding: 24, borderRadius: 8, minWidth: 420, maxWidth: 600 }}>
        <h3 style={{ marginTop: 0 }}>{title}</h3>
        <p style={{ color: '#555', fontSize: 13 }}>{label}</p>
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder}
          style={{ width: '100%', minHeight: 120, padding: 8, fontSize: 14, fontFamily: 'inherit' }}
        />
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
          <button onClick={onCancel} disabled={submitting}>Cancel</button>
          <button
            onClick={() => value.trim() && onSubmit(value.trim())}
            disabled={!value.trim() || submitting}
            style={{ background: '#1976d2', color: 'white', border: 'none', padding: '6px 16px', borderRadius: 4 }}
          >
            {submitting ? 'Submitting…' : 'Submit'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function ApplicationReview() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [application, setApplication] = useState(null)
  const [timeline, setTimeline] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reviewerNotes, setReviewerNotes] = useState('')
  const [modal, setModal] = useState(null)  // null | 'reject' | 'request-info'
  const [submitting, setSubmitting] = useState(false)
  // FPRM-274 / Sprint 17 — role of the logged-in reviewer, used to gate the
  // Approve button when multi-step workflow has a role-specific step.
  const [currentUserRole, setCurrentUserRole] = useState(null)
  const token = localStorage.getItem('token')

  const authHeaders = useCallback(() => (
    token ? { Authorization: `Bearer ${token}` } : {}
  ), [token])

  useEffect(() => {
    if (!token) return
    fetch(`${API}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then((me) => { if (me?.role) setCurrentUserRole(me.role) })
      .catch(() => {})
  }, [token])

  const load = useCallback(() => {
    setLoading(true)
    setError(null)
    Promise.all([
      fetch(`${API}/applications/${id}`, { headers: authHeaders() }).then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      }),
      fetch(`${API}/applications/${id}/timeline`, { headers: authHeaders() }).then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      }),
    ])
      .then(([app, t]) => {
        setApplication(app)
        setTimeline(Array.isArray(t) ? t : [])
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id, authHeaders])

  useEffect(() => { load() }, [load])

  const callAction = async (path, body) => {
    setSubmitting(true)
    try {
      const r = await fetch(`${API}/applications/${id}/${path}`, {
        method: 'POST',
        headers: { ...authHeaders(), 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
      })
      if (!r.ok) {
        const text = await r.text()
        throw new Error(`HTTP ${r.status}: ${text}`)
      }
      setModal(null)
      load()
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <div style={{ padding: 24 }}>Loading…</div>
  if (error && !application) return <div style={{ padding: 24, color: '#c0392b' }}>Error: {error}</div>
  if (!application) return null

  const a = application
  const isFinal = a.status === 'approved' || a.status === 'rejected'

  return (
    <div style={{
      padding: '24px 32px',
      fontFamily: 'system-ui, sans-serif',
      maxWidth: 1280,
      margin: '0 auto',
      display: 'grid',
      gridTemplateColumns: '1fr 320px',
      gap: 24,
    }}>
      <div>
        <Link to="/internal/applications" style={{ fontSize: 13 }}>← Back to queue</Link>
        <h1 style={{ margin: '8px 0', display: 'flex', alignItems: 'center', gap: 12 }}>
          {a.legal_name || a.applicant_name || 'Untitled application'}
          <StatusBadge status={a.status} />
        </h1>

        <Section title="A. Applicant">
          <Field label="Applicant name" value={a.applicant_name} />
          <Field label="Email" value={a.applicant_email} />
          <Field label="Phone" value={a.applicant_phone} />
          <Field label="Title" value={a.applicant_title} />
        </Section>

        <Section title="B. Company">
          <Field label="Legal name" value={a.legal_name} />
          <Field label="DBA name" value={a.dba_name} />
          <Field label="Website" value={a.website} />
          <Field label="Phone" value={a.phone} />
          <Field label="HQ address" value={a.hq_address} />
        </Section>

        <Section title="C. Business">
          <Field label="Requested categories" value={a.requested_categories} />
          <Field label="Territory" value={a.territory} />
          <Field label="Industries" value={a.industries} />
          <Field label="Year established" value={a.year_established} />
          <Field label="Employees" value={a.employee_count} />
          <Field label="Annual revenue" value={a.annual_revenue} />
          <Field label="Shareholders" value={a.shareholders} />
        </Section>

        <Section title="D. Experience">
          <Field label="Other software products" value={a.other_software_products} />
          <Field label="CMMS experience" value={a.cmms_experience} />
          <Field label="CMMS experience description" value={a.cmms_experience_description} />
          <Field label="Sales & marketing strategy" value={a.sales_marketing_strategy} />
        </Section>

        <Section title="E. Technical capabilities">
          <Field label="Technical support team" value={a.technical_support_team} />
          <Field label="Technical support description" value={a.technical_support_description} />
          <Field label="Implementation services" value={a.implementation_services} />
          <Field label="Implementation description" value={a.implementation_description} />
        </Section>

        <Section title="F. Partnership goals">
          <Field label="Partnership goals" value={a.partnership_goals} />
          <Field label="Market growth plan" value={a.market_growth_plan} />
          <Field label="Additional info" value={a.additional_info} />
        </Section>

        <Section title="G. References">
          <Field label="References" value={a.references} />
        </Section>

        <Section title="H. Review state">
          <Field label="Status" value={a.status} />
          <Field label="Submitted at" value={a.submitted_at} />
          <Field label="Reviewer id" value={a.reviewer_id} />
          <Field label="Reviewed at" value={a.reviewed_at} />
          <Field label="Rejection reason" value={a.rejection_reason} />
          <Field label="Info request message" value={a.info_request_message} />
          <Field label="Provisioned partner_org_id" value={a.partner_org_id} />
        </Section>

        {error && (
          <div style={{ background: '#fdecea', color: '#c0392b', padding: 12, borderRadius: 4 }}>
            {error}
          </div>
        )}
      </div>

      <aside style={{ position: 'sticky', top: 16, alignSelf: 'flex-start' }}>
        {/* FPRM-274 / Sprint 17 — multi-step approval progress */}
        {a.approval_progress && (
          <div style={{
            border: '1px solid #ddd', borderRadius: 6, padding: 16, marginBottom: 16,
            background: '#f7f9fc',
          }}>
            <div style={{ fontSize: 12, color: '#555', textTransform: 'uppercase', fontWeight: 600 }}>
              Approval Workflow
            </div>
            <div style={{ fontSize: 14, marginTop: 6, fontWeight: 600 }}>
              {a.approval_progress.current_step_order
                ? `Step ${a.approval_progress.current_step_order} of ${a.approval_progress.total_steps} — ${a.approval_progress.current_step_name}`
                : `All ${a.approval_progress.total_steps} steps complete`}
            </div>
            {a.approval_progress.current_required_role && (
              <div style={{ fontSize: 12, color: '#555', marginTop: 2 }}>
                Requires role: <code>{a.approval_progress.current_required_role}</code>
              </div>
            )}
            <div style={{ display: 'flex', gap: 4, marginTop: 8 }}>
              {Array.from({ length: a.approval_progress.total_steps }, (_, i) => {
                const done = i < a.approval_progress.completed_steps
                return (
                  <span key={i} style={{
                    width: 18, height: 6, borderRadius: 3,
                    background: done ? '#4caf50' : '#ddd',
                  }} />
                )
              })}
            </div>
          </div>
        )}
        <div style={{ border: '1px solid #ddd', borderRadius: 6, padding: 16, marginBottom: 16 }}>
          <h3 style={{ margin: '0 0 12px 0' }}>Review actions</h3>
          {(() => {
            const roleMismatch = (
              a.approval_progress &&
              a.approval_progress.current_required_role &&
              currentUserRole &&
              currentUserRole !== a.approval_progress.current_required_role
            )
            const approveDisabled = isFinal || submitting || roleMismatch
            const tooltip = roleMismatch
              ? `This step requires role: ${a.approval_progress.current_required_role}`
              : undefined
            return (
              <button
                onClick={() => callAction('approve')}
                disabled={approveDisabled}
                title={tooltip}
                style={{
                  width: '100%', marginBottom: 8, padding: 10,
                  background: approveDisabled ? '#ccc' : '#4caf50', color: 'white',
                  border: 'none', borderRadius: 4, fontSize: 14,
                  cursor: approveDisabled ? 'not-allowed' : 'pointer',
                }}
              >
                {roleMismatch ? `Approve (requires ${a.approval_progress.current_required_role})` : 'Approve'}
              </button>
            )
          })()}
          <button
            onClick={() => setModal('reject')}
            disabled={isFinal || submitting}
            style={{
              width: '100%', marginBottom: 8, padding: 10,
              background: isFinal ? '#ccc' : '#f44336', color: 'white',
              border: 'none', borderRadius: 4, fontSize: 14, cursor: isFinal ? 'default' : 'pointer',
            }}
          >
            Reject
          </button>
          <button
            onClick={() => setModal('request-info')}
            disabled={isFinal || submitting}
            style={{
              width: '100%', padding: 10,
              background: isFinal ? '#ccc' : '#ff9800', color: 'white',
              border: 'none', borderRadius: 4, fontSize: 14, cursor: isFinal ? 'default' : 'pointer',
            }}
          >
            Request Info
          </button>
          {a.status === 'info_required' && (
            <button
              onClick={() => setModal('cancel-info-request')}
              disabled={submitting}
              style={{
                width: '100%', marginTop: 8, padding: 10,
                background: '#6c757d', color: 'white',
                border: 'none', borderRadius: 4, fontSize: 14, cursor: 'pointer',
              }}
            >
              Cancel Info Request
            </button>
          )}
        </div>

        <div style={{ border: '1px solid #ddd', borderRadius: 6, padding: 16, marginBottom: 16 }}>
          <h3 style={{ margin: '0 0 8px 0', fontSize: 14 }}>Reviewer notes (internal)</h3>
          <textarea
            value={reviewerNotes}
            onChange={(e) => setReviewerNotes(e.target.value)}
            placeholder="Notes visible to internal reviewers only…"
            style={{ width: '100%', minHeight: 100, fontSize: 13, fontFamily: 'inherit', padding: 6 }}
          />
        </div>

        <div style={{ border: '1px solid #ddd', borderRadius: 6, padding: 16 }}>
          <h3 style={{ margin: '0 0 8px 0', fontSize: 14 }}>Timeline</h3>
          {timeline.length === 0 && <p style={{ color: '#777', fontSize: 13 }}>No events yet.</p>}
          <ul style={{ paddingLeft: 16, margin: 0 }}>
            {timeline.map((t, i) => (
              <li key={i} style={{ marginBottom: 8, fontSize: 12 }}>
                <div style={{ fontWeight: 500 }}>{t.action}</div>
                <div style={{ color: '#777' }}>
                  {t.actor_role} · {t.timestamp ? new Date(t.timestamp).toLocaleString() : ''}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      {modal === 'reject' && (
        <ActionModal
          title="Reject application"
          label="Provide a reason. The applicant will see this."
          placeholder="e.g. Insufficient CMMS experience for our master tier"
          onCancel={() => setModal(null)}
          onSubmit={(reason) => callAction('reject', { rejection_reason: reason })}
          submitting={submitting}
        />
      )}
      {modal === 'request-info' && (
        <ActionModal
          title="Request additional info"
          label="Message the applicant. They can resume their draft to respond."
          placeholder="e.g. Please attach your tax certificate."
          onCancel={() => setModal(null)}
          onSubmit={(message) => callAction('request-info', { message })}
          submitting={submitting}
        />
      )}
      {modal === 'cancel-info-request' && (
        <ConfirmModal
          title="Cancel info request?"
          body="Cancel the info request? The applicant will no longer be prompted to provide additional information. The application returns to Under Review."
          confirmLabel="Cancel Info Request"
          onCancel={() => setModal(null)}
          onConfirm={() => callAction('cancel-info-request')}
          submitting={submitting}
        />
      )}
    </div>
  )
}
