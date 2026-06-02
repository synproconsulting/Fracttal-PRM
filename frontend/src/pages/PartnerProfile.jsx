import { useEffect, useMemo, useState } from 'react'
import { useOutletContext, useParams } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const INTERNAL_ROLES = new Set(['channel_manager', 'channel_ops_admin', 'system_admin'])
const STATUS_ADMIN_ROLES = new Set(['system_admin', 'channel_ops_admin'])

const STATUS_TONE = {
  applicant:  { bg: '#FEF3C7', fg: '#92400E' },
  active:     { bg: '#DCFCE7', fg: '#166534' },
  suspended:  { bg: '#FEE2E2', fg: '#991B1B' },
  inactive:   { bg: '#E5E7EB', fg: '#475569' },
  terminated: { bg: '#1B2236', fg: '#fff' },
}
const STATUS_LABEL = {
  applicant: 'Applicant',
  active: 'Active',
  suspended: 'Suspended',
  inactive: 'Inactive',
  terminated: 'Terminated',
}

function StatusBadge({ value }) {
  const tone = STATUS_TONE[value] || { bg: '#E5E7EB', fg: '#475569' }
  return (
    <span style={{
      background: tone.bg, color: tone.fg,
      padding: '2px 10px', borderRadius: 12,
      fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap',
    }}>
      {STATUS_LABEL[value] || value || '—'}
    </span>
  )
}

function decodeJwt(token) {
  try {
    const parts = token.split('.')
    if (parts.length < 2) return null
    const padded = parts[1] + '==='.slice((parts[1].length + 3) % 4)
    const json = atob(padded.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(json)
  } catch (_) {
    return null
  }
}

const PROFILE_TEXT_FIELDS = [
  { key: 'year_established', label: 'Year established', type: 'number' },
  { key: 'employee_count', label: 'Employees', type: 'number' },
  { key: 'annual_revenue', label: 'Annual revenue (USD bracket)', type: 'text' },
  { key: 'other_software_products', label: 'Other software products you sell', type: 'textarea' },
  { key: 'sales_marketing_strategy', label: 'Sales & marketing strategy', type: 'textarea' },
  { key: 'cmms_experience_description', label: 'CMMS experience details', type: 'textarea' },
  { key: 'technical_support_description', label: 'Technical support team details', type: 'textarea' },
  { key: 'implementation_description', label: 'Implementation services details', type: 'textarea' },
  { key: 'partnership_goals', label: 'Partnership goals', type: 'textarea' },
  { key: 'market_growth_plan', label: 'Market growth plan', type: 'textarea' },
  { key: 'additional_info', label: 'Additional info', type: 'textarea' },
]

const PROFILE_BOOL_FIELDS = [
  { key: 'cmms_experience', label: 'CMMS experience' },
  { key: 'technical_support_team', label: 'Has technical support team' },
  { key: 'implementation_services', label: 'Offers implementation services' },
]

function OrgSummary({ org }) {
  if (!org) return null
  const rows = [
    ['Legal name', org.legal_name],
    ['DBA', org.dba_name],
    ['Website', org.website],
    ['Email', org.email],
    ['Phone', org.phone],
    ['Program', org.program_type],
    ['Category', org.partner_category],
    ['Status', org.status],
    ['Contract start', org.contract_start_date],
    ['Contract end', org.contract_end_date],
    ['Territory', Array.isArray(org.territory) && org.territory.length ? org.territory.join(', ') : null],
    ['Industries', Array.isArray(org.industries) && org.industries.length ? org.industries.join(', ') : null],
  ]
  return (
    <section className="fp-card" style={{ marginBottom: 24 }}>
      <h2 className="fp-section-title">Organisation</h2>
      <dl style={{ display: 'grid', gridTemplateColumns: '200px 1fr', rowGap: 10, columnGap: 16, margin: 0, fontSize: 'var(--fp-fs-base)' }}>
        {rows.map(([label, value]) => (
          <div key={label} style={{ display: 'contents' }}>
            <dt style={{ color: 'var(--fp-text-secondary)' }}>{label}</dt>
            <dd style={{ margin: 0, color: value ? 'var(--fp-text)' : 'var(--fp-text-muted)' }}>
              {value || '—'}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

function ProfileView({ profile }) {
  if (!profile) return null
  return (
    <section className="fp-card">
      <h2 className="fp-section-title">Profile details</h2>
      <dl style={{ display: 'grid', gridTemplateColumns: '220px 1fr', rowGap: 10, columnGap: 16, margin: 0, fontSize: 'var(--fp-fs-base)' }}>
        {PROFILE_TEXT_FIELDS.map((f) => (
          <div key={f.key} style={{ display: 'contents' }}>
            <dt style={{ color: 'var(--fp-text-secondary)' }}>{f.label}</dt>
            <dd style={{ margin: 0, whiteSpace: 'pre-wrap', color: profile[f.key] ? 'var(--fp-text)' : 'var(--fp-text-muted)' }}>
              {profile[f.key] || '—'}
            </dd>
          </div>
        ))}
        {PROFILE_BOOL_FIELDS.map((f) => (
          <div key={f.key} style={{ display: 'contents' }}>
            <dt style={{ color: 'var(--fp-text-secondary)' }}>{f.label}</dt>
            <dd style={{ margin: 0, color: profile[f.key] === null || profile[f.key] === undefined ? 'var(--fp-text-muted)' : 'var(--fp-text)' }}>
              {profile[f.key] === null || profile[f.key] === undefined
                ? '—'
                : profile[f.key] ? 'Yes' : 'No'}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  )
}

function ProfileEditForm({ profile, onSave, onCancel, saving }) {
  const [draft, setDraft] = useState(() => ({ ...profile }))

  function setField(key, value) {
    setDraft((d) => ({ ...d, [key]: value }))
  }

  function setBool(key, value) {
    setDraft((d) => ({ ...d, [key]: value === '' ? null : value === 'true' }))
  }

  function handleSubmit(e) {
    e.preventDefault()
    const patch = {}
    for (const f of PROFILE_TEXT_FIELDS) {
      if (f.type === 'number') {
        const v = draft[f.key]
        patch[f.key] = v === '' || v === null || v === undefined ? null : Number(v)
      } else {
        patch[f.key] = draft[f.key] || null
      }
    }
    for (const f of PROFILE_BOOL_FIELDS) {
      patch[f.key] = draft[f.key]
    }
    onSave(patch)
  }

  return (
    <form onSubmit={handleSubmit} className="fp-card">
      <h2 className="fp-section-title">Edit profile</h2>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {PROFILE_TEXT_FIELDS.map((f) => {
          const value = draft[f.key] ?? ''
          const id = `pp-${f.key}`
          const isFilled = value !== '' && value !== null && value !== undefined
          return (
            <div
              key={f.key}
              className={`fp-field${isFilled ? ' fp-field--filled' : ''}`}
              style={{ gridColumn: f.type === 'textarea' ? '1 / -1' : 'auto', marginBottom: 0 }}
            >
              {f.type === 'textarea' ? (
                <textarea
                  id={id}
                  rows={3}
                  placeholder=" "
                  value={value}
                  onChange={(e) => setField(f.key, e.target.value)}
                />
              ) : (
                <input
                  id={id}
                  type={f.type}
                  placeholder=" "
                  value={value}
                  onChange={(e) => setField(f.key, e.target.value)}
                />
              )}
              <label htmlFor={id}>{f.label}</label>
            </div>
          )
        })}
        {PROFILE_BOOL_FIELDS.map((f) => {
          const raw = draft[f.key]
          const value = raw === null || raw === undefined ? '' : String(raw)
          const id = `pp-${f.key}`
          return (
            <div key={f.key} className="fp-field fp-field--filled" style={{ marginBottom: 0 }}>
              <select id={id} value={value} onChange={(e) => setBool(f.key, e.target.value)}>
                <option value="">Unspecified</option>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
              <label htmlFor={id}>{f.label}</label>
            </div>
          )
        })}
      </div>
      <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 20 }}>
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="fp-btn fp-btn--ghost"
        >
          Cancel
        </button>
        <button type="submit" disabled={saving} className="fp-btn fp-btn--primary">
          {saving ? 'Saving…' : 'Save changes'}
        </button>
      </div>
    </form>
  )
}

// Sprint 24 PR B / FPRM-424 / AD-41 -- channel-manager assignment panel.
// Shown only on the internal partner-org detail page. Add/remove controls are
// gated to system_admin + channel_ops_admin (canManage); all internal roles can
// view the list. While NO partner has any assignment, every channel_manager
// sees all partners (the empty-state copy explains this).
function ChannelManagersPanel({ token, partnerOrgId, canManage, partnerView = false }) {
  const [assigned, setAssigned] = useState([])
  const [candidates, setCandidates] = useState([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)
  const [pick, setPick] = useState('')
  const [search, setSearch] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    if (!partnerOrgId || !token) return
    let alive = true
    setLoading(true)
    fetch(`${API}/partners/${partnerOrgId}/channel-managers`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => { if (alive) setAssigned(d.items || []) })
      .catch(() => { if (alive) setAssigned([]) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [partnerOrgId, token, reloadKey])

  useEffect(() => {
    if (!canManage || !token) return
    let alive = true
    fetch(`${API}/internal/channel-managers`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => { if (alive) setCandidates(d.items || []) })
      .catch(() => { if (alive) setCandidates([]) })
    return () => { alive = false }
  }, [canManage, token, reloadKey])

  const assignedIds = new Set(assigned.map((a) => a.user_id))
  const available = candidates
    .filter((c) => !assignedIds.has(c.user_id))
    .filter((c) => {
      const q = search.trim().toLowerCase()
      if (!q) return true
      return (c.full_name || '').toLowerCase().includes(q) || (c.email || '').toLowerCase().includes(q)
    })

  async function add() {
    if (!pick) return
    setBusy(true); setError(null)
    try {
      const r = await fetch(`${API}/partners/${partnerOrgId}/channel-managers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ user_id: pick }),
      })
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        throw new Error(d.detail || `HTTP ${r.status}`)
      }
      setPick(''); setSearch(''); setAdding(false); setReloadKey((k) => k + 1)
    } catch (e) { setError(e.message || String(e)) } finally { setBusy(false) }
  }

  async function remove(userId) {
    if (!window.confirm('Remove this channel manager from the partner?')) return
    setBusy(true); setError(null)
    try {
      const r = await fetch(`${API}/partners/${partnerOrgId}/channel-managers/${userId}`, {
        method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        throw new Error(d.detail || `HTTP ${r.status}`)
      }
      setReloadKey((k) => k + 1)
    } catch (e) { setError(e.message || String(e)) } finally { setBusy(false) }
  }

  return (
    <section className="fp-card" style={{ marginBottom: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <h2 className="fp-section-title" style={{ margin: 0 }}>
          {partnerView ? 'Channel Manager(s)' : 'Channel Managers'}
        </h2>
        {canManage && !adding && (
          <button type="button" className="fp-btn fp-btn--primary fp-btn--sm" onClick={() => { setError(null); setAdding(true) }}>
            + Assign
          </button>
        )}
      </div>

      {error && <div className="fp-alert fp-alert--danger" style={{ marginBottom: 12 }}>{error}</div>}

      {adding && canManage && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 12 }}>
          <input type="search" placeholder="Search channel managers…" value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14, flex: 1, minWidth: 180 }} />
          <select value={pick} onChange={(e) => setPick(e.target.value)} disabled={busy}
            style={{ padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14, minWidth: 220 }}>
            <option value="">Select a channel manager…</option>
            {available.map((c) => (
              <option key={c.user_id} value={c.user_id}>{c.full_name || c.email}</option>
            ))}
          </select>
          <button type="button" className="fp-btn fp-btn--primary fp-btn--sm" onClick={add} disabled={busy || !pick}>
            {busy ? 'Saving…' : 'Add'}
          </button>
          <button type="button" className="fp-btn fp-btn--ghost fp-btn--sm" onClick={() => { setAdding(false); setPick(''); setSearch('') }} disabled={busy}>
            Cancel
          </button>
        </div>
      )}

      {loading ? (
        <div style={{ color: '#64748B' }}>Loading…</div>
      ) : assigned.length === 0 ? (
        <p style={{ color: '#64748B', fontSize: 13, margin: 0 }}>
          {partnerView
            ? 'No channel manager assigned yet.'
            : 'No managers assigned — while no partner has any assignment, all channel managers see all partners.'}
        </p>
      ) : (
        <table className="fp-table">
          <thead><tr><th>Name</th><th>Email</th>{canManage && <th style={{ textAlign: 'right' }}>Actions</th>}</tr></thead>
          <tbody>
            {assigned.map((a) => (
              <tr key={a.id}>
                <td>{a.full_name || '—'}</td>
                <td style={{ color: '#64748B' }}>{a.email || '—'}</td>
                {canManage && (
                  <td style={{ textAlign: 'right' }}>
                    <button type="button" className="fp-btn fp-btn--danger fp-btn--sm" onClick={() => remove(a.user_id)} disabled={busy}>
                      Remove
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}


export default function PartnerProfile() {
  const params = useParams()
  const ctx = useOutletContext() || {}
  const tokenFromCtx = ctx.token
  const token = tokenFromCtx || localStorage.getItem('token')
  const payload = token ? decodeJwt(token) : null
  const internalMode = !!params.id

  const partnerOrgId = internalMode ? params.id : payload?.partner_org_id
  const isInternal = INTERNAL_ROLES.has(payload?.role)
  const isCM = payload?.role === 'channel_manager'

  // AD-42 (FPRM-444): a channel_manager may edit only the partners assigned to
  // them. Mirror the backend authority (GET .../channel-managers -> can_edit) so
  // the Edit button is visible exactly when the save would succeed. Admins and
  // partner_admin do not depend on assignment, so they keep the synchronous
  // check (no load flicker).
  const [cmCanEdit, setCmCanEdit] = useState(false)
  const canEdit = isCM ? cmCanEdit : (isInternal || payload?.role === 'partner_admin')

  const [org, setOrg] = useState(null)
  const [profile, setProfile] = useState(null)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const canManageStatus = internalMode && STATUS_ADMIN_ROLES.has(payload?.role)
  const [statusModal, setStatusModal] = useState(null) // { nextStatus }
  const [statusSaving, setStatusSaving] = useState(false)
  const [statusError, setStatusError] = useState(null)
  const [toast, setToast] = useState(null)

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 3000)
    return () => clearTimeout(t)
  }, [toast])

  async function applyStatusChange() {
    if (!statusModal || !partnerOrgId) return
    setStatusSaving(true); setStatusError(null)
    try {
      const r = await fetch(`${API}/internal/partners/${partnerOrgId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status: statusModal.nextStatus }),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(body.detail || `HTTP ${r.status}`)
      setOrg(body)
      setStatusModal(null)
      setToast('Partner organisation status updated')
    } catch (err) {
      setStatusError(err.message)
    } finally {
      setStatusSaving(false)
    }
  }

  useEffect(() => {
    if (!partnerOrgId || !token) return
    setLoading(true)
    setError(null)
    Promise.all([
      fetch(`${API}/partners/${partnerOrgId}`, { headers: { Authorization: `Bearer ${token}` } })
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`Partner ${r.status}`)))),
      fetch(`${API}/partner-profiles/${partnerOrgId}`, { headers: { Authorization: `Bearer ${token}` } })
        .then(async (r) => {
          if (r.ok) return r.json()
          if (r.status === 404) return null
          throw new Error(`Profile ${r.status}`)
        }),
    ])
      .then(([o, p]) => {
        setOrg(o)
        setProfile(p)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [partnerOrgId, token])

  // AD-42: resolve the channel_manager's edit authority for THIS partner.
  useEffect(() => {
    if (!isCM || !partnerOrgId || !token) return
    let alive = true
    fetch(`${API}/partners/${partnerOrgId}/channel-managers`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : { can_edit: false }))
      .then((d) => { if (alive) setCmCanEdit(!!d.can_edit) })
      .catch(() => { if (alive) setCmCanEdit(false) })
    return () => { alive = false }
  }, [isCM, partnerOrgId, token])

  const completeness = useMemo(() => profile?.profile_completeness_pct ?? 0, [profile])

  async function handleSave(patch) {
    setSaving(true)
    setError(null)
    try {
      const r = await fetch(`${API}/partner-profiles/${partnerOrgId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(patch),
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${r.status}`)
      }
      const updated = await r.json()
      setProfile(updated)
      setEditing(false)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  const content = (
    <>
      <div className="fp-page-header">
        <div>
          <h1 className="fp-page-title">{org?.legal_name || 'Partner profile'}</h1>
          {org?.status && (
            <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>Status:</span>
              <StatusBadge value={org.status} />
            </div>
          )}
          {profile && (
            <div style={{ marginTop: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                <span style={{ fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>
                  Profile {completeness}% complete
                </span>
                <span className={`fp-badge ${completeness >= 80 ? 'fp-badge--success' : 'fp-badge--warning'}`}>
                  {completeness >= 80 ? 'Ready to activate' : 'Add more details'}
                </span>
              </div>
              <div className="fp-progress" style={{ maxWidth: 360 }}>
                <div
                  className={`fp-progress__fill${completeness >= 80 ? ' fp-progress__fill--success' : ''}`}
                  style={{ width: `${completeness}%` }}
                />
              </div>
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
          {canManageStatus && org && (
            <button
              type="button"
              onClick={() => {
                const next = org.status === 'active' ? 'suspended' : 'active'
                setStatusError(null)
                setStatusModal({ nextStatus: next })
              }}
              className="fp-btn fp-btn--ghost"
              disabled={!(org.status === 'active' || org.status === 'suspended')}
              title={!(org.status === 'active' || org.status === 'suspended')
                ? 'Status changes only available from active or suspended'
                : ''}
            >
              {org.status === 'active' ? 'Suspend organisation' : org.status === 'suspended' ? 'Reactivate organisation' : 'Change status'}
            </button>
          )}
          {canEdit && !editing && (
            <button type="button" onClick={() => setEditing(true)} className="fp-btn fp-btn--primary">
              Edit profile
            </button>
          )}
        </div>
      </div>

      {loading && <div className="fp-card" style={{ color: 'var(--fp-text-secondary)' }}>Loading…</div>}
      {error && !loading && (
        <div className="fp-alert fp-alert--danger">{error}</div>
      )}

      {!loading && (
        <>
          <OrgSummary org={org} />
          {internalMode ? (
            <ChannelManagersPanel token={token} partnerOrgId={partnerOrgId} canManage={canManageStatus} />
          ) : (
            <ChannelManagersPanel token={token} partnerOrgId={partnerOrgId} canManage={false} partnerView />
          )}
          {profile ? (
            editing ? (
              <ProfileEditForm
                profile={profile}
                saving={saving}
                onSave={handleSave}
                onCancel={() => setEditing(false)}
              />
            ) : (
              <ProfileView profile={profile} />
            )
          ) : (
            <p style={{ color: 'var(--fp-text-secondary)', fontSize: 'var(--fp-fs-base)' }}>
              No profile record yet. This partner was created without a profile row — contact your Fracttal administrator.
            </p>
          )}
        </>
      )}

      {statusModal && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed', inset: 0, background: 'rgba(15, 23, 42, 0.45)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
          }}
        >
          <div style={{
            background: '#fff', borderRadius: 10, padding: 24,
            maxWidth: 460, width: 'calc(100% - 32px)',
            boxShadow: '0 10px 30px rgba(15,23,42,0.2)',
          }}>
            <h2 style={{ margin: '0 0 8px', fontSize: 18 }}>
              {statusModal.nextStatus === 'suspended' ? 'Suspend partner organisation' : 'Reactivate partner organisation'}
            </h2>
            <p style={{ margin: '0 0 16px', color: '#475569', fontSize: 14 }}>
              {statusModal.nextStatus === 'suspended'
                ? <>Suspend <strong>{org?.legal_name}</strong>? This will mark the organisation as suspended.</>
                : <>Reactivate <strong>{org?.legal_name}</strong>? This will return the organisation to active status.</>}
            </p>
            {statusError && (
              <div className="fp-alert fp-alert--danger" style={{ marginBottom: 12 }}>{statusError}</div>
            )}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                type="button"
                className="fp-btn fp-btn--ghost"
                onClick={() => { setStatusModal(null); setStatusError(null) }}
                disabled={statusSaving}
              >
                Cancel
              </button>
              <button
                type="button"
                className="fp-btn fp-btn--primary"
                onClick={applyStatusChange}
                disabled={statusSaving}
              >
                {statusSaving ? 'Saving…' : statusModal.nextStatus === 'suspended' ? 'Suspend' : 'Reactivate'}
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24, zIndex: 1100,
          background: '#166534', color: '#fff',
          padding: '10px 16px', borderRadius: 8,
          boxShadow: '0 8px 20px rgba(15,23,42,0.2)',
          fontSize: 14, fontWeight: 600,
        }}>
          {toast}
        </div>
      )}
    </>
  )

  if (internalMode) {
    return <div className="fp-page">{content}</div>
  }
  return content
}
