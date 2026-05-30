import { Fragment, useEffect, useMemo, useState } from 'react'
import { useOutletContext, useParams } from 'react-router-dom'
import { SortableTh } from '../components/SortableTh.jsx'
import DocumentTypeSelect from '../components/DocumentTypeSelect.jsx'
import { trackPreviewUrl } from '../utils/session.js'

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

// AD-37 (FPRM-391): the file-type allowlist is removed -- any file type is
// accepted; uploads are gated on size only.
const MAX_FILE_BYTES = 25 * 1024 * 1024  // 25 MB

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
    // AD-37: no type restriction -- size is the only gate.
    if (f.size > MAX_FILE_BYTES) {
      setError('File is larger than 25 MB.')
      return
    }
    setFile(f)
  }

  async function readFileAsBase64(f) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => {
        const result = String(reader.result || '')
        const comma = result.indexOf(',')
        resolve(comma >= 0 ? result.slice(comma + 1) : result)
      }
      reader.onerror = () => reject(new Error('Failed to read file'))
      reader.readAsDataURL(f)
    })
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
      // Sprint 21 / AD-33 -- upload binary content as base64 into the
      // centralised partner_documents store.
      const fileData = await readFileAsBase64(file)
      const r = await fetch(`${API}/partners/${partnerId}/documents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          document_type: docType,
          document_name: file.name,
          file_data: fileData,
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
        <p className="fp-modal__subtitle">Any file type — max 25 MB.</p>

        <div className="fp-field fp-field--filled">
          {/* FPRM-418 / AD-40: shared vocabulary dropdown -- identical list on
              every upload surface. */}
          <DocumentTypeSelect
            id="upload-doc-type"
            token={token}
            value={docType}
            onChange={setDocType}
          />
          <label htmlFor="upload-doc-type">Document type</label>
        </div>

        <label style={{ display: 'block', marginTop: 8, fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>
          File
          <input
            type="file"
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

function NewVersionModal({ partnerId, docId, docName, token, onClose, onUploaded }) {
  const [file, setFile] = useState(null)
  const [notes, setNotes] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  function onFileChange(e) {
    const f = e.target.files?.[0] || null
    setError(null)
    if (!f) { setFile(null); return }
    if (f.size > MAX_FILE_BYTES) { setError('File is larger than 25 MB.'); return }
    setFile(f)
  }

  async function readFileAsBase64(f) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => {
        const result = String(reader.result || '')
        const comma = result.indexOf(',')
        resolve(comma >= 0 ? result.slice(comma + 1) : result)
      }
      reader.onerror = () => reject(new Error('Failed to read file'))
      reader.readAsDataURL(f)
    })
  }

  async function onSubmit(e) {
    e.preventDefault()
    if (!file) { setError('Choose a file first.'); return }
    setBusy(true); setError(null)
    try {
      const b64 = await readFileAsBase64(file)
      const r = await fetch(`${API}/partners/${partnerId}/documents/${docId}/versions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          file_data: b64,
          file_size_bytes: file.size,
          mime_type: file.type,
          notes: notes || null,
        }),
      })
      const data = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`)
      onUploaded?.(data)
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fp-modal-overlay" role="dialog" aria-modal="true">
      <form className="fp-modal" onSubmit={onSubmit}>
        <h3 className="fp-modal__title">Upload new version</h3>
        <p className="fp-modal__subtitle">{docName}</p>
        <label style={{ display: 'block', marginTop: 8, fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>
          File <span style={{ color: 'var(--fp-text-secondary)' }}>(any type, max 25 MB)</span>
          <input type="file" onChange={onFileChange}
            style={{ display: 'block', marginTop: 6, fontSize: 'var(--fp-fs-sm)' }} />
        </label>
        <div className="fp-field fp-field--filled" style={{ marginTop: 8 }}>
          <textarea id="version-notes" rows={2} placeholder=" "
            value={notes} onChange={(e) => setNotes(e.target.value)} />
          <label htmlFor="version-notes">Notes (optional)</label>
        </div>
        {error && <div className="fp-alert fp-alert--danger" style={{ marginTop: 12 }}>{error}</div>}
        <div className="fp-modal__actions">
          <button type="button" onClick={onClose} disabled={busy} className="fp-btn fp-btn--ghost">Cancel</button>
          <button type="submit" disabled={busy || !file} className="fp-btn fp-btn--primary">
            {busy ? 'Uploading…' : 'Upload Version'}
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
  const [search, setSearch] = useState('')
  // Sprint 22 -- expanded doc id (inline version history panel), upload-new-version target
  const [expandedDocId, setExpandedDocId] = useState(null)
  const [versionsByDoc, setVersionsByDoc] = useState({})
  const [versionTargetDoc, setVersionTargetDoc] = useState(null)

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

  async function downloadDoc(doc) {
    // Sprint 21 / AD-33 -- fetch + Blob + URL.createObjectURL per AD-20.
    try {
      const r = await fetch(`${API}/partners/${partnerOrgId}/documents/${doc.id}/download`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${r.status}`)
      }
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = doc.document_name || 'document'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e.message)
    }
  }

  // Sprint 22 -- inline preview opens the /preview endpoint in a new tab.
  // PREVIEWABLE_MIME maps client-side decision logic for the Preview button.
  const PREVIEWABLE_MIME = new Set([
    'application/pdf', 'image/png', 'image/jpeg', 'image/jpg',
    'image/gif', 'image/webp',
  ])

  function previewDoc(doc) {
    if (!doc.id || !partnerOrgId || !token) return
    // The endpoint requires bearer auth; fetch + blob URL so we can open
    // it in a new tab without leaking the JWT into the URL.
    fetch(`${API}/partners/${partnerOrgId}/documents/${doc.id}/preview`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        if (!r.ok) {
          const body = await r.json().catch(() => ({}))
          throw new Error(body.detail || `HTTP ${r.status}`)
        }
        const blob = await r.blob()
        // FPRM-420: track the preview blob URL so logout revokes it immediately
        // (otherwise it survives the 30s timer into the next org's session).
        const url = trackPreviewUrl(URL.createObjectURL(blob))
        window.open(url, '_blank', 'noopener,noreferrer')
        // Revoke after a short delay so the new tab has time to read.
        setTimeout(() => URL.revokeObjectURL(url), 30_000)
      })
      .catch((e) => setError(e.message || String(e)))
  }

  // Sprint 22 -- versioning: load/expand the version history panel
  async function toggleVersions(docId) {
    if (expandedDocId === docId) {
      setExpandedDocId(null)
      return
    }
    setExpandedDocId(docId)
    if (versionsByDoc[docId]) return  // cached
    try {
      const r = await fetch(
        `${API}/partners/${partnerOrgId}/documents/${docId}/versions`,
        { headers: { Authorization: `Bearer ${token}` } },
      )
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const rows = await r.json()
      setVersionsByDoc((prev) => ({ ...prev, [docId]: rows }))
    } catch (e) {
      setError(e.message)
    }
  }

  async function downloadVersion(docId, version) {
    try {
      const r = await fetch(
        `${API}/partners/${partnerOrgId}/documents/${docId}/versions/${version.id}/download`,
        { headers: { Authorization: `Bearer ${token}` } },
      )
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `v${version.version_number}-${docs.find((d) => d.id === docId)?.document_name || 'document'}`
      document.body.appendChild(a); a.click(); document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e.message)
    }
  }

  async function revertToVersion(docId, version) {
    if (!confirm(`Revert to v${version.version_number}? The current version will be replaced.`)) return
    try {
      const r = await fetch(
        `${API}/partners/${partnerOrgId}/documents/${docId}/versions/${version.id}/revert`,
        { method: 'POST', headers: { Authorization: `Bearer ${token}` } },
      )
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${r.status}`)
      }
      // Reload docs + the version list for this doc
      reload()
      setVersionsByDoc((prev) => ({ ...prev, [docId]: undefined }))
      if (expandedDocId === docId) toggleVersions(docId)
    } catch (e) {
      setError(e.message)
    }
  }

  async function deleteOwnDoc(doc) {
    if (!confirm(`Delete ${doc.document_name}? This cannot be undone.`)) return
    try {
      const r = await fetch(
        `${API}/partners/${partnerOrgId}/documents/${doc.id}`,
        { method: 'DELETE', headers: { Authorization: `Bearer ${token}` } },
      )
      if (r.status === 409) {
        const body = await r.json().catch(() => ({}))
        alert(body.detail || 'This document is attached to a quote. Remove it from the quote first before deleting.')
        return
      }
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${r.status}`)
      }
      reload()
    } catch (e) {
      setError(e.message)
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
          {/* FPRM-418 / AD-40: same shared vocabulary as the upload dropdown. */}
          <DocumentTypeSelect
            token={token}
            value={typeFilter}
            onChange={setTypeFilter}
            placeholder="All document types"
            style={{ padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }}
          />
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
            style={{ padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }}>
            <option value="">All statuses</option>
            <option value="pending_review">Pending review</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="expired">Expired</option>
          </select>
          <input type="search" placeholder="Search by document name or type…"
            value={search} onChange={(e) => setSearch(e.target.value)}
            style={{ flex: 1, minWidth: 200, padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }} />
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
        const q = search.trim().toLowerCase()
        const visibleDocs = docs.filter((d) => {
          if (typeFilter && d.document_type !== typeFilter) return false
          if (statusFilter && d.status !== statusFilter) return false
          if (q && !(
            (d.document_name || '').toLowerCase().includes(q) ||
            (d.document_type || '').toLowerCase().includes(q)
          )) return false
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
              <SortableTh field="document_name" sort={sort} onSort={toggleSort}>Name</SortableTh>
              <th>Version</th>
              <SortableTh field="status" sort={sort} onSort={toggleSort}>Status</SortableTh>
              <SortableTh field="created_at" sort={sort} onSort={toggleSort}>Uploaded</SortableTh>
              <th>Uploaded By</th>
              <SortableTh field="expiry_date" sort={sort} onSort={toggleSort}>Expires</SortableTh>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {visibleDocs.map((d) => {
              const vcur = d.current_version_number ?? 1
              const vcount = d.version_count ?? 1
              const isExpanded = expandedDocId === d.id
              const versions = versionsByDoc[d.id]
              return (
              <Fragment key={d.id}>
              <tr>
                <td>{d.document_type}</td>
                <td>{d.document_name}</td>
                <td>
                  {vcount > 1 ? (
                    <button
                      type="button"
                      onClick={() => toggleVersions(d.id)}
                      style={{
                        background: 'transparent', border: '1px solid #CBD5E0',
                        borderRadius: 12, padding: '2px 8px', fontSize: 12,
                        cursor: 'pointer', color: '#1A6EBB', fontWeight: 600,
                      }}
                      title={`v${vcur} of ${vcount} -- click to view history`}
                    >
                      v{vcur} of {vcount} {isExpanded ? '▴' : '▾'}
                    </button>
                  ) : (
                    <span style={{ fontSize: 12, color: '#64748B' }}>v{vcur}</span>
                  )}
                </td>
                <td>
                  <StatusBadge status={d.status} />
                  {d.review_notes && d.status === 'rejected' && (
                    <div style={{ fontSize: 'var(--fp-fs-xs)', color: 'var(--fp-danger)', marginTop: 4, maxWidth: 320 }}>
                      {d.review_notes}
                    </div>
                  )}
                </td>
                <td>{d.uploaded_at ? new Date(d.uploaded_at).toLocaleDateString() : '—'}</td>
                <td style={{ color: '#64748B' }}>{d.uploaded_by_name ?? '—'}</td>
                <td>{d.expiry_date || '—'}</td>
                <td style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {PREVIEWABLE_MIME.has(d.mime_type) && (
                    <button
                      type="button"
                      onClick={() => previewDoc(d)}
                      className="fp-btn fp-btn--ghost fp-btn--sm"
                      title="Open in new tab"
                    >
                      Preview
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => downloadDoc(d)}
                    className="fp-btn fp-btn--ghost fp-btn--sm"
                  >
                    Download
                  </button>
                  {!isInternal && (
                    <button
                      type="button"
                      onClick={() => setVersionTargetDoc(d)}
                      className="fp-btn fp-btn--ghost fp-btn--sm"
                      title="Upload a new version of this document"
                    >
                      + Version
                    </button>
                  )}
                  {!isInternal && payload?.role === 'partner_admin' && (
                    <button
                      type="button"
                      onClick={() => deleteOwnDoc(d)}
                      className="fp-btn fp-btn--danger fp-btn--sm"
                    >
                      Delete
                    </button>
                  )}
                  {isInternal && d.status === 'pending_review' && (
                    <>
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
                    </>
                  )}
                </td>
              </tr>
              {isExpanded && (
                <tr key={`${d.id}-history`}>
                  <td colSpan={8} style={{ background: '#F8FAFC', padding: 12 }}>
                    <div style={{ fontWeight: 600, marginBottom: 8, color: '#1E293B' }}>
                      Version history
                    </div>
                    {!versions && <div style={{ color: '#64748B', fontSize: 13 }}>Loading…</div>}
                    {versions && versions.length === 0 && (
                      <div style={{ color: '#94A3B8', fontSize: 13 }}>No version history available.</div>
                    )}
                    {versions && versions.length > 0 && (
                      <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
                        <thead>
                          <tr style={{ textAlign: 'left', background: '#F1F5F9' }}>
                            <th style={{ padding: 6 }}>Version</th>
                            <th style={{ padding: 6 }}>Uploaded At</th>
                            <th style={{ padding: 6 }}>Uploaded By</th>
                            <th style={{ padding: 6 }}>Size</th>
                            <th style={{ padding: 6 }}>Notes</th>
                            <th style={{ padding: 6, textAlign: 'right' }}>Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {versions.map((v) => (
                            <tr key={v.id}
                              style={{
                                borderBottom: '1px solid #E2E8F0',
                                borderLeft: v.is_current ? '3px solid #1B8743' : '3px solid transparent',
                                background: v.is_current ? '#F0FDF4' : 'transparent',
                              }}>
                              <td style={{ padding: 6 }}>
                                v{v.version_number}
                                {v.is_current && (
                                  <span style={{ marginLeft: 6, fontSize: 11, color: '#1B8743', fontWeight: 600 }}>Current</span>
                                )}
                              </td>
                              <td style={{ padding: 6, color: '#64748B' }}>
                                {v.uploaded_at ? new Date(v.uploaded_at).toLocaleString() : '—'}
                              </td>
                              <td style={{ padding: 6, color: '#64748B' }}>{v.uploaded_by_name || '—'}</td>
                              <td style={{ padding: 6, color: '#64748B' }}>
                                {v.file_size_bytes != null ? `${(v.file_size_bytes / 1024).toFixed(1)} KB` : '—'}
                              </td>
                              <td style={{ padding: 6, color: '#64748B' }}>{v.notes || '—'}</td>
                              <td style={{ padding: 6, textAlign: 'right' }}>
                                <button
                                  type="button"
                                  onClick={() => downloadVersion(d.id, v)}
                                  className="fp-btn fp-btn--ghost fp-btn--sm"
                                  style={{ marginRight: 6 }}
                                >
                                  Download
                                </button>
                                {/* AD-36 (FPRM-390): revert available to internal roles
                                    OR partner_admin (own org enforced server-side). */}
                                {(isInternal || payload?.role === 'partner_admin') && !v.is_current && (
                                  <button
                                    type="button"
                                    onClick={() => revertToVersion(d.id, v)}
                                    className="fp-btn fp-btn--secondary fp-btn--sm"
                                  >
                                    Revert
                                  </button>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </td>
                </tr>
              )}
              </Fragment>
              )
            })}
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
      {versionTargetDoc && (
        <NewVersionModal
          partnerId={partnerOrgId}
          docId={versionTargetDoc.id}
          docName={versionTargetDoc.document_name}
          token={token}
          onClose={() => setVersionTargetDoc(null)}
          onUploaded={() => { reload(); setVersionsByDoc({}) }}
        />
      )}
    </>
  )

  if (internalMode) {
    // Sprint 21 hotfix FPRM-356: match the full-width layout used by every
    // other internal page (DealQueue, DealList, InternalQuotes, etc.) --
    // a plain <div> that fills the InternalLayout content slot. The earlier
    // ``fp-page`` wrapper bunched content into a narrow column.
    return <div>{content}</div>
  }
  return content
}
