import { useEffect, useState } from 'react'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

// Canonical fallback list (Sprint 24 / FPRM-418 / AD-40). Only used when
// GET /config/document-types is unreachable or returns empty -- the vocabulary
// endpoint is the single source of truth and this list must never be relied on
// as a substitute. It mirrors the seeded canonical types (migration 039) so a
// transient fetch failure still shows a usable dropdown.
export const DOCUMENT_TYPE_FALLBACK = [
  { code: 'id_legal_representative', label: 'ID of legal representative' },
  { code: 'power_of_attorney', label: 'Power of attorney' },
  { code: 'articles_of_incorporation', label: 'Articles of incorporation' },
  { code: 'beneficial_owners_list', label: 'Beneficial owners list' },
  { code: 'fiscal_id', label: 'Fiscal ID' },
  { code: 'proof_of_fiscal_domicile', label: 'Proof of fiscal domicile' },
  { code: 'bank_certificate', label: 'Bank certificate' },
  { code: 'nda', label: 'NDA' },
  { code: 'insurance', label: 'Insurance certificate' },
  { code: 'contract', label: 'Contract' },
  { code: 'quote_acceptance', label: 'Quote Acceptance' },
  { code: 'other', label: 'Other' },
]

// Shared fetch so non-<select> callers (validation, the vocabulary admin list)
// read the exact same source as the dropdown (AD-40). Returns
// [{ code, label, is_active }]. Throws on a non-2xx response.
export async function fetchDocumentTypes(token, { includeInactive = false } = {}) {
  const qs = includeInactive ? '?include_inactive=true' : ''
  const r = await fetch(`${API}/config/document-types${qs}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  const data = await r.json()
  return (data?.items || []).map((t) => ({
    code: t.code,
    label: t.label || t.code,
    is_active: t.is_active,
  }))
}

/**
 * Single shared document-type dropdown (Sprint 24 / FPRM-418 / AD-40).
 *
 * Sourced from the GET /config/document-types vocabulary endpoint. EVERY upload
 * surface (partner Documents page, quote-attach, Program Config Document Rules)
 * renders this component so the list can never diverge between surfaces. No
 * caller filters or overrides the vocabulary -- pass `disabledValues` only to
 * grey out (not hide) options that are contextually unavailable (e.g. a doc
 * type that already has a rule), which keeps the list identical everywhere.
 */
export default function DocumentTypeSelect({
  value,
  onChange,
  token,
  id,
  disabled = false,
  style,
  className,
  disabledValues = [],
  disabledSuffix = '',
  placeholder,
  reloadKey,
  'aria-label': ariaLabel,
}) {
  const [options, setOptions] = useState(DOCUMENT_TYPE_FALLBACK)

  useEffect(() => {
    let alive = true
    fetchDocumentTypes(token)
      .then((items) => { if (alive && items.length) setOptions(items) })
      .catch(() => { /* keep the canonical fallback on failure */ })
    return () => { alive = false }
  }, [token, reloadKey])

  const disabledSet = new Set(disabledValues.map((v) => String(v).trim().toLowerCase()))

  return (
    <select
      id={id}
      aria-label={ariaLabel}
      className={className}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange?.(e.target.value)}
      style={style}
    >
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options.map((t) => {
        const isDisabled = disabledSet.has(String(t.code).trim().toLowerCase())
        return (
          <option key={t.code} value={t.code} disabled={isDisabled}>
            {t.label}{isDisabled ? disabledSuffix : ''}
          </option>
        )
      })}
    </select>
  )
}
