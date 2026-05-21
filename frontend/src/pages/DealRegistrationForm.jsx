import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useOutletContext, useParams } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const INDUSTRY_OPTIONS = [
  'Manufacturing', 'Mining', 'Energy & Utilities', 'Healthcare',
  'Hospitality', 'Logistics & Transportation', 'Real Estate',
  'Food & Beverage', 'Education', 'Retail', 'Government', 'Other',
]

const COUNTRY_OPTIONS = [
  'Argentina', 'Brazil', 'Chile', 'Colombia', 'Costa Rica', 'Ecuador',
  'Mexico', 'Panama', 'Paraguay', 'Peru', 'Uruguay', 'United States',
  'Other',
]

const COMMISSION_LABEL_MAP = {
  autonomous_sell: 'Autonomous Sell',
  indirect_sell: 'Indirect Sell',
  direct_sell: 'Direct Sell',
  co_sell_shared: 'Co-Sell (Shared)',
}

function humanizeCommissionType(code) {
  if (COMMISSION_LABEL_MAP[code]) return COMMISSION_LABEL_MAP[code]
  return String(code)
    .split('_')
    .map((p) => (p ? p.charAt(0).toUpperCase() + p.slice(1) : ''))
    .join(' ')
}

const COMMISSION_FALLBACK_OPTIONS = Object.entries(COMMISSION_LABEL_MAP).map(
  ([value, label]) => ({ value, label }),
)

const COMPANY_SIZE_OPTIONS = ['1-10', '11-50', '51-200', '201-500', '500+']

const FEATURE_PLAN_OPTIONS = [
  { value: 'starter',      label: 'Starter' },
  { value: 'professional', label: 'Professional' },
  { value: 'enterprise',   label: 'Enterprise' },
]

// Current Systems combobox preset values (datalist-backed -- the user can
// type a custom value that overrides the preset list).
const CURRENT_SYSTEM_PRESETS = ['None', 'Excel', 'Paper', 'Social Media', 'CMMS']

const SECTION_B_SYSTEM_ROWS = [
  { key: 'current_system',     label: 'Current System' },
  { key: 'old_system',         label: 'Old System' },
  { key: 'inventory_stores',   label: 'Inventory / Stores' },
  { key: 'work_orders_prs',    label: 'Work Orders & PRs' },
  { key: 'monitoring_system',  label: 'Monitoring' },
]

// Section B feature requirement checkboxes. Split into two equal columns
// (column 1 first, then column 2) -- the form lays them out in a two-column
// grid by row, so flattening interleaves the columns visually.
const SECTION_B_FEATURES = [
  { key: 'need_asset_depreciation',     label: 'Asset Depreciation' },
  { key: 'need_wo_wr',                  label: 'Work Orders / WR' },
  { key: 'need_reports',                label: 'Reports' },
  { key: 'need_tool_management',        label: 'Tool Management' },
  { key: 'need_purchasing',             label: 'Purchasing' },
  { key: 'need_asset_management',       label: 'Asset Management' },
  { key: 'need_document_management',    label: 'Document Management' },
  { key: 'need_cost_tracking',          label: 'Cost Tracking' },
  { key: 'need_monitoring',             label: 'Monitoring' },
  { key: 'need_schedule_third_parties', label: 'Schedule Third Parties' },
  { key: 'need_track_labour',           label: 'Track Labour Activities' },
]

const SECTION_B_NARRATIVES = [
  { key: 'about_client',   label: 'About the Client',
    placeholder: 'Describe the client business, primary objectives, and why they are looking for a solution.' },
  { key: 'pain',           label: 'Pain (P)',
    placeholder: 'What is their current pain?' },
  { key: 'impact',         label: 'Impact (I)',
    placeholder: 'What is the business impact of that pain?' },
  { key: 'critical_event', label: 'Critical Event (CE)',
    placeholder: 'Is there a date-driven trigger (e.g. legacy system renewal date)?' },
  { key: 'decision',       label: 'Decision (D)',
    placeholder: 'Who decides and by when?' },
  { key: 'next_steps',     label: 'Next Steps',
    placeholder: 'Proposed timeline and actions.' },
]

function FloatingInput({ id, label, type = 'text', value, onChange, required, min }) {
  const filled = value !== '' && value !== null && value !== undefined
  return (
    <div className={`fp-field${filled ? ' fp-field--filled' : ''}`}>
      <input
        id={id}
        type={type}
        placeholder=" "
        required={required}
        min={min}
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
      />
      <label htmlFor={id}>{label}{required ? ' *' : ''}</label>
    </div>
  )
}

function FloatingSelect({ id, label, value, onChange, options, required }) {
  return (
    <div className="fp-field fp-field--filled">
      <select id={id} value={value ?? ''} onChange={(e) => onChange(e.target.value)} required={required}>
        <option value="">Select.</option>
        {options.map((opt) => (
          typeof opt === 'string'
            ? <option key={opt} value={opt}>{opt}</option>
            : <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
      <label htmlFor={id}>{label}{required ? ' *' : ''}</label>
    </div>
  )
}

// Combobox input -- presents a dropdown of preset values via the native
// <datalist> element while still accepting free-text. The user can type
// anything; the preset list is a convenience, not a constraint.
function FloatingCombobox({ id, label, value, onChange, options }) {
  const filled = value !== '' && value !== null && value !== undefined
  const listId = `${id}-options`
  return (
    <div className={`fp-field${filled ? ' fp-field--filled' : ''}`}>
      <input
        id={id}
        type="text"
        list={listId}
        placeholder=" "
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
      />
      <datalist id={listId}>
        {options.map((opt) => <option key={opt} value={opt} />)}
      </datalist>
      <label htmlFor={id}>{label}</label>
    </div>
  )
}

function FloatingTextarea({ id, label, value, onChange, rows = 4 }) {
  const filled = value !== '' && value !== null && value !== undefined
  return (
    <div className={`fp-field${filled ? ' fp-field--filled' : ''}`}>
      <textarea
        id={id}
        rows={rows}
        placeholder=" "
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
      />
      <label htmlFor={id}>{label}</label>
    </div>
  )
}

const EMPTY_DRAFT = {
  customer_name: '',
  customer_domain: '',
  customer_contact_name: '',
  customer_contact_position: '',
  customer_contact_email: '',
  customer_contact_phone: '',
  customer_industry: '',
  customer_country: '',
  customer_region: '',
  deal_name: '',
  estimated_deal_value: '',
  estimated_close_date: '',
  deal_notes: '',
  commission_type: '',
  // Section A additional prospect/engagement fields
  engagement_date: '',
  prospect_phone: '',
  compiled_by: '',
  prospect_contact_name: '',
  prospect_contact_position: '',
  prospect_website: '',
  industry_sector: '',
  company_size: '',
  feature_plan_preference: '',
  // Section B Current State (Situation)
  current_system: '',
  old_system: '',
  inventory_stores: '',
  work_orders_prs: '',
  monitoring_system: '',
  // Section B Feature requirements (Yes/No + free text)
  need_asset_depreciation: null,
  need_wo_wr: null,
  need_reports: null,
  need_tool_management: null,
  need_purchasing: null,
  need_integration: null,
  integration_with: '',
  need_multi_language: null,
  languages_required: '',
  need_asset_management: null,
  need_document_management: null,
  need_cost_tracking: null,
  need_monitoring: null,
  need_schedule_third_parties: null,
  need_track_labour: null,
  // Section B SPICED narrative fields
  about_client: '',
  pain: '',
  impact: '',
  critical_event: '',
  decision: '',
  next_steps: '',
  // Post-Sprint 20 license qty fields (migration 029)
  qty_transactional_users: '',
  qty_limited_tech_users: '',
}

export default function DealRegistrationForm() {
  const { id } = useParams()
  const navigate = useNavigate()
  const ctx = useOutletContext() || {}
  const token = ctx.token || localStorage.getItem('token')
  const payload = ctx.payload || null
  const partnerOrgId = payload?.partner_org_id

  const [deal, setDeal] = useState(() => ({ ...EMPTY_DRAFT, id: null, status: 'draft' }))
  const [loading, setLoading] = useState(!!id)
  const [saving, setSaving] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [activationBanner, setActivationBanner] = useState(false)
  const [commissionRates, setCommissionRates] = useState(null)
  // Logged-in user's full_name is fetched from /auth/me so we can pre-populate
  // the Partner contact name on a new draft. Editable -- the user can override.
  const [me, setMe] = useState(null)

  useEffect(() => {
    if (!token) return
    fetch(`${API}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d) setMe(d) })
      .catch(() => {})
  }, [token])

  // FPRM-158: fetch the partner's commission rates so we can preview the
  // applicable percentage once the user picks a commission_type. Fetch
  // failures are silent - we never block the form because of this.
  useEffect(() => {
    if (!partnerOrgId || !token) return
    fetch(`${API}/partners/${partnerOrgId}/commission-rates`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (d) setCommissionRates(d) })
      .catch(() => {})
  }, [partnerOrgId, token])

  const rateHint = useMemo(() => {
    if (!deal.commission_type) return ''
    if (!commissionRates?.items) return ''
    const y1 = commissionRates.items.find(
      (it) => it.commission_type === deal.commission_type && it.year === 'year_1',
    )
    if (y1 && y1.percentage != null) {
      return `Applicable rate (Year 1): ${y1.percentage}%`
    }
    return 'Rate not on file for this commission type'
  }, [deal.commission_type, commissionRates])

  // FPRM-173: derive commission_type options from the partner's commission
  // rates so a new vocabulary entry seeded in commission_structures shows up
  // here automatically. Falls back to the canonical four-value list while the
  // fetch is in flight or if it fails.
  const commissionOptions = useMemo(() => {
    const items = commissionRates?.items
    if (!items || items.length === 0) return COMMISSION_FALLBACK_OPTIONS
    const seen = new Set()
    const out = []
    for (const item of items) {
      const code = item.commission_type
      if (!code || seen.has(code)) continue
      seen.add(code)
      out.push({ value: code, label: humanizeCommissionType(code) })
    }
    return out.length > 0 ? out : COMMISSION_FALLBACK_OPTIONS
  }, [commissionRates])

  useEffect(() => {
    if (!id || !token) return
    setLoading(true)
    fetch(`${API}/deal-registrations/${id}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        if (!r.ok) {
          const body = await r.json().catch(() => ({}))
          throw new Error(body.detail || `HTTP ${r.status}`)
        }
        return r.json()
      })
      .then((d) => setDeal({ ...EMPTY_DRAFT, ...d }))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id, token])

  // Pre-populate Partner contact name + email (compiled_by) from the logged-in
  // user on a NEW draft only. Existing drafts keep whatever was persisted.
  // All pre-populated fields stay editable.
  useEffect(() => {
    if (id) return
    setDeal((d) => {
      const next = { ...d }
      if (!next.compiled_by && payload?.email) next.compiled_by = payload.email
      if (!next.prospect_contact_name && me?.full_name) next.prospect_contact_name = me.full_name
      return next
    })
  }, [id, payload, me])

  function setField(key, value) {
    setDeal((d) => ({ ...d, [key]: value }))
  }

  const submitDisabled = useMemo(
    () => !((deal.customer_name || '').trim() && (deal.deal_name || '').trim()) || saving || submitting,
    [deal.customer_name, deal.deal_name, saving, submitting],
  )

  function buildPayload() {
    const payload = {}
    const numericKeys = new Set([
      'estimated_deal_value', 'qty_transactional_users', 'qty_limited_tech_users',
    ])
    for (const key of Object.keys(EMPTY_DRAFT)) {
      const v = deal[key]
      if (v === '' || v === null || v === undefined) {
        payload[key] = null
        continue
      }
      if (numericKeys.has(key)) {
        const num = Number(v)
        payload[key] = Number.isFinite(num) ? num : null
        continue
      }
      payload[key] = v
    }
    return payload
  }

  async function saveDraft() {
    setError(null)
    setActivationBanner(false)
    setSaving(true)
    try {
      const payload = buildPayload()
      const url = deal.id ? `${API}/deal-registrations/${deal.id}` : `${API}/deal-registrations`
      const method = deal.id ? 'PATCH' : 'POST'
      const r = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(payload),
      })
      const body = await r.json().catch(() => ({}))
      if (r.status === 412) {
        setActivationBanner(true)
        return null
      }
      if (!r.ok) {
        const msg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail || body)
        throw new Error(msg || `HTTP ${r.status}`)
      }
      setDeal((d) => ({ ...d, ...body }))
      return body
    } catch (e) {
      setError(e.message)
      return null
    } finally {
      setSaving(false)
    }
  }

  async function submitDeal() {
    setError(null)
    setActivationBanner(false)
    setSubmitting(true)
    try {
      // Always persist current state before submitting
      const saved = await saveDraft()
      if (!saved || !saved.id) return
      const r = await fetch(`${API}/deal-registrations/${saved.id}/submit`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      const body = await r.json().catch(() => ({}))
      if (r.status === 412) {
        setActivationBanner(true)
        return
      }
      if (!r.ok) {
        const msg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail || body)
        throw new Error(msg || `HTTP ${r.status}`)
      }
      sessionStorage.setItem('deal_submitted_toast', `Deal "${body.deal_name}" submitted successfully`)
      navigate('/portal/deals', { replace: true })
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return <div className="fp-card" style={{ color: 'var(--fp-text-secondary)' }}>Loading deal.</div>
  }

  const isExistingSubmittable = !deal.id || deal.status === 'draft' || deal.status === 'info_required'

  // Split the feature checkboxes into two equal columns. CSS grid lays out
  // children row-by-row, so to get column-by-column visual order we
  // interleave the two halves.
  const halfPoint = Math.ceil(SECTION_B_FEATURES.length / 2)
  const featuresLeftCol = SECTION_B_FEATURES.slice(0, halfPoint)
  const featuresRightCol = SECTION_B_FEATURES.slice(halfPoint)
  const featuresInterleaved = []
  for (let i = 0; i < halfPoint; i++) {
    if (featuresLeftCol[i]) featuresInterleaved.push(featuresLeftCol[i])
    if (featuresRightCol[i]) featuresInterleaved.push(featuresRightCol[i])
  }

  return (
    <div>
      <div className="fp-page-header">
        <div>
          <h1 className="fp-page-title">{deal.id ? 'Edit deal' : 'Register a deal'}</h1>
          <p style={{ margin: '6px 0 0', fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>
            Save as a draft, refine, then submit for Fracttal review.
          </p>
        </div>
      </div>

      {activationBanner && (
        <div className="fp-alert fp-alert--warning" style={{ marginBottom: 16 }}>
          <div>
            <strong>Your partner account is not yet fully activated.</strong>{' '}
            <a href="/portal/home" style={{ color: 'inherit', textDecoration: 'underline', fontWeight: 600 }}>
              Complete activation ?
            </a>
          </div>
        </div>
      )}

      {error && !activationBanner && (
        <div className="fp-alert fp-alert--danger">{error}</div>
      )}

      {!isExistingSubmittable && (
        <div className="fp-alert fp-alert--info">
          This deal has been submitted and cannot be edited. View it in the pipeline.
        </div>
      )}

      <section className="fp-card" style={{ marginBottom: 24 }}>
        <h2 className="fp-section-title">Customer information</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <FloatingInput
            id="deal-customer_name"
            label="Company name"
            type="text"
            required
            value={deal.customer_name ?? ''}
            onChange={(v) => setField('customer_name', v)}
          />
          <FloatingInput
            id="deal-customer_domain"
            label="Customer domain (e.g. acme.com)"
            type="text"
            value={deal.customer_domain ?? ''}
            onChange={(v) => setField('customer_domain', v)}
          />
          <FloatingInput
            id="deal-customer_contact_name"
            label="Contact name"
            type="text"
            value={deal.customer_contact_name ?? ''}
            onChange={(v) => setField('customer_contact_name', v)}
          />
          <FloatingInput
            id="deal-customer_contact_position"
            label="Contact title"
            type="text"
            value={deal.customer_contact_position ?? ''}
            onChange={(v) => setField('customer_contact_position', v)}
          />
          <FloatingInput
            id="deal-customer_contact_email"
            label="Contact email"
            type="email"
            value={deal.customer_contact_email ?? ''}
            onChange={(v) => setField('customer_contact_email', v)}
          />
          <FloatingInput
            id="deal-customer_contact_phone"
            label="Contact phone"
            type="tel"
            value={deal.customer_contact_phone ?? ''}
            onChange={(v) => setField('customer_contact_phone', v)}
          />
          <FloatingInput
            id="deal-customer_region"
            label="Region / state"
            type="text"
            value={deal.customer_region ?? ''}
            onChange={(v) => setField('customer_region', v)}
          />
          <FloatingSelect
            id="deal-customer_industry"
            label="Industry"
            value={deal.customer_industry}
            onChange={(v) => setField('customer_industry', v)}
            options={INDUSTRY_OPTIONS}
          />
          <FloatingSelect
            id="deal-customer_country"
            label="Country"
            value={deal.customer_country}
            onChange={(v) => setField('customer_country', v)}
            options={COUNTRY_OPTIONS}
          />
          <FloatingSelect
            id="deal-company_size"
            label="Company size"
            value={deal.company_size}
            onChange={(v) => setField('company_size', v)}
            options={COMPANY_SIZE_OPTIONS}
          />
        </div>
      </section>

      {/* Partner contact information -- the person at the partner org who is
          driving this opportunity. Pre-populated from the logged-in user
          where possible; every field stays editable. */}
      <section className="fp-card" style={{ marginBottom: 24 }}>
        <h2 className="fp-section-title">Partner contact information</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <FloatingInput
            id="deal-prospect_contact_name"
            label="Partner contact name"
            type="text"
            value={deal.prospect_contact_name ?? ''}
            onChange={(v) => setField('prospect_contact_name', v)}
          />
          <FloatingInput
            id="deal-prospect_contact_position"
            label="Partner contact title"
            type="text"
            value={deal.prospect_contact_position ?? ''}
            onChange={(v) => setField('prospect_contact_position', v)}
          />
          <FloatingInput
            id="deal-prospect_phone"
            label="Partner contact phone"
            type="tel"
            value={deal.prospect_phone ?? ''}
            onChange={(v) => setField('prospect_phone', v)}
          />
          <FloatingInput
            id="deal-prospect_website"
            label="Partner website / LinkedIn URL"
            type="url"
            value={deal.prospect_website ?? ''}
            onChange={(v) => setField('prospect_website', v)}
          />
          <FloatingInput
            id="deal-compiled_by"
            label="Compiled by"
            type="text"
            value={deal.compiled_by ?? ''}
            onChange={(v) => setField('compiled_by', v)}
          />
        </div>
      </section>

      <section className="fp-card" style={{ marginBottom: 24 }}>
        <h2 className="fp-section-title">Deal information</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <FloatingInput
            id="deal-deal_name"
            label="Deal name"
            type="text"
            required
            value={deal.deal_name ?? ''}
            onChange={(v) => setField('deal_name', v)}
          />
          <FloatingInput
            id="deal-estimated_deal_value"
            label="Estimated deal value (USD)"
            type="number"
            value={deal.estimated_deal_value ?? ''}
            onChange={(v) => setField('estimated_deal_value', v)}
          />
          <FloatingInput
            id="deal-estimated_close_date"
            label="Estimated close date"
            type="date"
            value={deal.estimated_close_date ?? ''}
            onChange={(v) => setField('estimated_close_date', v)}
          />
          <FloatingInput
            id="deal-engagement_date"
            label="Engagement date"
            type="date"
            value={deal.engagement_date ?? ''}
            onChange={(v) => setField('engagement_date', v)}
          />
          <FloatingInput
            id="deal-qty_transactional_users"
            label="Requested Qty Transactional User Licenses"
            type="number"
            min={0}
            value={deal.qty_transactional_users ?? ''}
            onChange={(v) => setField('qty_transactional_users', v)}
          />
          <FloatingInput
            id="deal-qty_limited_tech_users"
            label="Requested Qty Limited Technician User Licenses"
            type="number"
            min={0}
            value={deal.qty_limited_tech_users ?? ''}
            onChange={(v) => setField('qty_limited_tech_users', v)}
          />
          <FloatingSelect
            id="deal-feature_plan_preference"
            label="Indicative feature plan"
            value={deal.feature_plan_preference}
            onChange={(v) => setField('feature_plan_preference', v)}
            options={FEATURE_PLAN_OPTIONS}
          />
          <div>
            <FloatingSelect
              id="deal-commission_type"
              label="Commission type"
              value={deal.commission_type}
              onChange={(v) => setField('commission_type', v)}
              options={commissionOptions}
            />
            {rateHint && (
              <p
                style={{
                  margin: '6px 4px 0',
                  fontSize: 'var(--fp-fs-sm)',
                  color: 'var(--fp-text-secondary)',
                }}
              >
                {rateHint}
              </p>
            )}
          </div>
          <div style={{ gridColumn: '1 / -1' }}>
            <FloatingTextarea
              id="deal-deal_notes"
              label="Deal notes"
              value={deal.deal_notes}
              onChange={(v) => setField('deal_notes', v)}
              rows={4}
            />
          </div>
        </div>
      </section>

      <section className="fp-card" style={{ marginBottom: 24 }}>
        <h2 className="fp-section-title">Current State and Needs Assessment</h2>
        <p style={{ margin: '0 0 16px', fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>
          Complete this section to help your Channel Manager prepare the best quote. All fields optional.
        </p>

        {/* About the Client */}
        <div style={{ marginBottom: 20 }}>
          <FloatingTextarea
            id="deal-about_client"
            label="About the Client"
            value={deal.about_client}
            onChange={(v) => setField('about_client', v)}
            rows={4}
          />
        </div>

        {/* Section B - Situation: Current Systems -- combobox (preset + free text) */}
        <div style={{ marginBottom: 20 }}>
          <h3 style={{ margin: '0 0 8px', fontSize: 'var(--fp-fs-md)', fontWeight: 600 }}>
            Situation (S) — Current Systems
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            {SECTION_B_SYSTEM_ROWS.map((row) => (
              <FloatingCombobox
                key={row.key}
                id={`deal-${row.key}`}
                label={row.label}
                value={deal[row.key]}
                onChange={(v) => setField(row.key, v)}
                options={CURRENT_SYSTEM_PRESETS}
              />
            ))}
          </div>
        </div>

        {/* Section B - Features Required (split evenly across two columns) */}
        <div style={{ marginBottom: 20 }}>
          <h3 style={{ margin: '0 0 8px', fontSize: 'var(--fp-fs-md)', fontWeight: 600 }}>
            Features Required
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px 16px', marginBottom: 12 }}>
            {featuresInterleaved.map((f) => (
              <label key={f.key} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 'var(--fp-fs-sm)' }}>
                <input
                  type="checkbox"
                  checked={deal[f.key] === true}
                  onChange={(e) => setField(f.key, e.target.checked ? true : null)}
                />
                {f.label}
              </label>
            ))}
          </div>
          {/* Paired free-text follow-ups */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 'var(--fp-fs-sm)', marginBottom: 6 }}>
                <input
                  type="checkbox"
                  checked={deal.need_integration === true}
                  onChange={(e) => setField('need_integration', e.target.checked ? true : null)}
                />
                Require Integration
              </label>
              {deal.need_integration === true && (
                <FloatingInput
                  id="deal-integration_with"
                  label="Integrate with?"
                  type="text"
                  value={deal.integration_with ?? ''}
                  onChange={(v) => setField('integration_with', v)}
                />
              )}
            </div>
            <div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 'var(--fp-fs-sm)', marginBottom: 6 }}>
                <input
                  type="checkbox"
                  checked={deal.need_multi_language === true}
                  onChange={(e) => setField('need_multi_language', e.target.checked ? true : null)}
                />
                Multi-language
              </label>
              {deal.need_multi_language === true && (
                <FloatingInput
                  id="deal-languages_required"
                  label="Which languages?"
                  type="text"
                  value={deal.languages_required ?? ''}
                  onChange={(v) => setField('languages_required', v)}
                />
              )}
            </div>
          </div>
        </div>

        {/* SPICED Narratives */}
        <div>
          <h3 style={{ margin: '0 0 8px', fontSize: 'var(--fp-fs-md)', fontWeight: 600 }}>
            SPICED Narrative
          </h3>
          <div style={{ display: 'grid', gap: 12 }}>
            {SECTION_B_NARRATIVES.slice(1).map((f) => (
              <FloatingTextarea
                key={f.key}
                id={`deal-${f.key}`}
                label={f.label}
                value={deal[f.key]}
                onChange={(v) => setField(f.key, v)}
                rows={3}
              />
            ))}
          </div>
        </div>
      </section>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16 }}>
        <button type="button" className="fp-btn fp-btn--ghost" onClick={() => navigate('/portal/deals')}>
          Cancel
        </button>
        <div style={{ display: 'flex', gap: 12 }}>
          <button
            type="button"
            className="fp-btn fp-btn--secondary"
            onClick={saveDraft}
            disabled={saving || submitting || !isExistingSubmittable}
          >
            {saving ? 'Saving.' : 'Save as draft'}
          </button>
          <button
            type="button"
            className="fp-btn fp-btn--primary"
            onClick={submitDeal}
            disabled={submitDisabled || !isExistingSubmittable}
          >
            {submitting ? 'Submitting.' : 'Submit deal'}
          </button>
        </div>
      </div>
    </div>
  )
}
