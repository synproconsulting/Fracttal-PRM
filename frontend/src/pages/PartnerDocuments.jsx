import { useEffect, useMemo, useState } from 'react'
import { useOutletContext, useParams } from 'react-router-dom'
import { SortableTh } from '../components/SortableTh.jsx'

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

const STATUS_LABELS = {
  approved: 'Approved',
  pending_review: 'Pending review',
  rejected: 'Rejected',
  expired: 'Expired',
}

const STATUS_TONE = {
  approved: 'fp-badge--success',
  pending_review: 'fp-badge--warning',
  rejected: 'fp-badge--danger',
  expired: 'fp-badge--neutral',
}

function StatusBadge({ status }) {
  return (
    <span className={`fp-badge ${STATUS_TONE[status] || 'fp-badge--neutral'}`}>
      {STATUS_LABELS[status] || status}
    </span>
  )
}

const DOCUMENT_TYPES = [
  { value: 'id_legal_representative', label: 'ID of legal representative' },
  { value: 'power_of_attorney', label: 'Power of attorney' },
  { value: 'articles_of_incorporation', label: 'Articles of incorporation' },
  { value: 'beneficial_owners_list', label: 'Beneficial owners list' },
  { value: 'fiscal_id', label: 'Fiscal ID' },
  { value: 'proof_of_fiscal_domicile', label: 'Proof of fiscal domicile' },
  { value: 'bank_certificate', label: 'Bank certificate' },
  { value: 'nda', label: 'NDA' },
  { value: 'insurance', label: 'Insurance certificate' },
  { value: 'other', label: 'Other' },
]

const ACCEPT_TYPES = '.pdf,.jpg,.jpeg,.png'
const ACCEPT_MIME = new Set(['application/pdf', 'image/jpeg', 'image/png'])
const MAX_FILE_BYTES = 10 * 1024 * 1024

function UploadModal({ partnerId, token, onClose, onUploaded }) {
  const [docType, setDocType] = useState('fiscal_id')
  const [file, setFile] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  function onFileChange(e) {
    const f = e.target.files?.[0] || null
    setError(null)
    if (!f) {
      setFile(null)
      return
    }
    if (!ACCEPT_MIME.has(f.type) && !/\.(pdf|jpe?g|png)$/i.test(f.name)) {
      setError('Only PDF, JPG and PNG files are accepted.')
      return
    }
    if (f.size > MAX_FILE_BYTES) {
      setError('File is larger than 10 MB.')
      return
    }
    setFile(f)
  }

  async function onUpload(e) {
    e.preventDefault()
    if (!file) {
      setError('Choose a file first.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const r = await fetch(`${API}/partners/${partnerId}/documents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          document_type: docType,
          document_name: file.name,
          file_path: `/uploads/${partnerId}/${file.name}`,
          file_size_bytes: file.size,
          mime_type: file.type,
        }),
      })
      const data = await r.json().catch(() => ({}))
      if (!r.ok) {
        throw new Error(data.detail || `HTTP ${r.status}`)
      }
      onUploaded?.(data)
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fp-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="upload-modal-title">
      <form className="fp-modal" onSubmit={onUpload}>
        <h3 id="upload-modal-title" className="fp-modal__title">Upload document</h3>
        <p className="fp-modal__subtitle">PDF, JPG, or PNG — max 10 MB.</p>

        <div className="fp-field fp-field--filled">
          <select
            id="upload-doc-type"
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
          >
            {DOCUMENT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <label htmlFor="upload-doc-type">Document type</label>
        </div>

        <label style={{ display: 'block', marginTop: 8, fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>
          File
          <input
            type="file"
            accept={ACCEPT_TYPES}
            onChange={onFileChange}
            style={{ display: 'block', marginTop: 6, fontSize: 'var(--fp-fs-sm)' }}
          />
        </label>

        {error && (
          <div className="fp-alert fp-alert--danger" style={{ marginTop: 12 }}>{error}</div>
        )}

        <div className="fp-modal__actions">
          <button type="button" onClick={onClose} disabled={busy} className="fp-btn fp-btn--ghost">
            Cancel
          </button>
          <button type="submit" disabled={busy || !file} className="fp-btn fp-btn--primary">
            {busy ? 'Uploading…' : 'Upload'}
          </button>
        </div>
      </form>
    </div>
  )
}

function RejectModal({ doc, onClose, onConfirm, saving }) {
  const [notes, setNotes] = useState('')
  return (
    <div className="fp-modal-overlay" role="dialog" aria-modal="true" aria-labelledby="reject-modal-title">
      <div className="fp-modal">
        <h3 id="reject-modal-title" className="fp-modal__title">Reject document</h3>
        <p className="fp-modal__subtitle">{doc.document_name}</p>
        <div className="fp-field fp-field--filled">
          <textarea
            id="reject-notes"
            rows={4}
            placeholder=" "
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
          <label htmlFor="reject-notes">Reason (visible to the partner)</label>
        </div>
        <div className="fp-modal__actions">
          <button type="button" onClick={onClose} disabled={saving} className="fp-btn fp-btn--ghost">
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm(notes)}
            disabled={saving || !notes.trim()}
            className="fp-btn fp-btn--solid-danger"
          >
            {saving ? 'Rejecting…' : 'Reject'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function PartnerDocuments() {

  const [exporting, setExporting] = useState(false)
  async function exportCSV() {
    setExporting(true)
    try {
      const token = localStorage.getItem('token')
      // The partner org id is needed. Read from current user's JWT or props.
      let orgId = null
      try {
        const t = token
        const payload = JSON.parse(atob(t.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
        orgId = payload.partner_org_id
      } catch {}
      if (!orgId) {
        // Fallback: try to read from URL `:id` param via window.location.pathname
        const m = window.location.pathname.match(/\/partners\/([0-9a-f-]+)\//i)
        if (m) orgId = m[1]
      }
      if (!orgId) throw new Error('No partner org id available')
      const r = await fetch(`${API}/partners/${orgId}/documents?export=csv`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'documents_export.csv'
      document.body.appendChild(a); a.click(); document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('CSV export error:', e)
    } finally {
      setExporting(false)
    }
  }
  const params = useParams()
  const ctx = useOutletContext() || {}
  const token = ctx.token || localStorage.getItem('token')
  const payload = token ? decodeJwt(token) : null
  const internalMode = !!params.id
  const partnerOrgId = internalMode ? params.id : payload?.partner_org_id
  const isInternal = INTERNAL_ROLES.has(payload?.role)

  const [docs, setDocs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [actionDoc, setActionDoc] = useState(null)
  const [actionSaving, setActionSaving] = useState(false)
  const [sort, setSort] = useState({ field: 'created_at', dir: 'desc' })
  const [typeFilter, setTypeFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  function toggleSort(field) {
    setSort((s) => s.field === field
      ? { field, dir: s.dir === 'asc' ? 'desc' : 'asc' }
      : { field, dir: 'asc' })
  }

  const reload = useMemo(() => {
    return () => {
      if (!partnerOrgId || !token) return
      setLoading(true)
      setError(null)
      const qs = new URLSearchParams({ sort_by: sort.field, sort_dir: sort.dir })
      fetch(`${API}/partners/${partnerOrgId}/documents?${qs.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((r) => {
          if (!r.ok) throw new Error(`HTTP ${r.status}`)
          return r.json()
        })
        .then((data) => setDocs(Array.isArray(data) ? data : data.items || []))
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false))
    }
  }, [partnerOrgId, token, sort])

  useEffect(() => {
    reload()
  }, [reload])

  async function approve(doc) {
    setActionSaving(true)
    try {
      const r = await fetch(`${API}/partners/${partnerOrgId}/documents/${doc.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status: 'approved' }),
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

  async function reject(doc, notes) {
    setActionSaving(true)
    try {
      const r = await fetch(`${API}/partners/${partnerOrgId}/documents/${doc.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status: 'rejected', review_notes: notes }),
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${r.status}`)
      }
      setActionDoc(null)
      reload()
    } catch (e) {
      setError(e.message)
    } finally {
      setActionSaving(false)
    }
  }

  const content = (
    <>
      <div className="fp-page-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <h1 className="fp-page-title">Documents</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button type="button" onClick={exportCSV} disabled={exporting} style={{ fontSize: '0.75rem', padding: '4px 10px', border: '1px solid #CBD5E0', borderRadius: 4, backgroundColor: 'white', color: '#718096', cursor: 'pointer', fontWeight: 400 }}>{exporting ? 'Exporting...' : 'Export CSV'}</button>
          {!isInternal && (
            <button type="button" className="fp-btn fp-btn--primary" onClick={() => setUploadOpen(true)}>
              Upload document
            </button>
          )}
        </div>
      </div>

      {/* Filter bar — single fp-card horizontal row per AD-26. Client-side
          filter on the already-loaded set; documents pages are small enough
          that this avoids a backend query-param round-trip. */}
      <section className="fp-card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}
            style={{ padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }}>
            <option value="">All document types</option>
            {DOCUMENT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
            style={{ padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }}>
            <option value="">All statuses</option>
            <option value="pending_review">Pending review</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="expired">Expired</option>
          </select>
        </div>
      </section>

      {error && (
        <div className="fp-alert fp-alert--danger">{error}</div>
      )}

      {loading && <div className="fp-card" style={{ color: 'var(--fp-text-secondary)' }}>Loading documents…</div>}

      {!loading && docs.length === 0 && (
        <div className="fp-card" style={{ color: 'var(--fp-text-secondary)', textAlign: 'center', padding: 40 }}>
          <div style={{ fontSize: 36, marginBottom: 8 }}>📄</div>
          <div style={{ fontSize: 'var(--fp-fs-base)' }}>No documents yet.</div>
          {!isInternal && (
            <div style={{ marginTop: 12 }}>
              <button type="button" className="fp-btn fp-btn--secondary" onClick={() => setUploadOpen(true)}>
                Upload your first document
              </button>
            </div>
          )}
        </div>
      )}

      {!loading && docs.length > 0 && (() => {
        const visibleDocs = docs.filter((d) => {
          if (typeFilter && d.document_type !== typeFilter) return false
          if (statusFilter && d.status !== statusFilter) return false
          return true
        })
        if (visibleDocs.length === 0) {
          return (
            <div className="fp-card" style={{ color: 'var(--fp-text-secondary)', textAlign: 'center', padding: 32 }}>
              No documents match the current filters.
            </div>
          )
        }
        return (
        <table className="fp-table">
          <thead>
            <tr>
              <SortableTh field="document_type" sort={sort} onSort={toggleSort}>Type</SortableTh>
              <th>Name</th>
              <SortableTh field="status" sort={sort} onSort={toggleSort}>Status</SortableTh>
              <SortableTh field="created_at" sort={sort} onSort={toggleSort}>Uploaded</SortableTh>
              <th>Expires</th>
              {isInternal && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {visibleDocs.map((d) => (
              <tr key={d.id}>
                <td>{d.document_type}</td>
                <td>{d.document_name}</td>
                <td>
                  <StatusBadge status={d.status} />
                  {d.review_notes && d.status === 'rejected' && (
                    <div style={{ fontSize: 'var(--fp-fs-xs)', color: 'var(--fp-danger)', marginTop: 4, maxWidth: 320 }}>
                      {d.review_notes}
                    </div>
                  )}
                </td>
                <td>{d.uploaded_at ? new Date(d.uploaded_at).toLocaleDateString() : '—'}</td>
                <td>{d.expiry_date || '—'}</td>
                {isInternal && (
                  <td>
                    {d.status === 'pending_review' ? (
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button
                          onClick={() => approve(d)}
                          disabled={actionSaving}
                          className="fp-btn fp-btn--success fp-btn--sm"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => setActionDoc(d)}
                          disabled={actionSaving}
                          className="fp-btn fp-btn--danger fp-btn--sm"
                        >
                          Reject
                        </button>
                      </div>
                    ) : (
                      <span style={{ color: 'var(--fp-text-muted)', fontSize: 'var(--fp-fs-sm)' }}>—</span>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        )
      })()}

      {uploadOpen && (
        <UploadModal
          partnerId={partnerOrgId}
          token={token}
          onClose={() => setUploadOpen(false)}
          onUploaded={() => reload()}
        />
      )}
      {actionDoc && (
        <RejectModal
          doc={actionDoc}
          saving={actionSaving}
          onClose={() => setActionDoc(null)}
          onConfirm={(notes) => reject(actionDoc, notes)}
        />
      )}
    </>
  )

  if (internalMode) {
    return <div className="fp-page">{content}</div>
  }
  return content
}
