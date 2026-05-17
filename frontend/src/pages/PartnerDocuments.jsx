import { useEffect, useMemo, useState } from 'react'
import { useOutletContext, useParams } from 'react-router-dom'

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

const STATUS_COLORS = {
  approved: '#4caf50',
  pending_review: '#ffc107',
  rejected: '#f44336',
  expired: '#9e9e9e',
}

const STATUS_LABELS = {
  approved: 'Approved',
  pending_review: 'Pending review',
  rejected: 'Rejected',
  expired: 'Expired',
}

function StatusBadge({ status }) {
  return (
    <span
      style={{
        background: STATUS_COLORS[status] || '#9e9e9e',
        color: 'white',
        padding: '2px 10px',
        borderRadius: 12,
        fontSize: 12,
        fontWeight: 500,
      }}
    >
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

function UploadPanel({ partnerId, token, onUploaded }) {
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
          file_path: `/uploads/${partnerId}/${file.name}`,  // metadata-only — actual storage pending
          file_size_bytes: file.size,
          mime_type: file.type,
        }),
      })
      const data = await r.json().catch(() => ({}))
      if (!r.ok) {
        throw new Error(data.detail || `HTTP ${r.status}`)
      }
      setFile(null)
      setDocType('fiscal_id')
      onUploaded?.(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form
      onSubmit={onUpload}
      style={{
        background: 'white', border: '1px solid #e0e0e0', borderRadius: 8,
        padding: 16, marginBottom: 24,
        display: 'flex', alignItems: 'flex-end', gap: 12, flexWrap: 'wrap',
      }}
    >
      <label style={{ display: 'flex', flexDirection: 'column', fontSize: 13, color: '#333', minWidth: 220 }}>
        Document type
        <select
          value={docType}
          onChange={(e) => setDocType(e.target.value)}
          style={{ padding: 8, marginTop: 4, fontSize: 14, border: '1px solid #ccc', borderRadius: 4 }}
        >
          {DOCUMENT_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
      </label>
      <label style={{ display: 'flex', flexDirection: 'column', fontSize: 13, color: '#333', flex: 1, minWidth: 220 }}>
        File (PDF, JPG, PNG; max 10 MB)
        <input
          type="file"
          accept={ACCEPT_TYPES}
          onChange={onFileChange}
          style={{ padding: 6, marginTop: 4, fontSize: 13 }}
        />
      </label>
      <button
        type="submit"
        disabled={busy || !file}
        style={{
          padding: '10px 16px', background: busy || !file ? '#90caf9' : '#1976d2',
          color: 'white', border: 'none', borderRadius: 4,
          cursor: busy || !file ? 'not-allowed' : 'pointer', fontSize: 14,
        }}
      >
        {busy ? 'Uploading…' : 'Upload'}
      </button>
      {error && (
        <div style={{ flexBasis: '100%', color: '#c0392b', fontSize: 13 }}>{error}</div>
      )}
    </form>
  )
}

function RejectModal({ doc, onClose, onConfirm, saving }) {
  const [notes, setNotes] = useState('')
  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
      }}
    >
      <div style={{ background: 'white', borderRadius: 8, padding: 24, maxWidth: 480, width: '90%' }}>
        <h3 style={{ marginTop: 0, color: '#102a43' }}>Reject document</h3>
        <p style={{ fontSize: 14, color: '#555', margin: '0 0 12px' }}>
          {doc.document_name}
        </p>
        <label style={{ display: 'block', fontSize: 13, color: '#333', marginBottom: 16 }}>
          Reason (visible to the partner)
          <textarea
            rows={4}
            required
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            style={{ width: '100%', padding: 8, marginTop: 4, fontSize: 14, border: '1px solid #ccc', borderRadius: 4 }}
          />
        </label>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            style={{ padding: '10px 16px', background: 'white', border: '1px solid #ccc', borderRadius: 4, cursor: saving ? 'not-allowed' : 'pointer' }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => onConfirm(notes)}
            disabled={saving || !notes.trim()}
            style={{ padding: '10px 16px', background: saving ? '#ef9a9a' : '#c62828', color: 'white', border: 'none', borderRadius: 4, cursor: saving || !notes.trim() ? 'not-allowed' : 'pointer' }}
          >
            {saving ? 'Rejecting…' : 'Reject'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function PartnerDocuments() {
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
  const [actionDoc, setActionDoc] = useState(null)  // doc being rejected
  const [actionSaving, setActionSaving] = useState(false)

  const reload = useMemo(() => {
    return () => {
      if (!partnerOrgId || !token) return
      setLoading(true)
      setError(null)
      fetch(`${API}/partners/${partnerOrgId}/documents`, {
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
  }, [partnerOrgId, token])

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

  const wrapperStyle = internalMode
    ? { maxWidth: 980, margin: '24px auto', padding: '0 24px', fontFamily: 'system-ui, sans-serif' }
    : {}

  return (
    <div style={wrapperStyle}>
      <h1 style={{ color: '#102a43', margin: '0 0 16px' }}>Documents</h1>

      {error && (
        <div style={{ background: '#fdecea', color: '#b71c1c', padding: 12, borderRadius: 4, marginBottom: 16, fontSize: 13 }}>
          {error}
        </div>
      )}

      {!isInternal && (
        <UploadPanel
          partnerId={partnerOrgId}
          token={token}
          onUploaded={() => reload()}
        />
      )}

      {loading && <div style={{ color: '#666', fontSize: 13 }}>Loading documents…</div>}

      {!loading && docs.length === 0 && (
        <div
          style={{
            background: 'white', border: '1px solid #e0e0e0',
            borderRadius: 8, padding: 20, color: '#666', fontSize: 14,
          }}
        >
          No documents yet.
        </div>
      )}

      {!loading && docs.length > 0 && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, background: 'white' }}>
          <thead>
            <tr style={{ background: '#f5f5f5', textAlign: 'left' }}>
              <th style={{ padding: 10 }}>Type</th>
              <th style={{ padding: 10 }}>Name</th>
              <th style={{ padding: 10 }}>Status</th>
              <th style={{ padding: 10 }}>Uploaded</th>
              <th style={{ padding: 10 }}>Expires</th>
              {isInternal && <th style={{ padding: 10 }}>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.id} style={{ borderBottom: '1px solid #eee' }}>
                <td style={{ padding: 10 }}>{d.document_type}</td>
                <td style={{ padding: 10 }}>{d.document_name}</td>
                <td style={{ padding: 10 }}>
                  <StatusBadge status={d.status} />
                  {d.review_notes && d.status === 'rejected' && (
                    <div style={{ fontSize: 12, color: '#b71c1c', marginTop: 4, maxWidth: 320 }}>
                      {d.review_notes}
                    </div>
                  )}
                </td>
                <td style={{ padding: 10 }}>
                  {d.uploaded_at ? new Date(d.uploaded_at).toLocaleDateString() : '—'}
                </td>
                <td style={{ padding: 10 }}>{d.expiry_date || '—'}</td>
                {isInternal && (
                  <td style={{ padding: 10 }}>
                    {d.status === 'pending_review' ? (
                      <div style={{ display: 'flex', gap: 8 }}>
                        <button
                          onClick={() => approve(d)}
                          disabled={actionSaving}
                          style={{
                            padding: '6px 12px', background: '#4caf50', color: 'white',
                            border: 'none', borderRadius: 4, cursor: actionSaving ? 'not-allowed' : 'pointer', fontSize: 13,
                          }}
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => setActionDoc(d)}
                          disabled={actionSaving}
                          style={{
                            padding: '6px 12px', background: 'white', color: '#c62828',
                            border: '1px solid #c62828', borderRadius: 4, cursor: actionSaving ? 'not-allowed' : 'pointer', fontSize: 13,
                          }}
                        >
                          Reject
                        </button>
                      </div>
                    ) : (
                      <span style={{ color: '#888', fontSize: 13 }}>—</span>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {actionDoc && (
        <RejectModal
          doc={actionDoc}
          saving={actionSaving}
          onClose={() => setActionDoc(null)}
          onConfirm={(notes) => reject(actionDoc, notes)}
        />
      )}
    </div>
  )
}
