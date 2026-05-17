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
  return (
    <section style={{ marginBottom: 32 }}>
      <h2 style={{ color: '#102a43', fontSize: 18, margin: '0 0 12px' }}>Organisation</h2>
      <dl style={{ display: 'grid', gridTemplateColumns: '180px 1fr', rowGap: 6, columnGap: 12, fontSize: 14, margin: 0 }}>
        <dt style={{ color: '#666' }}>Legal name</dt><dd style={{ margin: 0 }}>{org.legal_name || '—'}</dd>
        <dt style={{ color: '#666' }}>DBA</dt><dd style={{ margin: 0 }}>{org.dba_name || '—'}</dd>
        <dt style={{ color: '#666' }}>Website</dt><dd style={{ margin: 0 }}>{org.website || '—'}</dd>
        <dt style={{ color: '#666' }}>Email</dt><dd style={{ margin: 0 }}>{org.email || '—'}</dd>
        <dt style={{ color: '#666' }}>Phone</dt><dd style={{ margin: 0 }}>{org.phone || '—'}</dd>
        <dt style={{ color: '#666' }}>Program</dt><dd style={{ margin: 0 }}>{org.program_type || '—'}</dd>
        <dt style={{ color: '#666' }}>Category</dt><dd style={{ margin: 0 }}>{org.partner_category || '—'}</dd>
        <dt style={{ color: '#666' }}>Status</dt><dd style={{ margin: 0 }}>{org.status || '—'}</dd>
        <dt style={{ color: '#666' }}>Contract start</dt><dd style={{ margin: 0 }}>{org.contract_start_date || '—'}</dd>
        <dt style={{ color: '#666' }}>Contract end</dt><dd style={{ margin: 0 }}>{org.contract_end_date || '—'}</dd>
        <dt style={{ color: '#666' }}>Territory</dt>
        <dd style={{ margin: 0 }}>
          {Array.isArray(org.territory) && org.territory.length ? org.territory.join(', ') : '—'}
        </dd>
        <dt style={{ color: '#666' }}>Industries</dt>
        <dd style={{ margin: 0 }}>
          {Array.isArray(org.industries) && org.industries.length ? org.industries.join(', ') : '—'}
        </dd>
      </dl>
    </section>
  )
}

function ProfileView({ profile }) {
  if (!profile) return null
  return (
    <section>
      <h2 style={{ color: '#102a43', fontSize: 18, margin: '0 0 12px' }}>Profile details</h2>
      <dl style={{ display: 'grid', gridTemplateColumns: '220px 1fr', rowGap: 6, columnGap: 12, fontSize: 14, margin: 0 }}>
        {PROFILE_TEXT_FIELDS.map((f) => (
          <>
            <dt key={`${f.key}-l`} style={{ color: '#666' }}>{f.label}</dt>
            <dd key={`${f.key}-v`} style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
              {profile[f.key] === null || profile[f.key] === undefined || profile[f.key] === ''
                ? <span style={{ color: '#bbb' }}>—</span>
                : profile[f.key]}
            </dd>
          </>
        ))}
        {PROFILE_BOOL_FIELDS.map((f) => (
          <>
            <dt key={`${f.key}-l`} style={{ color: '#666' }}>{f.label}</dt>
            <dd key={`${f.key}-v`} style={{ margin: 0 }}>
              {profile[f.key] === null || profile[f.key] === undefined
                ? <span style={{ color: '#bbb' }}>—</span>
                : profile[f.key] ? 'Yes' : 'No'}
            </dd>
          </>
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
    for (const f of [...PROFILE_TEXT_FIELDS, ...PROFILE_BOOL_FIELDS]) {
      if (f.type === 'number') {
        const v = draft[f.key]
        patch[f.key] = v === '' || v === null || v === undefined ? null : Number(v)
      } else if (PROFILE_BOOL_FIELDS.find((b) => b.key === f.key)) {
        patch[f.key] = draft[f.key]
      } else {
        patch[f.key] = draft[f.key] || null
      }
    }
    onSave(patch)
  }

  return (
    <form onSubmit={handleSubmit}>
      <section style={{ marginBottom: 20 }}>
        <h2 style={{ color: '#102a43', fontSize: 18, margin: '0 0 12px' }}>Edit profile</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {PROFILE_TEXT_FIELDS.map((f) => (
            <label key={f.key} style={{ display: 'block', fontSize: 13, color: '#333', gridColumn: f.type === 'textarea' ? '1 / -1' : 'auto' }}>
              {f.label}
              {f.type === 'textarea' ? (
                <textarea
                  rows={3}
                  value={draft[f.key] ?? ''}
                  onChange={(e) => setField(f.key, e.target.value)}
                  style={{ width: '100%', padding: 8, marginTop: 4, fontSize: 14, border: '1px solid #ccc', borderRadius: 4 }}
                />
              ) : (
                <input
                  type={f.type}
                  value={draft[f.key] ?? ''}
                  onChange={(e) => setField(f.key, e.target.value)}
                  style={{ width: '100%', padding: 8, marginTop: 4, fontSize: 14, border: '1px solid #ccc', borderRadius: 4 }}
                />
              )}
            </label>
          ))}
          {PROFILE_BOOL_FIELDS.map((f) => (
            <label key={f.key} style={{ display: 'block', fontSize: 13, color: '#333' }}>
              {f.label}
              <select
                value={draft[f.key] === null || draft[f.key] === undefined ? '' : String(draft[f.key])}
                onChange={(e) => setBool(f.key, e.target.value)}
                style={{ width: '100%', padding: 8, marginTop: 4, fontSize: 14, border: '1px solid #ccc', borderRadius: 4 }}
              >
                <option value="">Unspecified</option>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </label>
          ))}
        </div>
      </section>
      <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          style={{ padding: '10px 16px', border: '1px solid #ccc', background: 'white', borderRadius: 4, cursor: saving ? 'not-allowed' : 'pointer' }}
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={saving}
          style={{ padding: '10px 16px', border: 'none', background: saving ? '#90caf9' : '#1976d2', color: 'white', borderRadius: 4, cursor: saving ? 'wait' : 'pointer' }}
        >
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
  const internalMode = !!params.id  // /internal/partners/:id/profile uses :id

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

  if (loading) return <div style={{ padding: 24 }}>Loading…</div>
  if (error && !profile && !org) return <div style={{ padding: 24, color: '#c0392b' }}>Could not load profile: {error}</div>

  return (
    <div style={{ maxWidth: 980, ...(internalMode ? { margin: '24px auto', padding: '0 24px', fontFamily: 'system-ui, sans-serif' } : {}) }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <h1 style={{ color: '#102a43', margin: 0 }}>
          {org?.legal_name || 'Partner profile'}
        </h1>
        {canEdit && !editing && (
          <button
            onClick={() => setEditing(true)}
            style={{ padding: '8px 16px', background: '#1976d2', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 14 }}
          >
            Edit profile
          </button>
        )}
      </div>

      {profile && (
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6, fontSize: 13, color: '#555' }}>
            <span>Profile {completeness}% complete</span>
            <span style={{ fontSize: 12, color: completeness >= 80 ? '#4caf50' : '#ff9800' }}>
              {completeness >= 80 ? 'Ready to activate' : 'Add more details to reach 80%'}
            </span>
          </div>
          <div style={{ height: 8, background: '#eee', borderRadius: 4, overflow: 'hidden' }}>
            <div
              style={{
                height: '100%',
                width: `${completeness}%`,
                background: completeness >= 80 ? '#4caf50' : '#1976d2',
                transition: 'width 0.3s ease',
              }}
            />
          </div>
        </div>
      )}

      {error && (
        <div style={{ background: '#fdecea', color: '#b71c1c', padding: 12, borderRadius: 4, marginBottom: 16, fontSize: 13 }}>
          {error}
        </div>
      )}

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
        <p style={{ color: '#777', fontSize: 14 }}>
          No profile record yet. This partner was created without a profile row — contact your Fracttal administrator.
        </p>
      )}
    </div>
  )
}
