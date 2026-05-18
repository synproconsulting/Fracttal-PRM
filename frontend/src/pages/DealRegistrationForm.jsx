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

const COMMISSION_OPTIONS = [
  { value: '', label: 'Select…' },
  { value: 'autonomous_sell', label: 'Autonomous Sell' },
  { value: 'indirect_sell', label: 'Indirect Sell' },
  { value: 'direct_sell', label: 'Direct Sell' },
  { value: 'co_sell_shared', label: 'Co-Sell (Shared)' },
]

const TEXT_FIELDS_CUSTOMER = [
  { key: 'customer_name', label: 'Customer name', required: true, type: 'text' },
  { key: 'customer_domain', label: 'Customer domain (e.g. acme.com)', type: 'text' },
  { key: 'customer_contact_name', label: 'Contact name', type: 'text' },
  { key: 'customer_contact_email', label: 'Contact email', type: 'email' },
  { key: 'customer_contact_phone', label: 'Contact phone', type: 'tel' },
  { key: 'customer_region', label: 'Region / state', type: 'text' },
]

const TEXT_FIELDS_DEAL = [
  { key: 'deal_name', label: 'Deal name', required: true, type: 'text' },
  { key: 'estimated_deal_value', label: 'Estimated deal value (USD)', type: 'number' },
  { key: 'estimated_close_date', label: 'Estimated close date', type: 'date' },
]

function FloatingInput({ id, label, type = 'text', value, onChange, required }) {
  const filled = value !== '' && value !== null && value !== undefined
  return (
    <div className={`fp-field${filled ? ' fp-field--filled' : ''}`}>
      <input
        id={id}
        type={type}
        placeholder=" "
        required={required}
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
        <option value="">Select…</option>
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

  // FPRM-158: fetch the partner's commission rates so we can preview the
  // applicable percentage once the user picks a commission_type. Fetch
  // failures are silent — we never block the form because of this.
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

  function setField(key, value) {
    setDeal((d) => ({ ...d, [key]: value }))
  }

  const submitDisabled = useMemo(
    () => !((deal.customer_name || '').trim() && (deal.deal_name || '').trim()) || saving || submitting,
    [deal.customer_name, deal.deal_name, saving, submitting],
  )

  function buildPayload() {
    const payload = {}
    for (const key of Object.keys(EMPTY_DRAFT)) {
      const v = deal[key]
      if (v === '' || v === null || v === undefined) {
        payload[key] = null
        continue
      }
      if (key === 'estimated_deal_value') {
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
    return <div className="fp-card" style={{ color: 'var(--fp-text-secondary)' }}>Loading deal…</div>
  }

  const isExistingSubmittable = !deal.id || deal.status === 'draft' || deal.status === 'info_required'

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
              Complete activation →
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
          {TEXT_FIELDS_CUSTOMER.map((f) => (
            <FloatingInput
              key={f.key}
              id={`deal-${f.key}`}
              label={f.label}
              type={f.type}
              required={f.required}
              value={deal[f.key] ?? ''}
              onChange={(v) => setField(f.key, v)}
            />
          ))}
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
        </div>
      </section>

      <section className="fp-card" style={{ marginBottom: 24 }}>
        <h2 className="fp-section-title">Deal information</h2>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {TEXT_FIELDS_DEAL.map((f) => (
            <FloatingInput
              key={f.key}
              id={`deal-${f.key}`}
              label={f.label}
              type={f.type}
              required={f.required}
              value={deal[f.key] ?? ''}
              onChange={(v) => setField(f.key, v)}
            />
          ))}
          <div>
            <FloatingSelect
              id="deal-commission_type"
              label="Commission type"
              value={deal.commission_type}
              onChange={(v) => setField('commission_type', v)}
              options={COMMISSION_OPTIONS.slice(1)}
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
            {saving ? 'Saving…' : 'Save as draft'}
          </button>
          <button
            type="button"
            className="fp-btn fp-btn--primary"
            onClick={submitDeal}
            disabled={submitDisabled || !isExistingSubmittable}
          >
            {submitting ? 'Submitting…' : 'Submit deal'}
          </button>
        </div>
      </div>
    </div>
  )
}
