import { useState, useEffect, useRef } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'

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

function Textarea({ label, name, value, onChange, errors, required = false, rows = 4 }) {
  return (
    <div>
      <label style={labelStyle}>
        {label} {required && <span style={{ color: '#c0392b' }}>*</span>}
        <textarea
          name={name}
          value={value || ''}
          onChange={(e) => onChange(name, e.target.value)}
          rows={rows}
          style={{ ...inputStyle, fontFamily: 'inherit', resize: 'vertical' }}
        />
      </label>
      {errors[name] && <div style={errorStyle}>{errors[name]}</div>}
    </div>
  )
}

function Select({ label, name, value, onChange, options, errors, required = false, placeholder = 'Select...' }) {
  return (
    <div>
      <label style={labelStyle}>
        {label} {required && <span style={{ color: '#c0392b' }}>*</span>}
        <select
          name={name}
          value={value || ''}
          onChange={(e) => onChange(name, e.target.value)}
          style={inputStyle}
        >
          <option value="">{placeholder}</option>
          {options.map((opt) => {
            const v = typeof opt === 'string' ? opt : opt.value
            const l = typeof opt === 'string' ? opt : opt.label
            return <option key={v} value={v}>{l}</option>
          })}
        </select>
      </label>
      {errors[name] && <div style={errorStyle}>{errors[name]}</div>}
    </div>
  )
}

function CheckboxGroup({ label, name, values, onChange, options }) {
  const selected = Array.isArray(values) ? values : []
  const toggle = (val) => {
    const next = selected.includes(val)
      ? selected.filter((s) => s !== val)
      : [...selected, val]
    onChange(name, next)
  }
  return (
    <div>
      <div style={labelStyle}>{label}</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginTop: 6 }}>
        {options.map((opt) => {
          const v = typeof opt === 'string' ? opt : opt.value
          const l = typeof opt === 'string' ? opt : opt.label
          return (
            <label key={v} style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 'normal' }}>
              <input
                type="checkbox"
                checked={selected.includes(v)}
                onChange={() => toggle(v)}
              />
              {l}
            </label>
          )
        })}
      </div>
    </div>
  )
}

function YesNoRadio({ label, name, value, onChange }) {
  const set = (v) => onChange(name, v)
  return (
    <div>
      <div style={labelStyle}>{label}</div>
      <div style={{ display: 'flex', gap: 16, marginTop: 6 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 'normal' }}>
          <input type="radio" checked={value === true} onChange={() => set(true)} />
          Yes
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 'normal' }}>
          <input type="radio" checked={value === false} onChange={() => set(false)} />
          No
        </label>
      </div>
    </div>
  )
}

const INDUSTRY_OPTIONS = [
  'Manufacturing',
  'Mining',
  'Energy',
  'Healthcare',
  'Facilities Management',
  'Other',
]

const ANNUAL_REVENUE_OPTIONS = [
  '<$1M',
  '$1M-$5M',
  '$5M-$20M',
  '$20M+',
]

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
  if (step === 10) {
    if (!data.terms_accepted) errors.terms_accepted = 'You must accept the terms to submit'
    if (!data.legal_name) errors.legal_name = 'Company name is required'
    if (!data.applicant_name) errors.applicant_name = 'Contact name is required'
    if (!data.applicant_email) errors.applicant_email = 'Email is required'
  }
  return errors
}

function setReferenceField(prev, idx, key, value) {
  const refs = Array.isArray(prev.references) ? [...prev.references] : []
  while (refs.length < idx + 1) refs.push({})
  refs[idx] = { ...refs[idx], [key]: value }
  return { ...prev, references: refs }
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
  const [categories, setCategories] = useState([])
  const [uploadedDocs, setUploadedDocs] = useState([])
  const [submitting, setSubmitting] = useState(false)
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
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

  // Fetch partner categories for Step 3
  useEffect(() => {
    fetch(`${API}/config/partner-categories`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => {
        const list = Array.isArray(data) ? data : (data.items || [])
        setCategories(list)
      })
      .catch(() => setCategories([]))
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
        // Strip UI-only flags (prefix _) before sending to backend
        for (const k of Object.keys(writable)) {
          if (k.startsWith('_')) delete writable[k]
        }
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

  const handleReferenceField = (idx, key, value) => {
    setFormData((prev) => setReferenceField(prev, idx, key, value))
  }

  const uploadDocument = async (file) => {
    if (!file || !draftId || !draftToken) return
    const allowed = ['application/pdf', 'image/jpeg', 'image/jpg', 'image/png']
    if (file.type && !allowed.includes(file.type)) {
      setErrors((e) => ({ ...e, _doc: 'Only PDF, JPG, or PNG files are allowed' }))
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      setErrors((e) => ({ ...e, _doc: 'File must be 10 MB or less' }))
      return
    }
    setErrors((e) => { const { _doc, ...rest } = e; return rest })
    const r = await fetch(`${API}/applications/${draftId}/documents?draft_token=${draftToken}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        document_type: 'other',
        document_name: file.name,
        file_path: `uploads/${draftId}/${file.name}`,
        file_size_bytes: file.size,
        mime_type: file.type,
      }),
    })
    if (r.ok) {
      const doc = await r.json()
      setUploadedDocs((docs) => [...docs, doc])
    } else {
      const err = await r.json().catch(() => ({}))
      setErrors((e) => ({ ...e, _doc: err.detail || 'Upload failed' }))
    }
  }

  const scrollToFirstError = () => {
    if (typeof window !== 'undefined' && window.scrollTo) {
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  const handleSubmit = async () => {
    const stepErrors = validateStep(10, formData)
    if (Object.keys(stepErrors).length > 0) {
      setErrors(stepErrors)
      scrollToFirstError()
      return
    }
    if (!draftId || !draftToken) {
      setErrors({ _global: 'No draft to submit' })
      scrollToFirstError()
      return
    }
    setSubmitting(true)
    try {
      // Final save before submit (auto-save debounce may not have fired yet)
      const finalData = { ...formData, terms_accepted: true }
      for (const k of Object.keys(finalData)) {
        if (k.startsWith('_')) delete finalData[k]
      }
      delete finalData.id
      delete finalData.draft_token
      delete finalData.status
      delete finalData.created_at
      delete finalData.updated_at
      delete finalData.submitted_at
      await fetch(`${API}/applications/${draftId}?draft_token=${draftToken}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(finalData),
      })
      const r = await fetch(`${API}/applications/${draftId}/submit?draft_token=${draftToken}`, { method: 'POST' })
      if (r.ok) {
        try { localStorage.removeItem(`fprm_draft_${draftId}`) } catch (_) { /* ignore */ }
        navigate(`/register/confirmation?ref=${draftId}`)
        return
      }
      const err = await r.json().catch(() => ({}))
      const apiErrors = err.detail?.errors
      if (Array.isArray(apiErrors)) {
        setErrors({ _global: apiErrors.join('; ') })
      } else {
        setErrors({ _global: err.detail || 'Submission failed' })
      }
      scrollToFirstError()
    } finally {
      setSubmitting(false)
    }
  }

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

      {step === 3 && (
        <section>
          <h2>Business Information</h2>
          <Field label="Year Established" name="year_established" value={formData.year_established} onChange={handleField} errors={errors} type="number" />
          <Textarea label="Shareholders / Ownership" name="shareholders_text" value={typeof formData.shareholders === 'string' ? formData.shareholders : (formData.shareholders ? JSON.stringify(formData.shareholders) : '')} onChange={(_n, v) => handleField('shareholders', v)} errors={errors} rows={3} />
          <Field label="Number of Employees" name="employee_count" value={formData.employee_count} onChange={handleField} errors={errors} type="number" />
          <Select label="Annual Revenue" name="annual_revenue" value={formData.annual_revenue} onChange={handleField} errors={errors} options={ANNUAL_REVENUE_OPTIONS} />
          <CheckboxGroup label="Industry Sector Focus" name="industries" values={formData.industries} onChange={handleField} options={INDUSTRY_OPTIONS} />
          <Field label="Countries / Regions Served (comma separated)" name="territory_text"
            value={Array.isArray(formData.territory) ? formData.territory.join(', ') : (formData.territory || '')}
            onChange={(_n, v) => handleField('territory', v.split(',').map((s) => s.trim()).filter(Boolean))}
            errors={errors} />
          {categories.length > 0 ? (
            <CheckboxGroup
              label="Requested Partner Categories"
              name="requested_categories"
              values={formData.requested_categories}
              onChange={handleField}
              options={categories.map((c) => ({ value: c.code, label: c.display_name || c.code }))}
            />
          ) : (
            <p style={{ color: '#888', fontSize: 13, marginTop: 12 }}>Partner categories will load once the catalog is available.</p>
          )}
        </section>
      )}

      {step === 4 && (
        <section>
          <h2>Reseller Experience</h2>
          <YesNoRadio
            label="Do you currently resell other software?"
            name="_resells_other"
            value={typeof formData.other_software_products === 'string' && formData.other_software_products.length > 0 ? true : (formData._resells_other === false ? false : null)}
            onChange={(name, v) => {
              handleField('_resells_other', v)
              if (v === false) handleField('other_software_products', '')
            }}
          />
          {(formData._resells_other === true || (formData.other_software_products && formData.other_software_products.length > 0)) && (
            <Textarea label="Please list the products" name="other_software_products" value={formData.other_software_products} onChange={handleField} errors={errors} />
          )}
          <YesNoRadio
            label="Do you have CMMS experience?"
            name="cmms_experience"
            value={formData.cmms_experience}
            onChange={(name, v) => {
              handleField('cmms_experience', v)
              if (v === false) handleField('cmms_experience_description', '')
            }}
          />
          {formData.cmms_experience === true && (
            <Textarea label="Please describe your CMMS experience" name="cmms_experience_description" value={formData.cmms_experience_description} onChange={handleField} errors={errors} />
          )}
          <Textarea label="Describe your sales and marketing strategy for CMMS software" name="sales_marketing_strategy" value={formData.sales_marketing_strategy} onChange={handleField} errors={errors} />
        </section>
      )}

      {step === 5 && (
        <section>
          <h2>Technical Capabilities</h2>
          <YesNoRadio
            label="Do you have a technical support team?"
            name="technical_support_team"
            value={formData.technical_support_team}
            onChange={(name, v) => {
              handleField('technical_support_team', v)
              if (v === false) handleField('technical_support_description', '')
            }}
          />
          {formData.technical_support_team === true && (
            <Textarea label="Describe your technical support team's qualifications and experience" name="technical_support_description" value={formData.technical_support_description} onChange={handleField} errors={errors} />
          )}
          <YesNoRadio
            label="Do you offer implementation and training services?"
            name="implementation_services"
            value={formData.implementation_services}
            onChange={(name, v) => {
              handleField('implementation_services', v)
              if (v === false) handleField('implementation_description', '')
            }}
          />
          {formData.implementation_services === true && (
            <Textarea label="Describe your implementation and training services" name="implementation_description" value={formData.implementation_description} onChange={handleField} errors={errors} />
          )}
        </section>
      )}

      {step === 6 && (
        <section>
          <h2>Partnership Goals</h2>
          <Textarea label="Why are you interested in becoming a Fracttal Distribution Partner? What are your goals for this partnership?" name="partnership_goals" value={formData.partnership_goals} onChange={handleField} errors={errors} rows={6} />
          <Textarea label="How do you plan to grow the market?" name="market_growth_plan" value={formData.market_growth_plan} onChange={handleField} errors={errors} rows={5} />
        </section>
      )}

      {step === 7 && (
        <section>
          <h2>References</h2>
          {[0, 1].map((idx) => {
            const r = (formData.references || [])[idx] || {}
            return (
              <div key={idx} style={{ padding: 12, border: '1px solid #eee', borderRadius: 6, marginTop: 12 }}>
                <h3 style={{ marginTop: 0 }}>Reference {idx + 1}</h3>
                <Field label="Name" name={`ref_${idx}_name`} value={r.name} onChange={(_n, v) => handleReferenceField(idx, 'name', v)} errors={errors} />
                <Field label="Company" name={`ref_${idx}_company`} value={r.company} onChange={(_n, v) => handleReferenceField(idx, 'company', v)} errors={errors} />
                <Field label="Phone" name={`ref_${idx}_phone`} value={r.phone} onChange={(_n, v) => handleReferenceField(idx, 'phone', v)} errors={errors} type="tel" />
                <Field label="Email" name={`ref_${idx}_email`} value={r.email} onChange={(_n, v) => handleReferenceField(idx, 'email', v)} errors={errors} type="email" />
              </div>
            )
          })}
        </section>
      )}

      {step === 8 && (
        <section>
          <h2>Additional Information</h2>
          <Textarea label="Anything else you'd like us to know" name="additional_info" value={formData.additional_info} onChange={handleField} errors={errors} rows={6} />
        </section>
      )}

      {step === 9 && (
        <section>
          <h2>Supporting Documents</h2>
          <p style={{ color: '#555', fontSize: 14 }}>
            Upload supporting documentation (PDF, JPG, or PNG; max 10 MB per file).
          </p>
          <input
            type="file"
            accept=".pdf,.jpg,.jpeg,.png"
            onChange={(e) => {
              const file = e.target.files && e.target.files[0]
              if (file) uploadDocument(file)
              e.target.value = ''
            }}
          />
          {errors._doc && <div style={errorStyle}>{errors._doc}</div>}
          {uploadedDocs.length > 0 && (
            <ul style={{ marginTop: 16 }}>
              {uploadedDocs.map((d) => (
                <li key={d.id}>
                  {d.document_name} <span style={{ color: '#999', fontSize: 12 }}>
                    ({Math.round((d.file_size_bytes || 0) / 1024)} KB)
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {step === 10 && (
        <section>
          <h2>Review &amp; Submit</h2>
          <div style={{ background: '#fafafa', padding: 16, borderRadius: 6, fontSize: 14 }}>
            <p><strong>Company:</strong> {formData.legal_name || '—'}</p>
            <p><strong>Contact:</strong> {formData.applicant_name || '—'} ({formData.applicant_email || '—'})</p>
            <p><strong>Year established:</strong> {formData.year_established || '—'}</p>
            <p><strong>Employees:</strong> {formData.employee_count || '—'}</p>
            <p><strong>Annual revenue:</strong> {formData.annual_revenue || '—'}</p>
            <p><strong>Industries:</strong> {(formData.industries || []).join(', ') || '—'}</p>
            <p><strong>Territory:</strong> {Array.isArray(formData.territory) ? formData.territory.join(', ') : (formData.territory || '—')}</p>
            <p><strong>Requested categories:</strong> {(formData.requested_categories || []).join(', ') || '—'}</p>
            <p><strong>Documents uploaded:</strong> {uploadedDocs.length}</p>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 16 }}>
            <input
              type="checkbox"
              checked={!!formData.terms_accepted}
              onChange={(e) => handleField('terms_accepted', e.target.checked)}
            />
            <span>
              I confirm the information above is accurate and accept the Fracttal Distribution
              Partner application terms.
            </span>
          </label>
          {errors.terms_accepted && <div style={errorStyle}>{errors.terms_accepted}</div>}
        </section>
      )}

      <div style={{ marginTop: 32, display: 'flex', gap: 12 }}>
        {step > 1 && (
          <button type="button" onClick={prevStep} disabled={submitting} style={{ padding: '10px 20px' }}>
            Back
          </button>
        )}
        {step < TOTAL_STEPS && (
          <button type="button" onClick={nextStep} style={{ padding: '10px 20px', background: '#007aff', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
            Save & Continue
          </button>
        )}
        {step === TOTAL_STEPS && (
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting}
            style={{ padding: '10px 20px', background: '#28a745', color: 'white', border: 'none', borderRadius: 4, cursor: submitting ? 'not-allowed' : 'pointer' }}
          >
            {submitting ? 'Submitting…' : 'Submit Application'}
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
