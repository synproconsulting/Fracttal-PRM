import { useCallback, useEffect, useState } from 'react'
import { formatCurrency as fmtMoney, CURRENCY_SYMBOL } from '../utils/currency.js'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const STATUS_TONE = {
  draft: 'fp-badge--neutral',
  sent: 'fp-badge--info',
  accepted: 'fp-badge--success',
  expired: 'fp-badge--danger',
  cancelled: 'fp-badge--danger',
}

export default function QuoteDetail({ quoteId, onClose, onAddVersion, includeInPipeline, onPipelineChange, isReadOnly = false }) {
  const token = localStorage.getItem('token')
  const [quote, setQuote] = useState(null)
  const [versionsList, setVersionsList] = useState([])
  const [selectedVersion, setSelectedVersion] = useState(null)
  const [lineItems, setLineItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState(null)
  // Pipeline inclusion is owned by the parent quotes list — seed from prop and
  // re-sync whenever the parent's value changes (e.g. after refresh()).
  const [pipelineIncluded, setPipelineIncluded] = useState(!!includeInPipeline)
  useEffect(() => { setPipelineIncluded(!!includeInPipeline) }, [includeInPipeline])

  const loadQuote = useCallback(async () => {
    setError(null)
    try {
      const [qRes, vRes] = await Promise.all([
        fetch(`${API}/quotes/${quoteId}`, { headers: { Authorization: `Bearer ${token}` } }),
        fetch(`${API}/quotes/${quoteId}/versions`, { headers: { Authorization: `Bearer ${token}` } }),
      ])
      const q = await qRes.json()
      const v = await vRes.json()
      if (!qRes.ok) throw new Error(typeof q.detail === 'string' ? q.detail : `HTTP ${qRes.status}`)
      if (!vRes.ok) throw new Error(typeof v.detail === 'string' ? v.detail : `HTTP ${vRes.status}`)
      setQuote(q)
      setVersionsList(v)
      const active = q.active_version_data
      setSelectedVersion(active)
      setLineItems(active?.line_items || [])
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setLoading(false)
    }
  }, [quoteId, token])

  useEffect(() => { if (quoteId && token) loadQuote() }, [quoteId, token, loadQuote])

  function showToast(msg) {
    setToast(msg)
    setTimeout(() => setToast(null), 4000)
  }

  async function selectVersion(versionNumber) {
    if (!quote) return
    if (selectedVersion && selectedVersion.version_number === versionNumber) return
    setBusy(true)
    try {
      // re-fetch quote to get the requested version's line items (only active version comes back with items by default)
      // workaround: use the current active or, if not the requested one, hit /versions/X by fetching the full quote w/ active set
      // Simpler: keep what we have and refetch
      if (versionNumber === quote.active_version && quote.active_version_data) {
        setSelectedVersion(quote.active_version_data)
        setLineItems(quote.active_version_data.line_items || [])
      } else {
        // The current API only returns active_version_data on GET /quotes/{id}.
        // To show another version's lines, set it active temporarily — but that mutates state.
        // Instead: show summary only for non-active versions.
        const v = versionsList.find((x) => x.version_number === versionNumber)
        if (v) {
          setSelectedVersion({ ...v, line_items: null })
          setLineItems([])
        }
      }
    } finally {
      setBusy(false)
    }
  }

  async function setActive(versionNumber) {
    if (busy) return
    setBusy(true); setError(null)
    try {
      const r = await fetch(`${API}/quotes/${quoteId}/active-version`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ version_number: versionNumber }),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
      await loadQuote()
      showToast(`Version ${versionNumber} is now active`)
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  async function markAsSent() {
    if (busy || !quote) return
    setBusy(true); setError(null)
    try {
      const r = await fetch(`${API}/quotes/${quoteId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status: 'sent' }),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
      await loadQuote()
      showToast('Quote marked as Sent')
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  async function setStatus(newStatus, toastMsg) {
    if (busy || !quote) return
    setBusy(true); setError(null)
    try {
      const r = await fetch(`${API}/quotes/${quoteId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status: newStatus }),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
      await loadQuote()
      showToast(toastMsg)
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  async function togglePipelineInclusion() {
    if (busy || !quote) return
    const next = !pipelineIncluded
    setBusy(true); setError(null)
    setPipelineIncluded(next)
    try {
      const r = await fetch(`${API}/quotes/${quoteId}/pipeline-inclusion`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ include_in_pipeline: next }),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
      showToast(next ? 'Quote included in pipeline' : 'Quote removed from pipeline')
      if (typeof onPipelineChange === 'function') onPipelineChange(next)
    } catch (e) {
      setPipelineIncluded(!next)
      setError(e.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  const [pdfGenerating, setPdfGenerating] = useState(false)
  const [pdfAvailable, setPdfAvailable] = useState(false)
  const [scenarios, setScenarios] = useState([])
  const [activeScenario, setActiveScenario] = useState(null)
  const [scenarioBusy, setScenarioBusy] = useState(false)

  useEffect(() => {
    setPdfAvailable(!!selectedVersion?.pdf_generated_at)
  }, [selectedVersion])

  useEffect(() => {
    if (!quoteId || !token) return
    fetch(`${API}/quotes/${quoteId}/scenarios`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (r) => {
        if (!r.ok) return { scenarios: [], active_scenario: null }
        return r.json()
      })
      .then((data) => {
        setScenarios(data.scenarios || [])
        setActiveScenario(data.active_scenario || null)
      })
      .catch(() => {})
  }, [quoteId, token, quote])

  async function handleSelectScenario(scenario) {
    if (scenarioBusy) return
    setScenarioBusy(true); setError(null)
    try {
      const r1 = await fetch(`${API}/quotes/${quoteId}/active-scenario`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ scenario_label: scenario.scenario_label }),
      })
      if (!r1.ok) {
        const body = await r1.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r1.status}`)
      }
      const r2 = await fetch(`${API}/quotes/${quoteId}/active-version`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ version_number: scenario.version_number, scenario_label: scenario.scenario_label }),
      })
      if (!r2.ok) {
        const body = await r2.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r2.status}`)
      }
      await loadQuote()
      showToast(`Selected ${scenario.scenario_label} scenario`)
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setScenarioBusy(false)
    }
  }

  async function handleGeneratePdf() {
    if (pdfGenerating || !selectedVersion) return
    setPdfGenerating(true); setError(null)
    try {
      const r = await fetch(`${API}/quotes/${quoteId}/versions/${selectedVersion.version_number}/generate-pdf`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
      setPdfAvailable(true)
      showToast('PDF generated')
      await loadQuote()
    } catch (e) {
      setError(e.message || String(e))
    } finally {
      setPdfGenerating(false)
    }
  }

  async function handleDownloadPdf() {
    if (!selectedVersion) return
    try {
      const r = await fetch(`${API}/quotes/${quoteId}/versions/${selectedVersion.version_number}/pdf`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${r.status}`)
      }
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `quote-v${selectedVersion.version_number}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e.message || String(e))
    }
  }

  if (loading) return <div className="fp-card" style={{ color: '#64748B' }}>Loading quote…</div>
  if (error && !quote) return <div className="fp-alert fp-alert--danger">{error}</div>
  if (!quote) return null

  const currency = quote.currency_code || 'USD'
  const activeVersionNum = quote.active_version
  const isTerminal = quote.status === 'accepted' || quote.status === 'expired' || quote.status === 'cancelled'

  return (
    <div>
      <div className="fp-page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h2 className="fp-page-title">{quote.quote_name || 'Untitled Quote'}</h2>
          <div style={{ display: 'flex', gap: 12, alignItems: 'center', marginTop: 6, flexWrap: 'wrap' }}>
            <span className={`fp-badge ${STATUS_TONE[quote.status] || 'fp-badge--neutral'}`}>
              {quote.status.charAt(0).toUpperCase() + quote.status.slice(1)}
            </span>
            <span style={{ fontSize: 13, color: '#64748B' }}>Currency: <strong>{currency}</strong></span>
            <span style={{ fontSize: 13, color: '#64748B' }}>Active: v{activeVersionNum}</span>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {!isReadOnly && quote.status === 'draft' && (
            <button type="button" disabled={busy} onClick={markAsSent} className="fp-btn fp-btn--secondary">
              Mark as Sent
            </button>
          )}
          {!isReadOnly && quote.status === 'sent' && (
            <button type="button" disabled={busy}
              onClick={() => setStatus('accepted', 'Quote marked as Accepted')}
              className="fp-btn fp-btn--success">
              Mark as Accepted
            </button>
          )}
          {!isReadOnly && quote.status === 'sent' && (
            <button type="button" disabled={busy}
              onClick={() => setStatus('expired', 'Quote marked as Expired')}
              className="fp-btn fp-btn--ghost">
              Mark as Expired
            </button>
          )}
          {!isReadOnly && (quote.status === 'draft' || quote.status === 'sent') && (
            <button type="button" disabled={busy}
              onClick={() => {
                if (window.confirm('Cancel this quote? This cannot be undone.')) {
                  setStatus('cancelled', 'Quote cancelled')
                }
              }}
              className="fp-btn fp-btn--danger">
              Cancel Quote
            </button>
          )}
          {!isReadOnly && onAddVersion && !isTerminal && (
            <button type="button" disabled={busy} onClick={() => onAddVersion(quote)} className="fp-btn fp-btn--primary">
              Add Version
            </button>
          )}
          {onClose && (
            <button type="button" onClick={onClose} className="fp-btn fp-btn--ghost">Close</button>
          )}
        </div>
      </div>

      {error && <div className="fp-alert fp-alert--danger" style={{ marginBottom: 12 }}>{error}</div>}

      <section className="fp-card" style={{ marginBottom: 16 }}>
        <h3 className="fp-section-title">{isReadOnly ? 'Composition' : 'Pipeline & composition'}</h3>
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'flex-start' }}>
          {!isReadOnly && (
            <div style={{ flex: '1 1 240px' }}>
              <div style={{ fontSize: 13, color: '#64748B', marginBottom: 6 }}>Pipeline inclusion</div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: busy ? 'wait' : 'pointer' }}>
                <input
                  type="checkbox"
                  checked={pipelineIncluded}
                  disabled={busy}
                  onChange={togglePipelineInclusion}
                />
                <span style={{ fontWeight: 600, color: pipelineIncluded ? '#15803D' : '#64748B' }}>
                  {pipelineIncluded ? '✅ Included in pipeline' : '— Not included in pipeline'}
                </span>
              </label>
              <div style={{ fontSize: 12, color: '#94A3B8', marginTop: 6 }}>
                Channel managers control whether this quote contributes to the cross-deal pipeline total.
              </div>
            </div>
          )}
          <div style={{ flex: '1 1 240px' }}>
            <div style={{ fontSize: 13, color: '#64748B', marginBottom: 6 }}>Quote composition</div>
            <div style={{ fontWeight: 600, color: '#1E293B' }}>
              {(() => {
                const sw = !!selectedVersion?.includes_software
                const sv = !!selectedVersion?.includes_services
                if (sw && sv) return 'Software + Services'
                if (sw) return 'Software only'
                if (sv) return 'Services only'
                return '—'
              })()}
            </div>
            <div style={{ fontSize: 12, color: '#94A3B8', marginTop: 6 }}>
              Services quoting is read-only until the services pricing module ships.
            </div>
          </div>
        </div>
      </section>

      <section className="fp-card" style={{ marginBottom: 16 }}>
        <h3 className="fp-section-title">Versions</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {versionsList.map((v) => {
            const isSelected = selectedVersion && selectedVersion.version_number === v.version_number
            const isActive = v.version_number === activeVersionNum
            return (
              <button key={v.version_number} type="button" onClick={() => selectVersion(v.version_number)}
                style={{
                  padding: '6px 12px',
                  borderRadius: 6,
                  border: isSelected ? '2px solid #1A6EBB' : '1px solid #E0E4EA',
                  background: isActive ? '#1A6EBB' : '#fff',
                  color: isActive ? '#fff' : '#1E293B',
                  fontWeight: isActive ? 700 : 500,
                  cursor: 'pointer',
                  opacity: v.is_deleted ? 0.4 : 1,
                }}>
                v{v.version_number}{v.scenario_label ? ` (${v.scenario_label})` : ''}{isActive ? ' ★' : ''}
              </button>
            )
          })}
        </div>
        {!isReadOnly && selectedVersion && selectedVersion.version_number !== activeVersionNum && !selectedVersion.is_deleted && !isTerminal && (
          <button type="button" disabled={busy} onClick={() => setActive(selectedVersion.version_number)}
            className="fp-btn fp-btn--ghost" style={{ marginTop: 12 }}>
            Set as Active
          </button>
        )}
      </section>

      {scenarios.length > 0 && (
        <section className="fp-card" style={{ marginBottom: 16 }}>
          <h3 className="fp-section-title">Scenario Comparison</h3>
          <div style={{ display: 'grid', gridTemplateColumns: `repeat(${scenarios.length}, minmax(0, 1fr))`, gap: 12 }}>
            {scenarios.map((scenario) => {
              const isActive = scenario.scenario_label === activeScenario
              return (
                <div key={scenario.scenario_label}
                  style={{
                    border: isActive ? '2px solid #1A6EBB' : '1px solid #E0E4EA',
                    borderRadius: 8,
                    overflow: 'hidden',
                    background: '#fff',
                  }}>
                  <div style={{
                    background: '#1A6EBB', color: '#fff',
                    padding: '8px 12px', fontWeight: 700,
                    display: 'flex', justifyContent: 'space-between',
                  }}>
                    <span>{isActive ? '⭐ ' : ''}{scenario.scenario_label.charAt(0).toUpperCase() + scenario.scenario_label.slice(1)}</span>
                    <span style={{ fontSize: 12, opacity: 0.85 }}>v{scenario.version_number}</span>
                  </div>
                  <div style={{ padding: 14 }}>
                    <div style={{ fontSize: 13, color: '#64748B', textTransform: 'capitalize', marginBottom: 8 }}>
                      {scenario.feature_plan} Plan
                    </div>
                    <div style={{ fontSize: 22, fontWeight: 700, color: '#1A6EBB', marginBottom: 4 }}>
                      {fmtMoney(scenario.grand_total_after_discount, currency)}
                    </div>
                    <div style={{ fontSize: 11, color: '#94A3B8', marginBottom: 14 }}>per year</div>
                    {isActive ? (
                      <div style={{ color: '#1A6EBB', fontWeight: 600, fontSize: 13 }}>✓ Selected</div>
                    ) : !isReadOnly ? (
                      <button
                        type="button"
                        disabled={scenarioBusy}
                        onClick={() => handleSelectScenario(scenario)}
                        className="fp-btn fp-btn--primary"
                        style={{ width: '100%' }}
                      >
                        Select This Option
                      </button>
                    ) : null}
                  </div>
                </div>
              )
            })}
          </div>
        </section>
      )}

      <section className="fp-card" style={{ marginBottom: 16 }}>
        <h3 className="fp-section-title">Line items{selectedVersion ? ` — Version ${selectedVersion.version_number}` : ''}</h3>
        {!lineItems || lineItems.length === 0 ? (
          <div style={{ color: '#64748B', fontSize: 13 }}>
            {selectedVersion && selectedVersion.version_number !== activeVersionNum
              ? 'Line items only display for the active version. Switch to active or use Set as Active to view.'
              : 'No line items.'}
          </div>
        ) : (
          <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#1A6EBB', color: '#fff' }}>
                <th style={{ textAlign: 'left', padding: 8 }}>Description</th>
                <th style={{ textAlign: 'right', padding: 8 }}>Qty</th>
                <th style={{ textAlign: 'right', padding: 8 }}>Unit Price</th>
                <th style={{ textAlign: 'right', padding: 8 }}>Discount %</th>
                <th style={{ textAlign: 'right', padding: 8 }}>Total Before</th>
                <th style={{ textAlign: 'right', padding: 8 }}>Total After</th>
              </tr>
            </thead>
            <tbody>
              {lineItems.map((li) => (
                <tr key={li.id || `${li.line_order}-${li.line_type}`} style={{
                  borderBottom: '1px solid #F1F5F9',
                  background: li.line_type === 'free_allocation' ? '#F0FDF4' : 'transparent',
                  color: li.line_type === 'free_allocation' ? '#15803D' : 'inherit',
                  fontStyle: li.line_type === 'free_allocation' ? 'italic' : 'normal',
                }}>
                  <td style={{ padding: 8 }}>{li.description}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>{li.quantity}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>{Number(li.unit_price) > 0 ? fmtMoney(li.unit_price, currency) : '—'}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>{Number(li.discount_pct) > 0 ? `${Number(li.discount_pct).toFixed(0)}%` : '—'}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>{fmtMoney(li.total_before_discount, currency)}</td>
                  <td style={{ padding: 8, textAlign: 'right' }}>{fmtMoney(li.total_after_discount, currency)}</td>
                </tr>
              ))}
              <tr style={{ borderTop: '2px solid #1A6EBB', background: '#F5F7FA', fontWeight: 700 }}>
                <td style={{ padding: 8 }} colSpan={4}>Grand Total</td>
                <td style={{ padding: 8, textAlign: 'right' }}>{fmtMoney(selectedVersion?.grand_total_before_discount, currency)}</td>
                <td style={{ padding: 8, textAlign: 'right' }}>{fmtMoney(selectedVersion?.grand_total_after_discount, currency)}</td>
              </tr>
            </tbody>
          </table>
        )}
      </section>

      <section className="fp-card" style={{ marginBottom: 16 }}>
        <h3 className="fp-section-title">PDF</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {!isReadOnly && (
            <button type="button" data-action="generate-pdf" disabled={pdfGenerating || !selectedVersion}
              onClick={handleGeneratePdf} className="fp-btn fp-btn--secondary">
              {pdfGenerating ? 'Generating…' : 'Generate PDF'}
            </button>
          )}
          <button type="button" data-action="download-pdf" disabled={!pdfAvailable}
            onClick={handleDownloadPdf} className="fp-btn fp-btn--primary">
            Download PDF
          </button>
        </div>
        {selectedVersion?.pdf_generated_at && (
          <div style={{ marginTop: 8, fontSize: 12, color: '#64748B' }}>
            Last generated: {new Date(selectedVersion.pdf_generated_at).toLocaleString()}
          </div>
        )}
      </section>

      {toast && (
        <div role="status" style={{ position: 'fixed', bottom: 24, right: 24, background: '#1b8743', color: '#fff', padding: '12px 18px', borderRadius: 8, boxShadow: '0 6px 24px rgba(0,0,0,0.15)', fontSize: 14, zIndex: 1100 }}>
          {toast}
        </div>
      )}
    </div>
  )
}
