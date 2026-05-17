import { useEffect, useMemo, useState } from 'react'
import { useOutletContext, useParams } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const INTERNAL_ROLES = new Set(['channel_manager', 'channel_ops_admin', 'system_admin'])

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

export default function PartnerProfile() {
  const params = useParams()
  const ctx = useOutletContext() || {}
  const tokenFromCtx = ctx.token
  const token = tokenFromCtx || localStorage.getItem('token')
  const payload = token ? decodeJwt(token) : null
  const internalMode = !!params.id

  const partnerOrgId = internalMode ? params.id : payload?.partner_org_id
  const isInternal = INTERNAL_ROLES.has(payload?.role)
  const canEdit = isInternal || payload?.role === 'partner_admin'

  const [org, setOrg] = useState(null)
  const [profile, setProfile] = useState(null)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

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
        {canEdit && !editing && (
          <button type="button" onClick={() => setEditing(true)} className="fp-btn fp-btn--primary">
            Edit profile
          </button>
        )}
      </div>

      {loading && <div className="fp-card" style={{ color: 'var(--fp-text-secondary)' }}>Loading…</div>}
      {error && !loading && (
        <div className="fp-alert fp-alert--danger">{error}</div>
      )}

      {!loading && (
        <>
          <OrgSummary org={org} />
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
    </>
  )

  if (internalMode) {
    return <div className="fp-page">{content}</div>
  }
  return content
}
