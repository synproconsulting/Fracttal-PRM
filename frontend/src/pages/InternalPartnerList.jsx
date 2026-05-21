import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import { SortableTh } from '../components/SortableTh.jsx'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

function decodeJwt(token) {
  try {
    const parts = token.split('.')
    if (parts.length < 2) return null
    const padded = parts[1] + '==='.slice((parts[1].length + 3) % 4)
    return JSON.parse(atob(padded.replace(/-/g, '+').replace(/_/g, '/')))
  } catch (_) { return null }
}

const STATUS_ADMIN_ROLES = new Set(['system_admin', 'channel_ops_admin'])

const STATUS_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'applicant', label: 'Applicant' },
  { value: 'active', label: 'Active' },
  { value: 'suspended', label: 'Suspended' },
  { value: 'inactive', label: 'Inactive' },
  { value: 'terminated', label: 'Terminated' },
]
const CATEGORY_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'master', label: 'Master' },
  { value: 'promotor', label: 'Promotor' },
  { value: 'reseller', label: 'Reseller' },
]
const TIER_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'registered', label: 'Registered' },
  { value: 'silver', label: 'Silver' },
  { value: 'gold', label: 'Gold' },
  { value: 'platinum', label: 'Platinum' },
]

const STATUS_TONE = {
  applicant:  { bg: '#FEF3C7', fg: '#92400E' },
  active:     { bg: '#DCFCE7', fg: '#166534' },
  suspended:  { bg: '#FEE2E2', fg: '#991B1B' },
  inactive:   { bg: '#E5E7EB', fg: '#475569' },
  terminated: { bg: '#1B2236', fg: '#fff' },
}
const STATUS_LABEL = {
  applicant: 'Applicant',
  active: 'Active',
  suspended: 'Suspended',
  inactive: 'Inactive',
  terminated: 'Terminated',
}

function StatusBadge({ value }) {
  const tone = STATUS_TONE[value] || { bg: '#E5E7EB', fg: '#475569' }
  return (
    <span style={{
      background: tone.bg, color: tone.fg,
      padding: '2px 10px', borderRadius: 12,
      fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap',
    }}>
      {STATUS_LABEL[value] || value || '—'}
    </span>
  )
}

function fmtDate(value) {
  if (!value) return '—'
  try { return new Date(value).toISOString().slice(0, 10) }
  catch (_) { return value }
}

function useDebounced(value, delay) {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return v
}

export default function InternalPartnerList() {
  const [exporting, setExporting] = useState(false)
  async function exportCSV() {
    setExporting(true)
    try {
      const token = localStorage.getItem('token')
      const r = await fetch(`${API}/internal/partners?export=csv`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'partners_export.csv'
      document.body.appendChild(a); a.click(); document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('CSV export error:', e)
    } finally {
      setExporting(false)
    }
  }

  const ctx = useOutletContext() || {}
  const { token } = ctx
  const payload = useMemo(() => (token ? decodeJwt(token) : null), [token])
  const canManageStatus = STATUS_ADMIN_ROLES.has(payload?.role)

  const [searchInput, setSearchInput] = useState('')
  const debouncedSearch = useDebounced(searchInput, 300)
  const [status, setStatus] = useState('')
  const [category, setCategory] = useState('')
  const [tier, setTier] = useState('')
  const [page, setPage] = useState(1)
  const [sort, setSort] = useState({ field: 'created_at', dir: 'desc' })
  const pageSize = 20

  function toggleSort(field) {
    setSort((s) => s.field === field
      ? { field, dir: s.dir === 'asc' ? 'desc' : 'asc' }
      : { field, dir: 'asc' })
  }

  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [statusModal, setStatusModal] = useState(null) // { partner, nextStatus }
  const [statusSaving, setStatusSaving] = useState(false)
  const [statusError, setStatusError] = useState(null)
  const [toast, setToast] = useState(null)

  const dismissToast = useCallback(() => setToast(null), [])
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(dismissToast, 3000)
    return () => clearTimeout(t)
  }, [toast, dismissToast])

  async function applyStatusChange() {
    if (!statusModal) return
    setStatusSaving(true); setStatusError(null)
    try {
      const r = await fetch(`${API}/internal/partners/${statusModal.partner.id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status: statusModal.nextStatus }),
      })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(body.detail || `HTTP ${r.status}`)
      setStatusModal(null)
      setToast('Partner organisation status updated')
      load()
    } catch (err) {
      setStatusError(err.message)
    } finally {
      setStatusSaving(false)
    }
  }

  // Reset to page 1 whenever a filter changes.
  const filterKey = `${debouncedSearch}|${status}|${category}|${tier}`
  const filterKeyRef = useRef(filterKey)
  useEffect(() => {
    if (filterKeyRef.current !== filterKey) {
      filterKeyRef.current = filterKey
      setPage(1)
    }
  }, [filterKey])

  const load = useCallback(() => {
    setLoading(true); setError(null)
    const params = new URLSearchParams()
    if (debouncedSearch) params.set('search', debouncedSearch)
    if (status) params.set('status', status)
    if (category) params.set('category', category)
    if (tier) params.set('tier', tier)
    params.set('page', String(page))
    params.set('page_size', String(pageSize))
    params.set('sort_by', sort.field)
    params.set('sort_dir', sort.dir)
    fetch(`${API}/internal/partners?${params.toString()}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        const b = await r.json().catch(() => ({}))
        if (!r.ok) throw new Error(b.detail || `HTTP ${r.status}`)
        return b
      })
      .then((b) => { setRows(b.items || []); setTotal(b.total || 0) })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [token, debouncedSearch, status, category, tier, page, sort])

  useEffect(() => { load() }, [load])

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / pageSize)),
    [total]
  )

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: 22, margin: '0 0 4px' }}>Partner Organisations</h1>
          <p style={{ margin: 0, color: '#5A6478' }}>
            {total} partner{total === 1 ? '' : 's'} across all categories and statuses.
          </p>
        </div>
        <button type="button" onClick={exportCSV} disabled={exporting} style={{ fontSize: '0.75rem', padding: '4px 10px', border: '1px solid #CBD5E0', borderRadius: 4, backgroundColor: 'white', color: '#718096', cursor: 'pointer', fontWeight: 400 }}>{exporting ? 'Exporting...' : 'Export CSV'}</button>
      </div>

      <div className="fp-card" style={{ padding: 12, marginTop: 16, display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1, minWidth: 240 }}>
          <span style={{ fontSize: 12, color: '#5A6478', fontWeight: 600 }}>Search</span>
          <input
            placeholder="Partner legal name…"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }}
          />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#5A6478', fontWeight: 600 }}>Status</span>
          <select value={status} onChange={(e) => setStatus(e.target.value)}
                  style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6, minWidth: 140 }}>
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#5A6478', fontWeight: 600 }}>Category</span>
          <select value={category} onChange={(e) => setCategory(e.target.value)}
                  style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6, minWidth: 140 }}>
            {CATEGORY_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#5A6478', fontWeight: 600 }}>Tier</span>
          <select value={tier} onChange={(e) => setTier(e.target.value)}
                  style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6, minWidth: 140 }}>
            {TIER_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>
      </div>

      {loading && <div className="fp-card" style={{ padding: 18, marginTop: 16 }}>Loading partners…</div>}
      {error && <div className="fp-alert fp-alert--danger" style={{ marginTop: 16 }}>Could not load partners: {error}</div>}

      {!loading && !error && (
        <>
          <div className="fp-card" style={{ padding: 0, marginTop: 16, overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
              <thead>
                <tr style={{ background: '#F8FAFC' }}>
                  <SortableTh field="legal_name" sort={sort} onSort={toggleSort} style={{ padding: '10px 12px' }}>Legal Name</SortableTh>
                  <SortableTh field="partner_category" sort={sort} onSort={toggleSort} style={{ padding: '10px 12px' }}>Category</SortableTh>
                  <SortableTh field="tier" sort={sort} onSort={toggleSort} style={{ padding: '10px 12px' }}>Tier</SortableTh>
                  <SortableTh field="status" sort={sort} onSort={toggleSort} style={{ padding: '10px 12px' }}>Status</SortableTh>
                  <th style={{ textAlign: 'left', padding: '10px 12px' }}>Activation</th>
                  <SortableTh field="created_at" sort={sort} onSort={toggleSort} style={{ padding: '10px 12px' }}>Created</SortableTh>
                  <th style={{ textAlign: 'right', padding: '10px 12px' }}>Docs</th>
                  {canManageStatus && (
                    <th style={{ textAlign: 'right', padding: '10px 12px' }}>Actions</th>
                  )}
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={canManageStatus ? 8 : 7} style={{ padding: 18, textAlign: 'center', color: '#5A6478' }}>
                      No partner organisations found.
                    </td>
                  </tr>
                )}
                {rows.map((p) => (
                  <tr key={p.id} style={{ borderTop: '1px solid #E5E7EB' }}>
                    <td style={{ padding: '10px 12px' }}>
                      <Link to={`/internal/partners/${p.id}/profile`}
                            style={{ color: '#1A6EBB', fontWeight: 600, textDecoration: 'none' }}>
                        {p.legal_name}
                      </Link>
                    </td>
                    <td style={{ padding: '10px 12px', textTransform: 'capitalize' }}>{p.partner_category || '—'}</td>
                    <td style={{ padding: '10px 12px', textTransform: 'capitalize' }}>{p.tier || '—'}</td>
                    <td style={{ padding: '10px 12px' }}><StatusBadge value={p.status} /></td>
                    <td style={{ padding: '10px 12px' }}>
                      {p.activation_complete
                        ? <span style={{ color: '#166534', fontWeight: 600 }}>✔ Activated</span>
                        : <span style={{ color: '#92400E', fontWeight: 600 }}>⏳ Pending</span>}
                    </td>
                    <td style={{ padding: '10px 12px' }}>{fmtDate(p.created_at)}</td>
                    <td style={{ padding: '10px 12px', textAlign: 'right' }}>
                      <Link to={`/internal/partners/${p.id}/documents`}
                            style={{ color: '#1A6EBB', textDecoration: 'none', fontSize: 13 }}>
                        Docs →
                      </Link>
                    </td>
                    {canManageStatus && (
                      <td style={{ padding: '10px 12px', textAlign: 'right' }}>
                        {p.status === 'active' && (
                          <button
                            type="button"
                            onClick={() => { setStatusError(null); setStatusModal({ partner: p, nextStatus: 'suspended' }) }}
                            style={{
                              background: 'transparent', border: '1px solid #991B1B',
                              color: '#991B1B', padding: '4px 10px', borderRadius: 6,
                              fontSize: 12, fontWeight: 600, cursor: 'pointer',
                            }}
                          >
                            Suspend
                          </button>
                        )}
                        {p.status === 'suspended' && (
                          <button
                            type="button"
                            onClick={() => { setStatusError(null); setStatusModal({ partner: p, nextStatus: 'active' }) }}
                            style={{
                              background: 'transparent', border: '1px solid #166534',
                              color: '#166534', padding: '4px 10px', borderRadius: 6,
                              fontSize: 12, fontWeight: 600, cursor: 'pointer',
                            }}
                          >
                            Reactivate
                          </button>
                        )}
                        {p.status !== 'active' && p.status !== 'suspended' && (
                          <span style={{ color: '#94A3B8', fontSize: 12 }}>—</span>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {total > pageSize && (
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
              <button
                type="button"
                className="fp-btn fp-btn--ghost fp-btn--sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
              >
                ← Prev
              </button>
              <span style={{ alignSelf: 'center', fontSize: 13, color: '#5A6478' }}>
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                className="fp-btn fp-btn--ghost fp-btn--sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}

      {statusModal && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed', inset: 0, background: 'rgba(15, 23, 42, 0.45)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
          }}
        >
          <div style={{
            background: '#fff', borderRadius: 10, padding: 24,
            maxWidth: 460, width: 'calc(100% - 32px)',
            boxShadow: '0 10px 30px rgba(15,23,42,0.2)',
          }}>
            <h2 style={{ margin: '0 0 8px', fontSize: 18 }}>
              {statusModal.nextStatus === 'suspended' ? 'Suspend partner organisation' : 'Reactivate partner organisation'}
            </h2>
            <p style={{ margin: '0 0 16px', color: '#475569', fontSize: 14 }}>
              {statusModal.nextStatus === 'suspended'
                ? <>Suspend <strong>{statusModal.partner.legal_name}</strong>? This will mark the organisation as suspended.</>
                : <>Reactivate <strong>{statusModal.partner.legal_name}</strong>? This will return the organisation to active status.</>}
            </p>
            {statusError && (
              <div className="fp-alert fp-alert--danger" style={{ marginBottom: 12 }}>{statusError}</div>
            )}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button
                type="button"
                className="fp-btn fp-btn--ghost"
                onClick={() => { setStatusModal(null); setStatusError(null) }}
                disabled={statusSaving}
              >
                Cancel
              </button>
              <button
                type="button"
                className="fp-btn fp-btn--primary"
                onClick={applyStatusChange}
                disabled={statusSaving}
              >
                {statusSaving ? 'Saving…' : statusModal.nextStatus === 'suspended' ? 'Suspend' : 'Reactivate'}
              </button>
            </div>
          </div>
        </div>
      )}

      {toast && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24, zIndex: 1100,
          background: '#166534', color: '#fff',
          padding: '10px 16px', borderRadius: 8,
          boxShadow: '0 8px 20px rgba(15,23,42,0.2)',
          fontSize: 14, fontWeight: 600,
        }}>
          {toast}
        </div>
      )}
    </div>
  )
}
