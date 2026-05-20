import { useEffect, useMemo, useState } from 'react'
import { formatCurrency as fmtMoney } from '../utils/currency.js'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const VOLUME_BANDS = [
  { min: 1,   max: 10,   discount: 0  },
  { min: 11,  max: 50,   discount: 30 },
  { min: 51,  max: 100,  discount: 40 },
  { min: 101, max: 300,  discount: 50 },
  { min: 301, max: 500,  discount: 60 },
  { min: 501, max: null, discount: 70 },
]

const CURRENCIES = ['USD', 'EUR', 'GBP', 'AUD', 'CAD', 'ZAR', 'AED', 'SAR', 'EGP']

function applyBands(qty, unitPrice, lineType, description) {
  const lines = []
  let remaining = qty
  for (const band of VOLUME_BANDS) {
    if (remaining <= 0) break
    const capacity = band.max ? band.max - band.min + 1 : remaining
    const bandQty = Math.min(remaining, capacity)
    if (bandQty > 0) {
      const totalBefore = Number((unitPrice * bandQty).toFixed(2))
      const totalAfter = Number((totalBefore * (1 - band.discount / 100)).toFixed(2))
      lines.push({
        lineType, description, quantity: bandQty,
        unitPrice, discountPct: band.discount,
        totalBefore, totalAfter,
      })
    }
    remaining -= bandQty
  }
  return lines
}

function calculatePreview(inputs, plans, allAddons) {
  const { featurePlan, featurePlanDiscountPct, qtyTransactional, qtyLimitedTech, selectedAddonKeys } = inputs
  const plan = plans.find((p) => p.plan_code === featurePlan)
  if (!plan) return null
  const discountPct = parseFloat(featurePlanDiscountPct) || 0
  const planName = featurePlan.charAt(0).toUpperCase() + featurePlan.slice(1)
  const freeLimitedTech = discountPct === 0 ? qtyTransactional : 0
  const qtyLimitedTechToPay = Math.max(0, qtyLimitedTech - freeLimitedTech)
  const lines = []

  const fpBefore = Number(plan.feature_pack_annual)
  const fpAfter = Number((fpBefore * (1 - discountPct / 100)).toFixed(2))
  lines.push({
    lineType: 'feature_pack',
    description: `Fracttal One CMMS — ${planName} Plan (Annual Payment)`,
    quantity: 1, unitPrice: fpBefore, discountPct,
    totalBefore: fpBefore, totalAfter: fpAfter,
  })

  if (qtyTransactional > 0) {
    lines.push(...applyBands(
      qtyTransactional, Number(plan.transactional_user_annual),
      'transactional_user', `Transactional Users — ${planName} Plan (Annual Payment)`,
    ))
  }

  const actualFree = Math.min(freeLimitedTech, qtyLimitedTech)
  if (actualFree > 0) {
    lines.push({
      lineType: 'free_allocation',
      description: `Limited Technician Users — ${planName} Plan (Annual Payment) [Complimentary]`,
      quantity: actualFree, unitPrice: 0, discountPct: 0,
      totalBefore: 0, totalAfter: 0,
    })
  }

  if (qtyLimitedTechToPay > 0) {
    lines.push(...applyBands(
      qtyLimitedTechToPay, Number(plan.limited_tech_user_annual),
      'limited_tech_user', `Limited Technician Users — ${planName} Plan (Annual Payment)`,
    ))
  }

  for (const key of selectedAddonKeys) {
    const addon = allAddons.find((a) => a.addon_key === key)
    if (addon) {
      const annualPrice = Number((Number(addon.monthly_price) * 12).toFixed(2))
      lines.push({
        lineType: 'addon',
        description: addon.display_name,
        quantity: 1, unitPrice: annualPrice, discountPct: 0,
        totalBefore: annualPrice, totalAfter: annualPrice,
      })
    }
  }

  const grandBefore = Number(lines.reduce((s, l) => s + l.totalBefore, 0).toFixed(2))
  const grandAfter = Number(lines.reduce((s, l) => s + l.totalAfter, 0).toFixed(2))
  return { lines, grandBefore, grandAfter }
}

export default function QuoteForm({
  dealId, quoteId,
  dealQtyTransactional = 1, dealQtyLimitedTech = 0,
  initialValues = null,
  onSuccess, onCancel,
}) {
  const token = localStorage.getItem('token')
  const isNewVersion = !!quoteId

  const [plans, setPlans] = useState([])
  const [addons, setAddons] = useState([])
  const [loadingCatalog, setLoadingCatalog] = useState(true)
  const [catalogError, setCatalogError] = useState(null)

  const [quoteName, setQuoteName] = useState(initialValues?.quoteName || '')
  const [featurePlan, setFeaturePlan] = useState(initialValues?.featurePlan || 'professional')
  const [featurePlanDiscountPct, setFeaturePlanDiscountPct] = useState(initialValues?.featurePlanDiscountPct ?? 0)
  const [qtyTransactional, setQtyTransactional] = useState(initialValues?.qtyTransactional ?? dealQtyTransactional)
  const [qtyLimitedTech, setQtyLimitedTech] = useState(initialValues?.qtyLimitedTech ?? dealQtyLimitedTech)
  const [scenarioLabel, setScenarioLabel] = useState(initialValues?.scenarioLabel || '')
  const [currencyCode, setCurrencyCode] = useState(initialValues?.currencyCode || 'USD')
  const [selectedAddonKeys, setSelectedAddonKeys] = useState(initialValues?.selectedAddonKeys || [])

  const [preview, setPreview] = useState(null)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)
  const [existingScenarios, setExistingScenarios] = useState([])

  useEffect(() => {
    if (!isNewVersion || !quoteId || !token) return
    fetch(`${API}/quotes/${quoteId}/scenarios`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (r) => (r.ok ? r.json() : { scenarios: [] }))
      .then((data) => setExistingScenarios((data.scenarios || []).map((s) => s.scenario_label)))
      .catch(() => {})
  }, [isNewVersion, quoteId, token])

  const allScenariosCreated = ['good', 'better', 'best'].every((l) => existingScenarios.includes(l))

  useEffect(() => {
    if (!token) { setCatalogError('Not authenticated'); setLoadingCatalog(false); return }
    Promise.all([
      fetch(`${API}/internal/config/pricing/plans`, { headers: { Authorization: `Bearer ${token}` } }).then((r) => r.json()),
      fetch(`${API}/internal/config/pricing/addons`, { headers: { Authorization: `Bearer ${token}` } }).then((r) => r.json()),
    ])
      .then(([p, a]) => { setPlans(p); setAddons(a) })
      .catch((e) => setCatalogError(e.message || String(e)))
      .finally(() => setLoadingCatalog(false))
  }, [token])

  useEffect(() => {
    if (loadingCatalog || !plans.length) return
    const t = setTimeout(() => {
      const inputs = {
        featurePlan,
        featurePlanDiscountPct,
        qtyTransactional: Number(qtyTransactional) || 0,
        qtyLimitedTech: Number(qtyLimitedTech) || 0,
        selectedAddonKeys,
      }
      setPreview(calculatePreview(inputs, plans, addons))
    }, 500)
    return () => clearTimeout(t)
  }, [featurePlan, featurePlanDiscountPct, qtyTransactional, qtyLimitedTech, selectedAddonKeys, plans, addons, loadingCatalog])

  const availableAddons = useMemo(() => {
    if (!addons.length) return []
    const priced = addons.filter((a) => Number(a.monthly_price) > 0)
    if (featurePlan === 'starter') return priced.filter((a) => a.available_starter)
    if (featurePlan === 'professional') return priced.filter((a) => a.available_professional)
    return []
  }, [addons, featurePlan])

  function toggleAddon(key) {
    setSelectedAddonKeys((cur) => (cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key]))
  }

  async function handleSubmit(e) {
    e?.preventDefault?.()
    if (saving) return
    setSaving(true); setSaveError(null)
    try {
      const payload = {
        feature_plan: featurePlan,
        feature_plan_discount_pct: Number(featurePlanDiscountPct) || 0,
        qty_transactional_users: Number(qtyTransactional) || 0,
        qty_limited_tech_users: Number(qtyLimitedTech) || 0,
        selected_addon_keys: selectedAddonKeys,
        scenario_label: scenarioLabel || null,
      }
      if (!isNewVersion) {
        payload.quote_name = quoteName || null
        payload.currency_code = currencyCode
      }
      const url = isNewVersion
        ? `${API}/quotes/${quoteId}/versions`
        : `${API}/deals/${dealId}/quotes`
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(payload),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) {
        throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
      }
      onSuccess?.(body)
    } catch (err) {
      setSaveError(err.message || String(err))
    } finally {
      setSaving(false)
    }
  }

  const discountActive = Number(featurePlanDiscountPct) > 0
  const isEnterprise = featurePlan === 'enterprise'

  if (loadingCatalog) {
    return <div style={{ padding: 24 }}>Loading pricing catalogue…</div>
  }
  if (catalogError) {
    return <div className="fp-alert fp-alert--danger">Failed to load catalogue: {catalogError}</div>
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1fr)', gap: 24 }}>
      <div>
        {!isNewVersion && (
          <section className="fp-card" style={{ marginBottom: 16 }}>
            <h3 className="fp-section-title">Quote details</h3>
            <div style={{ display: 'grid', gap: 12 }}>
              <label style={{ display: 'block' }}>
                <span style={{ fontSize: 12, color: '#64748B', fontWeight: 600 }}>Quote name (optional)</span>
                <input type="text" value={quoteName} onChange={(e) => setQuoteName(e.target.value)}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #E0E4EA', marginTop: 4 }} />
              </label>
              <label style={{ display: 'block' }}>
                <span style={{ fontSize: 12, color: '#64748B', fontWeight: 600 }}>Currency</span>
                <select value={currencyCode} onChange={(e) => setCurrencyCode(e.target.value)}
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #E0E4EA', marginTop: 4 }}>
                  {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
            </div>
          </section>
        )}

        <section className="fp-card" style={{ marginBottom: 16 }}>
          <h3 className="fp-section-title">Quantities</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
            <div style={{ background: '#F5F7FA', padding: 10, borderRadius: 6 }}>
              <div style={{ fontSize: 11, color: '#64748B', fontWeight: 600 }}>From deal: Transactional</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>{dealQtyTransactional}</div>
            </div>
            <div style={{ background: '#F5F7FA', padding: 10, borderRadius: 6 }}>
              <div style={{ fontSize: 11, color: '#64748B', fontWeight: 600 }}>From deal: Limited Tech</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>{dealQtyLimitedTech}</div>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <label style={{ display: 'block' }}>
              <span style={{ fontSize: 12, color: '#64748B', fontWeight: 600 }}>Quoted Transactional Users</span>
              <input type="number" min={1} value={qtyTransactional}
                onChange={(e) => setQtyTransactional(parseInt(e.target.value, 10) || 0)}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #E0E4EA', marginTop: 4 }} />
            </label>
            <label style={{ display: 'block' }}>
              <span style={{ fontSize: 12, color: '#64748B', fontWeight: 600 }}>Quoted Limited Technician Users</span>
              <input type="number" min={0} value={qtyLimitedTech}
                onChange={(e) => setQtyLimitedTech(parseInt(e.target.value, 10) || 0)}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #E0E4EA', marginTop: 4 }} />
            </label>
          </div>
        </section>

        <section className="fp-card" style={{ marginBottom: 16 }}>
          <h3 className="fp-section-title">Plan &amp; Discount</h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <label style={{ display: 'block' }}>
              <span style={{ fontSize: 12, color: '#64748B', fontWeight: 600 }}>Feature Plan</span>
              <select value={featurePlan} onChange={(e) => setFeaturePlan(e.target.value)}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #E0E4EA', marginTop: 4 }}>
                {plans.map((p) => (
                  <option key={p.plan_code} value={p.plan_code}>
                    {p.plan_code.charAt(0).toUpperCase() + p.plan_code.slice(1)}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ display: 'block' }}>
              <span style={{ fontSize: 12, color: '#64748B', fontWeight: 600 }}>Feature Plan Discount %</span>
              <input type="number" min={0} max={100} step={0.1} value={featurePlanDiscountPct}
                onChange={(e) => setFeaturePlanDiscountPct(parseFloat(e.target.value) || 0)}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #E0E4EA', marginTop: 4 }} />
            </label>
            <label style={{ display: 'block' }}>
              <span style={{ fontSize: 12, color: '#64748B', fontWeight: 600 }}>Scenario label (optional)</span>
              <select value={scenarioLabel} onChange={(e) => setScenarioLabel(e.target.value)}
                style={{ width: '100%', padding: '8px 10px', borderRadius: 6, border: '1px solid #E0E4EA', marginTop: 4 }}>
                <option value="">None</option>
                <option value="good" disabled={isNewVersion && existingScenarios.includes('good')}>Good{isNewVersion && existingScenarios.includes('good') ? ' (already created)' : ''}</option>
                <option value="better" disabled={isNewVersion && existingScenarios.includes('better')}>Better{isNewVersion && existingScenarios.includes('better') ? ' (already created)' : ''}</option>
                <option value="best" disabled={isNewVersion && existingScenarios.includes('best')}>Best{isNewVersion && existingScenarios.includes('best') ? ' (already created)' : ''}</option>
              </select>
              {isNewVersion && allScenariosCreated && (
                <span style={{ display: 'block', marginTop: 4, fontSize: 12, color: '#64748B' }}>
                  All 3 scenarios created — new versions will be unlabelled.
                </span>
              )}
            </label>
          </div>
          {discountActive && (
            <div style={{ marginTop: 12, background: '#FFF7ED', border: '1px solid #FED7AA', color: '#9A3412', padding: 10, borderRadius: 6, fontSize: 13 }}>
              ⚠️ Free Limited Technician User allocation is suppressed when a Feature Plan discount is applied.
            </div>
          )}
        </section>

        <section className="fp-card" style={{ marginBottom: 16 }}>
          <h3 className="fp-section-title">Add-ons</h3>
          {isEnterprise && (
            <div style={{ background: '#EFF6FF', border: '1px solid #BFDBFE', color: '#1E40AF', padding: 10, borderRadius: 6, fontSize: 13 }}>
              Enterprise plan includes all features — no add-ons required.
            </div>
          )}
          {!isEnterprise && availableAddons.length === 0 && (
            <div style={{ color: '#94A3B8', fontSize: 13 }}>No add-ons available for this plan.</div>
          )}
          {!isEnterprise && availableAddons.length > 0 && (
            <div style={{ display: 'grid', gap: 8 }}>
              {availableAddons.map((a) => {
                const monthly = Number(a.monthly_price)
                const annual = monthly * 12
                const checked = selectedAddonKeys.includes(a.addon_key)
                return (
                  <label key={a.addon_key} style={{ display: 'flex', justifyContent: 'space-between', padding: 8, border: '1px solid #E0E4EA', borderRadius: 6, cursor: 'pointer', background: checked ? '#F0F7FF' : '#fff' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <input type="checkbox" checked={checked} onChange={() => toggleAddon(a.addon_key)} />
                      <strong>{a.display_name}</strong>
                    </span>
                    <span style={{ fontSize: 13, color: '#64748B' }}>
                      ${monthly.toFixed(2)}/mo • ${annual.toFixed(2)}/yr
                    </span>
                  </label>
                )
              })}
            </div>
          )}
        </section>

        {saveError && (
          <div className="fp-alert fp-alert--danger" style={{ marginBottom: 12 }}>{saveError}</div>
        )}

        <div style={{ display: 'flex', gap: 12 }}>
          <button type="submit" disabled={saving} className="fp-btn fp-btn--primary">
            {saving ? 'Saving…' : (isNewVersion ? 'Add Version' : 'Save Quote')}
          </button>
          {onCancel && (
            <button type="button" onClick={onCancel} disabled={saving} className="fp-btn fp-btn--ghost">
              Cancel
            </button>
          )}
        </div>
      </div>

      <div>
        <div className="fp-card" style={{ position: 'sticky', top: 16 }}>
          <h3 className="fp-section-title">Live preview</h3>
          {!preview && <div style={{ color: '#94A3B8', fontSize: 13 }}>Select a plan to preview pricing…</div>}
          {preview && (
            <>
              <table style={{ width: '100%', fontSize: 12, borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: '#1A6EBB', color: '#fff' }}>
                    <th style={{ textAlign: 'left', padding: 6 }}>Description</th>
                    <th style={{ textAlign: 'right', padding: 6 }}>Qty</th>
                    <th style={{ textAlign: 'right', padding: 6 }}>Unit</th>
                    <th style={{ textAlign: 'right', padding: 6 }}>Disc</th>
                    <th style={{ textAlign: 'right', padding: 6 }}>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.lines.map((l, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #F1F5F9', background: l.lineType === 'free_allocation' ? '#F0FDF4' : 'transparent', color: l.lineType === 'free_allocation' ? '#15803D' : 'inherit', fontStyle: l.lineType === 'free_allocation' ? 'italic' : 'normal' }}>
                      <td style={{ padding: 6 }}>{l.description}</td>
                      <td style={{ padding: 6, textAlign: 'right' }}>{l.quantity}</td>
                      <td style={{ padding: 6, textAlign: 'right' }}>{l.unitPrice > 0 ? fmtMoney(l.unitPrice, currencyCode) : '—'}</td>
                      <td style={{ padding: 6, textAlign: 'right' }}>{l.discountPct > 0 ? `${l.discountPct}%` : '—'}</td>
                      <td style={{ padding: 6, textAlign: 'right' }}>{fmtMoney(l.totalAfter, currencyCode)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ borderTop: '2px solid #1A6EBB', marginTop: 8, paddingTop: 8, fontSize: 13 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span>Annual Total Before Discount:</span>
                  <span>{fmtMoney(preview.grandBefore, currencyCode)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700, marginTop: 4 }}>
                  <span>Annual Total After Discount:</span>
                  <span>{fmtMoney(preview.grandAfter, currencyCode)}</span>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </form>
  )
}
