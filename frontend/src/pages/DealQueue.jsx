import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { SortableTh } from '../components/SortableTh.jsx'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

// FPRM-317 -- options reused by the New Deal modal (kept in sync with the
// partner-facing form in DealRegistrationForm.jsx).
const _COMPANY_SIZE_OPTIONS = ['1-10', '11-50', '51-200', '201-500', '500+']
const _FEATURE_PLAN_OPTIONS = [
  { value: 'starter',      label: 'Starter' },
  { value: 'professional', label: 'Professional' },
  { value: 'enterprise',   label: 'Enterprise' },
]

const STATUS_TONE = {
  draft: 'fp-badge--neutral',
  submitted: 'fp-badge--info',
  under_review: 'fp-badge--warning',
  info_required: 'fp-badge--warning',
  approved: 'fp-badge--success',
  rejected: 'fp-badge--danger',
  expired: 'fp-badge--neutral',
}

const STATUS_LABEL = {
  draft: 'Draft',
  submitted: 'Submitted',
  under_review: 'Under review',
  info_required: 'Info required',
  approved: 'Approved',
  rejected: 'Rejected',
  expired: 'Expired',
}

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'under_review', label: 'Under review' },
  { value: 'info_required', label: 'Info required' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
]

function StatusBadge({ status }) {
  return (
    <span className={`fp-badge ${STATUS_TONE[status] || 'fp-badge--neutral'}`}>
      {STATUS_LABEL[status] || status}
    </span>
  )
}

function formatMoney(value) {
  if (value === null || value === undefined || value === '') return '—'
  const num = Number(value)
  if (!Number.isFinite(num)) return '—'
  return `$${num.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
}

function formatPipelineMoney(value) {
  if (value === null || value === undefined || value === '') return '—'
  const num = Number(value)
  if (!Number.isFinite(num)) return '—'
  return `$${num.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function formatDate(value) {
  if (!value) return '—'
  try { return new Date(value).toLocaleDateString() } catch { return value }
}

// FPRM-317 -- "New Deal" modal: channel manager creates a draft deal on
// behalf of a partner. Captures the essentials (partner org + Section A core
// fields + opening SPICED narrative). The partner then receives the draft
// and can flesh out the rest of Section B before submitting.
function NewDealModal({ token, onClose, onCreated }) {
  const [partners, setPartners] = useState([])
  const [partnersLoading, setPartnersLoading] = useState(true)
  const [partnersErr, setPartnersErr] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [draft, setDraft] = useState({
    partner_org_id: '',
    customer_name: '',
    deal_name: '',
    customer_contact_email: '',
    estimated_deal_value: '',
    estimated_close_date: '',
    engagement_date: '',
    prospect_contact_name: '',
    prospect_contact_position: '',
    prospect_phone: '',
    industry_sector: '',
    company_size: '',
    feature_plan_preference: '',
    about_client: '',
    pain: '',
    next_steps: '',
  })

  useEffect(() => {
    if (!token) return
    fetch(`${API}/internal/partners?status=active&page_size=200`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then((data) => setPartners(data.items || data || []))
      .catch((e) => setPartnersErr(e.message))
      .finally(() => setPartnersLoading(false))
  }, [token])

  function setField(k, v) { setDraft((d) => ({ ...d, [k]: v })) }

  const canSubmit = (
    draft.partner_org_id && draft.customer_name.trim() && draft.deal_name.trim() && !saving
  )

  async function submit(e) {
    e.preventDefault()
    setError(null)
    setSaving(true)
    try {
      const payload = {}
      for (const [k, v] of Object.entries(draft)) {
        if (v === '' || v === null || v === undefined) continue
        if (k === 'estimated_deal_value') {
          const n = Number(v); if (Number.isFinite(n)) payload[k] = n
          continue
        }
        payload[k] = v
      }
      const r = await fetch(`${API}/deal-registrations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(payload),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) {
        const msg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail || body)
        throw new Error(msg || `HTTP ${r.status}`)
      }
      onCreated(body)
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div role="dialog" aria-modal="true" style={{
      position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.45)',
      display: 'flex', alignItems: 'flex-start', justifyContent: 'center', zIndex: 1000,
      padding: '40px 16px', overflow: 'auto',
    }}>
      <div style={{ background: '#fff', borderRadius: 10, padding: 24, maxWidth: 720, width: '100%', boxShadow: '0 10px 30px rgba(15,23,42,0.2)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h2 style={{ margin: 0, fontSize: 18 }}>New Deal (on behalf of partner)</h2>
          <button type="button" onClick={onClose} aria-label="Close" style={{ background: 'transparent', border: 'none', fontSize: 22, cursor: 'pointer', color: '#475569' }}>×</button>
        </div>
        <p style={{ margin: '0 0 16px', fontSize: 13, color: '#475569' }}>
          You are creating a draft deal on behalf of a partner. The partner will see this in their portal and can flesh out remaining Section B fields before submitting.
        </p>
        {error && <div className="fp-alert fp-alert--danger" style={{ marginBottom: 12 }}>{error}</div>}
        <form onSubmit={submit} style={{ display: 'grid', gap: 12 }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>Partner organisation *</span>
            {partnersLoading ? <span style={{ fontSize: 13, color: '#94A3B8' }}>Loading partners…</span> : (
              <select required value={draft.partner_org_id} onChange={(e) => setField('partner_org_id', e.target.value)}
                      style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6, fontSize: 14 }}>
                <option value="">Select partner…</option>
                {partners.map((p) => (
                  <option key={p.id} value={p.id}>{p.legal_name || p.id.slice(0, 8)}</option>
                ))}
              </select>
            )}
            {partnersErr && <span style={{ fontSize: 12, color: '#B91C1C' }}>{partnersErr}</span>}
          </label>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>Customer name *</span>
              <input required value={draft.customer_name} onChange={(e) => setField('customer_name', e.target.value)}
                     style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>Deal name *</span>
              <input required value={draft.deal_name} onChange={(e) => setField('deal_name', e.target.value)}
                     style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>Customer contact email</span>
              <input type="email" value={draft.customer_contact_email} onChange={(e) => setField('customer_contact_email', e.target.value)}
                     style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>Industry sector</span>
              <input value={draft.industry_sector} onChange={(e) => setField('industry_sector', e.target.value)}
                     style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>Company size</span>
              <select value={draft.company_size} onChange={(e) => setField('company_size', e.target.value)}
                      style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }}>
                <option value="">Select…</option>
                {_COMPANY_SIZE_OPTIONS.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>Estimated value (USD)</span>
              <input type="number" value={draft.estimated_deal_value} onChange={(e) => setField('estimated_deal_value', e.target.value)}
                     style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>Estimated close date</span>
              <input type="date" value={draft.estimated_close_date} onChange={(e) => setField('estimated_close_date', e.target.value)}
                     style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>Engagement date</span>
              <input type="date" value={draft.engagement_date} onChange={(e) => setField('engagement_date', e.target.value)}
                     style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>Prospect contact name</span>
              <input value={draft.prospect_contact_name} onChange={(e) => setField('prospect_contact_name', e.target.value)}
                     style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>Contact position / title</span>
              <input value={draft.prospect_contact_position} onChange={(e) => setField('prospect_contact_position', e.target.value)}
                     style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>Prospect phone</span>
              <input type="tel" value={draft.prospect_phone} onChange={(e) => setField('prospect_phone', e.target.value)}
                     style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
            </label>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>Indicative feature plan</span>
              <select value={draft.feature_plan_preference} onChange={(e) => setField('feature_plan_preference', e.target.value)}
                      style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }}>
                <option value="">Select…</option>
                {_FEATURE_PLAN_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </label>
          </div>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>About the client</span>
            <textarea rows={3} value={draft.about_client} onChange={(e) => setField('about_client', e.target.value)}
                      style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6, fontFamily: 'inherit' }} />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>Pain (P)</span>
            <textarea rows={2} value={draft.pain} onChange={(e) => setField('pain', e.target.value)}
                      style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6, fontFamily: 'inherit' }} />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>Next steps</span>
            <textarea rows={2} value={draft.next_steps} onChange={(e) => setField('next_steps', e.target.value)}
                      style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6, fontFamily: 'inherit' }} />
          </label>

          <p style={{ margin: '4px 0 0', fontSize: 12, color: '#64748B' }}>
            The partner will be able to add remaining Section B fields (Current Systems, Features Required, Impact, Critical Event, Decision) from their portal before submitting.
          </p>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 8 }}>
            <button type="button" className="fp-btn fp-btn--ghost" onClick={onClose} disabled={saving}>Cancel</button>
            <button type="submit" className="fp-btn fp-btn--primary" disabled={!canSubmit}>
              {saving ? 'Creating…' : 'Create draft'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}


export default function DealQueue() {
  const token = localStorage.getItem('token')
  const navigate = useNavigate()
  const [statusFilter, setStatusFilter] = useState('submitted')
  const [search, setSearch] = useState('')
  const [deals, setDeals] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actionSaving, setActionSaving] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [newDealOpen, setNewDealOpen] = useState(false)
  const [toast, setToast] = useState(null)
  const [sort, setSort] = useState({ field: 'created_at', dir: 'desc' })

  function toggleSort(field) {
    setSort((s) => s.field === field
      ? { field, dir: s.dir === 'asc' ? 'desc' : 'asc' }
      : { field, dir: 'asc' })
  }

  function reload() {
    if (!token) return
    setLoading(true)
    setError(null)
    const qs = new URLSearchParams({ limit: '200', sort_by: sort.field, sort_dir: sort.dir })
    if (statusFilter) qs.set('status', statusFilter)
    fetch(`${API}/internal/deals?${qs.toString()}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (r) => {
        if (!r.ok) {
          const body = await r.json().catch(() => ({}))
          throw new Error(body.detail || `HTTP ${r.status}`)
        }
        return r.json()
      })
      .then((data) => setDeals(data.items || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { reload() /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [statusFilter, sort])

  const visibleDeals = useMemo(() => {
    if (!search) return deals
    const q = search.toLowerCase()
    return deals.filter((d) => (
      (d.deal_name || '').toLowerCase().includes(q) ||
      (d.customer_name || '').toLowerCase().includes(q) ||
      (d.partner_legal_name || '').toLowerCase().includes(q)
    ))
  }, [deals, search])

  async function exportCSV() {
    setExporting(true)
    try {
      const r = await fetch(`${API}/internal/deals?export=csv`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'deals_export.csv'
      document.body.appendChild(a); a.click(); document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('CSV export error:', e); setError(e.message)
    } finally {
      setExporting(false)
    }
  }

  async function startReview(deal) {
    setActionSaving(true)
    try {
      const r = await fetch(`${API}/internal/deals/${deal.id}/start-review`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${r.status}`)
      }
      reload()
    } catch (e) {
      setError(e.message)
    } finally {
      setActionSaving(false)
    }
  }

  return (
    <div className="fp-page">
      <div className="fp-page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 className="fp-page-title">Deal Queue</h1>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button type="button" className="fp-btn fp-btn--primary" onClick={() => setNewDealOpen(true)}>
            + New Deal
          </button>
          <button type="button" onClick={exportCSV} disabled={exporting}
                  style={{ fontSize: '0.75rem', padding: '4px 10px', border: '1px solid #CBD5E0', borderRadius: 4, backgroundColor: 'white', color: '#718096', cursor: 'pointer', fontWeight: 400 }}>
            {exporting ? 'Exporting...' : 'Export CSV'}
          </button>
        </div>
      </div>

      {toast && (
        <div className="fp-alert fp-alert--success" style={{ marginBottom: 12 }}>{toast}</div>
      )}

      {/* Filter bar — single fp-card horizontal row per AD-26. Status dropdown
          LEFT, free-text search RIGHT (client-side, across deal/customer/partner). */}
      <section className="fp-card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
            style={{ padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }}>
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <input type="search" placeholder="Search by deal, customer, or partner…"
            value={search} onChange={(e) => setSearch(e.target.value)}
            style={{ flex: 1, minWidth: 200, padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }} />
        </div>
      </section>

      {error && <div className="fp-alert fp-alert--danger">{error}</div>}

      {loading && <div className="fp-card" style={{ color: 'var(--fp-text-secondary)' }}>Loading deals…</div>}

      {!loading && deals.length === 0 && !error && (
        <div className="fp-card" style={{ textAlign: 'center', padding: 40, color: 'var(--fp-text-secondary)' }}>
          No deals in this view.
        </div>
      )}

      {!loading && deals.length > 0 && visibleDeals.length === 0 && (
        <div className="fp-card" style={{ textAlign: 'center', padding: 32, color: 'var(--fp-text-secondary)' }}>
          No deals match the current search.
        </div>
      )}

      {!loading && visibleDeals.length > 0 && (
        <section className="fp-card">
          <table className="fp-table">
            <thead>
              <tr>
                <SortableTh field="deal_name" sort={sort} onSort={toggleSort}>Deal</SortableTh>
                <SortableTh field="partner_org" sort={sort} onSort={toggleSort}>Partner org</SortableTh>
                <SortableTh field="customer_name" sort={sort} onSort={toggleSort}>Customer</SortableTh>
                <SortableTh field="status" sort={sort} onSort={toggleSort}>Status</SortableTh>
                <SortableTh field="deal_value" sort={sort} onSort={toggleSort}>Est. value</SortableTh>
                <SortableTh field="pipeline_total" sort={sort} onSort={toggleSort}>Pipeline</SortableTh>
                <SortableTh field="submitted_at" sort={sort} onSort={toggleSort}>Submitted</SortableTh>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {visibleDeals.map((d) => (
                <tr key={d.id}>
                  <td>
                    <Link to={`/internal/deals/${d.id}`}
                          style={{ color: 'var(--fp-primary)', fontWeight: 600, textDecoration: 'none' }}>
                      {d.deal_name || '(unnamed)'}
                    </Link>
                  </td>
                  <td style={{ fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>
                    {d.partner_legal_name || (d.partner_org_id ? `${d.partner_org_id.slice(0, 8)}…` : '—')}
                  </td>
                  <td>{d.customer_name || '—'}</td>
                  <td><StatusBadge status={d.status} /></td>
                  <td>{formatMoney(d.estimated_deal_value)}</td>
                  <td>{d.pipeline_total == null ? '—' : formatPipelineMoney(d.pipeline_total)}</td>
                  <td>{formatDate(d.submitted_at)}</td>
                  <td>
                    {d.status === 'submitted' && (
                      <button
                        type="button"
                        className="fp-btn fp-btn--primary fp-btn--sm"
                        disabled={actionSaving}
                        onClick={() => startReview(d)}
                      >
                        Start review
                      </button>
                    )}
                    {d.status !== 'submitted' && (
                      <Link to={`/internal/deals/${d.id}`}
                            className="fp-btn fp-btn--ghost fp-btn--sm"
                            style={{ textDecoration: 'none' }}>
                        Open
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {newDealOpen && (
        <NewDealModal
          token={token}
          onClose={() => setNewDealOpen(false)}
          onCreated={(deal) => {
            setNewDealOpen(false)
            const label = deal?.deal_name || 'New deal'
            setToast(`Draft created: ${label}`)
            setTimeout(() => setToast(null), 4000)
            reload()
            // Optional handoff: navigate the channel manager straight to the
            // detail page so they can keep editing collaboration / quotes.
            if (deal?.id) navigate(`/internal/deals/${deal.id}`)
          }}
        />
      )}

    </div>
  )
}
