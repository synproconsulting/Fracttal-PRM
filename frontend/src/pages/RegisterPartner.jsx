import { useState, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const TOTAL_STEPS = 10

const STEP_TITLES = {
  1: 'A. Company Information',
  2: 'B. Primary Contact',
  3: 'C. Business Information',
  4: 'D. Reseller Experience',
  5: 'E. Technical Capabilities',
  6: 'F. Partnership Goals',
  7: 'G. References',
  8: 'H. Additional Information',
  9: 'Documents',
  10: 'Review & Submit',
}

const labelStyle = { display: 'block', marginTop: 12, fontWeight: 500, fontSize: 14 }
const inputStyle = { display: 'block', width: '100%', padding: 8, fontSize: 14, marginTop: 4, boxSizing: 'border-box' }
const errorStyle = { color: '#c0392b', fontSize: 12 }

function Field({ label, name, value, onChange, errors, type = 'text', required = false, ...rest }) {
  return (
    <div>
      <label style={labelStyle}>
        {label} {required && <span style={{ color: '#c0392b' }}>*</span>}
        <input
          type={type}
          name={name}
          value={value || ''}
          onChange={(e) => onChange(name, e.target.value)}
          style={inputStyle}
          {...rest}
        />
      </label>
      {errors[name] && <div style={errorStyle}>{errors[name]}</div>}
    </div>
  )
}

function validateStep(step, data) {
  const errors = {}
  if (step === 1) {
    if (!data.legal_name) errors.legal_name = 'Company name is required'
    if (!data.applicant_email) errors.applicant_email = 'Email is required'
  }
  if (step === 2) {
    if (!data.applicant_name) errors.applicant_name = 'Contact name is required'
    if (!data.applicant_email) errors.applicant_email = 'Email is required'
  }
  return errors
}

function setHqAddressField(prev, key, value) {
  return { ...prev, hq_address: { ...(prev.hq_address || {}), [key]: value } }
}

export default function RegisterPartner() {
  const [step, setStep] = useState(1)
  const [draftId, setDraftId] = useState(null)
  const [draftToken, setDraftToken] = useState(null)
  const [formData, setFormData] = useState({})
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState(null)
  const [searchParams] = useSearchParams()
  const saveTimer = useRef(null)
  const loadedRef = useRef(false)

  // Resume draft from URL token
  useEffect(() => {
    const token = searchParams.get('draft_token')
    const id = searchParams.get('draft_id')
    if (token && id && !loadedRef.current) {
      loadedRef.current = true
      setDraftToken(token)
      setDraftId(id)
      fetch(`${API}/applications/${id}?draft_token=${token}`)
        .then((r) => (r.ok ? r.json() : Promise.reject(r)))
        .then((data) => setFormData(data))
        .catch(() => {
          // Token invalid or expired - start fresh
          setDraftId(null)
          setDraftToken(null)
        })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Auto-save with debounce
  useEffect(() => {
    if (!draftId || !draftToken) return
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(async () => {
      setSaving(true)
      try {
        const writable = { ...formData }
        delete writable.id
        delete writable.draft_token
        delete writable.status
        delete writable.created_at
        delete writable.updated_at
        delete writable.submitted_at
        await fetch(`${API}/applications/${draftId}?draft_token=${draftToken}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(writable),
        })
        setSavedAt(new Date())
      } finally {
        setSaving(false)
      }
    }, 2000)
    return () => saveTimer.current && clearTimeout(saveTimer.current)
  }, [formData, draftId, draftToken])

  const handleField = (name, value) => {
    setFormData((prev) => ({ ...prev, [name]: value }))
  }

  const handleAddressField = (key, value) => {
    setFormData((prev) => setHqAddressField(prev, key, value))
  }

  const createDraft = async () => {
    const r = await fetch(`${API}/applications`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ applicant_email: formData.applicant_email || '' }),
    })
    if (!r.ok) {
      const err = await r.json().catch(() => ({}))
      throw new Error(err.detail || 'Failed to create draft')
    }
    const data = await r.json()
    setDraftId(data.id)
    setDraftToken(data.draft_token)
    try {
      localStorage.setItem(
        `fprm_draft_${data.id}`,
        JSON.stringify({ id: data.id, token: data.draft_token })
      )
    } catch (_) { /* localStorage may be unavailable */ }
    return data
  }

  const nextStep = async () => {
    const stepErrors = validateStep(step, formData)
    if (Object.keys(stepErrors).length > 0) {
      setErrors(stepErrors)
      return
    }
    setErrors({})
    if (step === 1 && !draftId) {
      try {
        await createDraft()
      } catch (e) {
        setErrors({ _global: e.message })
        return
      }
    }
    setStep((s) => Math.min(TOTAL_STEPS, s + 1))
  }

  const prevStep = () => setStep((s) => Math.max(1, s - 1))

  const draftUrl = draftId
    ? `${window.location.origin}/register?draft_id=${draftId}&draft_token=${draftToken}`
    : null

  const hq = formData.hq_address || {}

  return (
    <div style={{ maxWidth: 720, margin: '40px auto', padding: '0 20px', fontFamily: 'system-ui, sans-serif' }}>
      <h1 style={{ marginBottom: 4 }}>Fracttal Distribution Partner Application</h1>
      <p style={{ marginTop: 0, color: '#666' }}>
        Step {step} of {TOTAL_STEPS} — {STEP_TITLES[step]}
      </p>
      {saving && <p style={{ color: '#888', fontSize: 12, margin: 0 }}>Saving...</p>}
      {!saving && savedAt && (
        <p style={{ color: '#888', fontSize: 12, margin: 0 }}>
          Saved at {savedAt.toLocaleTimeString()}
        </p>
      )}
      {errors._global && <p style={errorStyle}>{errors._global}</p>}

      {step === 1 && (
        <section>
          <h2>Company Information</h2>
          <Field label="Company Name" name="legal_name" value={formData.legal_name} onChange={handleField} errors={errors} required />
          <Field label="DBA / Trade Name" name="dba_name" value={formData.dba_name} onChange={handleField} errors={errors} />
          <Field
            label="Street Address"
            name="hq_street"
            value={hq.street}
            onChange={(_n, v) => handleAddressField('street', v)}
            errors={errors}
          />
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1 }}>
              <Field
                label="City"
                name="hq_city"
                value={hq.city}
                onChange={(_n, v) => handleAddressField('city', v)}
                errors={errors}
              />
            </div>
            <div style={{ flex: 1 }}>
              <Field
                label="State / Province"
                name="hq_state"
                value={hq.state}
                onChange={(_n, v) => handleAddressField('state', v)}
                errors={errors}
              />
            </div>
          </div>
          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1 }}>
              <Field
                label="Postal Code"
                name="hq_postal"
                value={hq.postal_code}
                onChange={(_n, v) => handleAddressField('postal_code', v)}
                errors={errors}
              />
            </div>
            <div style={{ flex: 1 }}>
              <Field
                label="Country"
                name="hq_country"
                value={hq.country}
                onChange={(_n, v) => handleAddressField('country', v)}
                errors={errors}
              />
            </div>
          </div>
          <Field label="Website" name="website" value={formData.website} onChange={handleField} errors={errors} placeholder="https://" />
          <Field label="Phone" name="phone" value={formData.phone} onChange={handleField} errors={errors} type="tel" />
          <Field label="Email Address" name="applicant_email" value={formData.applicant_email} onChange={handleField} errors={errors} type="email" required />
        </section>
      )}

      {step === 2 && (
        <section>
          <h2>Primary Contact</h2>
          <Field label="Contact Name" name="applicant_name" value={formData.applicant_name} onChange={handleField} errors={errors} required />
          <Field label="Title / Position" name="applicant_title" value={formData.applicant_title} onChange={handleField} errors={errors} />
          <Field label="Phone" name="applicant_phone" value={formData.applicant_phone} onChange={handleField} errors={errors} type="tel" />
          <Field label="Email Address" name="applicant_email" value={formData.applicant_email} onChange={handleField} errors={errors} type="email" required />
        </section>
      )}

      {step >= 3 && (
        <section>
          <h2>{STEP_TITLES[step]}</h2>
          <p style={{ color: '#666' }}>This section will be enabled in an upcoming release. Your draft is saved.</p>
        </section>
      )}

      <div style={{ marginTop: 32, display: 'flex', gap: 12 }}>
        {step > 1 && (
          <button type="button" onClick={prevStep} style={{ padding: '10px 20px' }}>
            Back
          </button>
        )}
        {step < TOTAL_STEPS && (
          <button type="button" onClick={nextStep} style={{ padding: '10px 20px', background: '#007aff', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
            Save & Continue
          </button>
        )}
      </div>

      {draftUrl && (
        <div style={{ marginTop: 24, padding: 16, background: '#f5f5f5', borderRadius: 6 }}>
          <p style={{ margin: 0, fontWeight: 500 }}>Save & Continue Later</p>
          <p style={{ marginTop: 4, fontSize: 13, color: '#555' }}>
            Bookmark this link to resume your application:
          </p>
          <input
            readOnly
            value={draftUrl}
            style={{ width: '100%', padding: 6, fontSize: 12 }}
            onClick={(e) => e.target.select()}
          />
        </div>
      )}
    </div>
  )
}
