import { useCallback, useEffect, useMemo, useState } from 'react'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const MAX_BYTES = 10 * 1024 * 1024  // AD-39 asset cap

const VISIBILITY_OPTIONS = [
  { value: 'all', label: 'All partners' },
  { value: 'tier:registered', label: 'Tier: Registered' },
  { value: 'tier:silver', label: 'Tier: Silver' },
  { value: 'tier:gold', label: 'Tier: Gold' },
  { value: 'category:master', label: 'Category: Master' },
  { value: 'category:promotor', label: 'Category: Promotor' },
  { value: 'category:reseller', label: 'Category: Reseller' },
]

function decodeJwt(token) {
  try {
    const p = token.split('.')[1]
    return JSON.parse(atob(p.replace(/-/g, '+').replace(/_/g, '/')))
  } catch { return null }
}

function readFileAsBase64(f) {
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

// ---------------- Upload / Edit modal ----------------

function AssetModal({ token, categories, editing, onClose, onSaved, onError }) {
  const isEdit = !!editing
  const [form, setForm] = useState({
    title: editing?.title || '',
    description: editing?.description || '',
    category_id: editing?.category_id || '',
    visibility: editing?.visibility || 'all',
    is_active: editing ? editing.is_active : true,
  })
  const [file, setFile] = useState(null)
  const [err, setErr] = useState(null)
  const [busy, setBusy] = useState(false)

  function onFileChange(e) {
    const f = e.target.files?.[0] || null
    setErr(null)
    if (f && f.size > MAX_BYTES) { setErr('File is larger than 10 MB.'); return }
    setFile(f)
  }

  async function save() {
    setBusy(true); setErr(null)
    try {
      if (isEdit) {
        const r = await fetch(`${API}/internal/assets/${editing.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({
            title: form.title, description: form.description,
            category_id: form.category_id || null, visibility: form.visibility,
            is_active: form.is_active,
          }),
        })
        const d = await r.json().catch(() => ({}))
        if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`)
      } else {
        if (!form.title.trim()) { setErr('Title is required'); setBusy(false); return }
        if (!file) { setErr('Choose a file'); setBusy(false); return }
        const b64 = await readFileAsBase64(file)
        const r = await fetch(`${API}/internal/assets`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({
            title: form.title, description: form.description,
            category_id: form.category_id || null, visibility: form.visibility,
            file_name: file.name, file_type: file.type, file_size_bytes: file.size,
            file_data: b64,
          }),
        })
        const d = await r.json().catch(() => ({}))
        if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`)
      }
      onSaved()
      onClose()
    } catch (e) {
      setErr(e.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fp-modal-overlay" role="dialog" aria-modal="true">
      <div className="fp-modal" style={{ maxWidth: 560, width: '90vw' }}>
        <h3 className="fp-modal__title">{isEdit ? `Edit "${editing.title}"` : 'Upload asset'}</h3>
        <div style={{ display: 'grid', gap: 12 }}>
          <label style={{ fontSize: 13 }}>
            <span style={{ display: 'block', color: '#64748B', marginBottom: 4 }}>Title</span>
            <input type="text" value={form.title} disabled={busy}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              style={{ width: '100%', padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }} />
          </label>
          <label style={{ fontSize: 13 }}>
            <span style={{ display: 'block', color: '#64748B', marginBottom: 4 }}>Description (optional)</span>
            <textarea rows={2} value={form.description} disabled={busy}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              style={{ width: '100%', padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }} />
          </label>
          <label style={{ fontSize: 13 }}>
            <span style={{ display: 'block', color: '#64748B', marginBottom: 4 }}>Category</span>
            <select value={form.category_id} disabled={busy}
              onChange={(e) => setForm({ ...form, category_id: e.target.value })}
              style={{ width: '100%', padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }}>
              <option value="">— none —</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label style={{ fontSize: 13 }}>
            <span style={{ display: 'block', color: '#64748B', marginBottom: 4 }}>Visibility</span>
            <select value={form.visibility} disabled={busy}
              onChange={(e) => setForm({ ...form, visibility: e.target.value })}
              style={{ width: '100%', padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }}>
              {VISIBILITY_OPTIONS.map((v) => <option key={v.value} value={v.value}>{v.label}</option>)}
            </select>
          </label>
          {!isEdit && (
            <label style={{ fontSize: 13 }}>
              <span style={{ display: 'block', color: '#64748B', marginBottom: 4 }}>File (any type, max 10 MB)</span>
              <input type="file" onChange={onFileChange} disabled={busy} />
            </label>
          )}
          {isEdit && (
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
              <input type="checkbox" checked={form.is_active} disabled={busy}
                onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              <span>Active</span>
            </label>
          )}
          {err && <div className="fp-alert fp-alert--danger">{err}</div>}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
            <button type="button" className="fp-btn fp-btn--ghost" onClick={onClose} disabled={busy}>Cancel</button>
            <button type="button" className="fp-btn fp-btn--primary" onClick={save} disabled={busy}>
              {busy ? 'Saving…' : (isEdit ? 'Save' : 'Upload')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ---------------- Download-logs modal ----------------

function LogsModal({ token, asset, onClose }) {
  const [logs, setLogs] = useState(null)
  useEffect(() => {
    fetch(`${API}/internal/assets/${asset.id}/download-logs`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => setLogs(d.items || []))
      .catch(() => setLogs([]))
  }, [token, asset.id])
  return (
    <div className="fp-modal-overlay" role="dialog" aria-modal="true">
      <div className="fp-modal" style={{ maxWidth: 560, width: '90vw' }}>
        <h3 className="fp-modal__title">Downloads — {asset.title}</h3>
        {logs === null ? <div style={{ color: '#64748B' }}>Loading…</div>
          : logs.length === 0 ? <div style={{ color: '#94A3B8' }}>No downloads yet.</div>
          : (
            <table className="fp-table">
              <thead><tr><th>When</th><th>User</th><th>Partner org</th></tr></thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id}>
                    <td>{l.downloaded_at ? new Date(l.downloaded_at).toLocaleString() : '—'}</td>
                    <td style={{ fontSize: 12, color: '#64748B' }}>{l.downloaded_by || '—'}</td>
                    <td style={{ fontSize: 12, color: '#64748B' }}>{l.partner_org_id || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 12 }}>
          <button type="button" className="fp-btn fp-btn--ghost" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}

// ---------------- Category management ----------------

function CategoryManager({ token, role, categories, reloadCategories, onError, onUpdate }) {
  const canDelete = role === 'system_admin'
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)

  async function add() {
    if (!name.trim()) return
    setBusy(true)
    try {
      const r = await fetch(`${API}/internal/asset-categories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ name: name.trim(), display_order: categories.length }),
      })
      const d = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`)
      setName(''); reloadCategories(); onUpdate?.('Category created')
    } catch (e) { onError?.(e.message) } finally { setBusy(false) }
  }

  async function patch(cat, body) {
    try {
      const r = await fetch(`${API}/internal/asset-categories/${cat.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      })
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || `HTTP ${r.status}`) }
      reloadCategories()
    } catch (e) { onError?.(e.message) }
  }

  async function remove(cat) {
    if (!confirm(`Deactivate category "${cat.name}"?`)) return
    try {
      const r = await fetch(`${API}/internal/asset-categories/${cat.id}`, {
        method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || `HTTP ${r.status}`) }
      reloadCategories(); onUpdate?.('Category deactivated')
    } catch (e) { onError?.(e.message) }
  }

  function move(cat, idx, dir) {
    const swap = categories[idx + dir]
    if (!swap) return
    patch(cat, { display_order: swap.display_order })
    patch(swap, { display_order: cat.display_order })
  }

  return (
    <section className="fp-card" style={{ marginTop: 24 }}>
      <h3 className="fp-section-title" style={{ marginTop: 0 }}>Categories</h3>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <input type="text" placeholder="New category name" value={name}
          onChange={(e) => setName(e.target.value)} disabled={busy}
          style={{ flex: 1, padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }} />
        <button type="button" className="fp-btn fp-btn--primary" onClick={add} disabled={busy || !name.trim()}>Add</button>
      </div>
      {categories.length === 0 ? <div style={{ color: '#94A3B8' }}>No categories yet.</div> : (
        <table className="fp-table">
          <thead><tr><th>Order</th><th>Name</th><th>Active</th><th style={{ textAlign: 'right' }}>Actions</th></tr></thead>
          <tbody>
            {categories.map((c, idx) => (
              <tr key={c.id}>
                <td>
                  <button type="button" className="fp-btn fp-btn--ghost fp-btn--sm" disabled={idx === 0}
                    onClick={() => move(c, idx, -1)}>↑</button>
                  <button type="button" className="fp-btn fp-btn--ghost fp-btn--sm" disabled={idx === categories.length - 1}
                    onClick={() => move(c, idx, 1)}>↓</button>
                </td>
                <td><strong>{c.name}</strong></td>
                <td>{c.is_active ? 'Yes' : 'No'}</td>
                <td style={{ textAlign: 'right' }}>
                  <button type="button" className="fp-btn fp-btn--ghost fp-btn--sm"
                    onClick={() => { const n = prompt('Rename category', c.name); if (n && n.trim()) patch(c, { name: n.trim() }) }}>
                    Rename
                  </button>
                  {canDelete && c.is_active && (
                    <button type="button" className="fp-btn fp-btn--danger fp-btn--sm" onClick={() => remove(c)}>
                      Deactivate
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}

// ---------------- Page ----------------

export default function InternalAssets() {
  const token = localStorage.getItem('token')
  const role = decodeJwt(token)?.role
  const canWrite = role === 'system_admin' || role === 'channel_ops_admin'
  const [assets, setAssets] = useState([])
  const [categories, setCategories] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [toast, setToast] = useState(null)
  const [categoryId, setCategoryId] = useState('')
  const [activeFilter, setActiveFilter] = useState('')
  const [search, setSearch] = useState('')
  const [uploadOpen, setUploadOpen] = useState(false)
  const [editAsset, setEditAsset] = useState(null)
  const [logsAsset, setLogsAsset] = useState(null)

  const reloadCategories = useCallback(() => {
    fetch(`${API}/internal/asset-categories`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => setCategories(d.items || []))
      .catch(() => {})
  }, [token])

  const reload = useMemo(() => () => {
    setLoading(true); setError(null)
    const qs = new URLSearchParams()
    if (categoryId) qs.set('category_id', categoryId)
    if (activeFilter) qs.set('is_active', activeFilter)
    if (search.trim()) qs.set('search', search.trim())
    fetch(`${API}/internal/assets?${qs.toString()}`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then((d) => setAssets(d.items || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [token, categoryId, activeFilter, search])

  useEffect(() => { reloadCategories() }, [reloadCategories])
  useEffect(() => { reload() }, [reload])

  function showToast(m) { setToast(m); setTimeout(() => setToast(null), 2500) }

  async function toggleActive(a) {
    try {
      const r = await fetch(`${API}/internal/assets/${a.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ is_active: !a.is_active }),
      })
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.detail || `HTTP ${r.status}`) }
      reload()
    } catch (e) { setError(e.message) }
  }

  function fmtSize(b) { return b == null ? '—' : `${(b / 1024).toFixed(1)} KB` }

  return (
    <div>
      <div className="fp-page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
        <h1 className="fp-page-title">Assets</h1>
        {canWrite && (
          <button type="button" className="fp-btn fp-btn--primary" onClick={() => setUploadOpen(true)}>Upload asset</button>
        )}
      </div>

      <section className="fp-card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}
            style={{ padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }}>
            <option value="">All categories</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select value={activeFilter} onChange={(e) => setActiveFilter(e.target.value)}
            style={{ padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }}>
            <option value="">All statuses</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
          <input type="search" placeholder="Search by title…" value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ flex: 1, minWidth: 200, padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }} />
        </div>
      </section>

      {error && <div className="fp-alert fp-alert--danger">{error}</div>}
      {loading ? <div className="fp-card" style={{ color: '#64748B' }}>Loading assets…</div>
        : assets.length === 0 ? <div className="fp-card" style={{ textAlign: 'center', padding: 32, color: '#94A3B8' }}>No assets yet.</div>
        : (
          <table className="fp-table">
            <thead>
              <tr>
                <th>Title</th><th>Category</th><th>Type</th><th>Size</th>
                <th>Visibility</th><th>Downloads</th><th>Active</th><th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((a) => (
                <tr key={a.id} style={{ opacity: a.is_active ? 1 : 0.55 }}>
                  <td><strong>{a.title}</strong></td>
                  <td>{a.category_name || '—'}</td>
                  <td style={{ fontSize: 12, color: '#64748B' }}>{a.file_type || '—'}</td>
                  <td style={{ fontSize: 12, color: '#64748B' }}>{fmtSize(a.file_size_bytes)}</td>
                  <td style={{ fontSize: 12, color: '#64748B' }}>{a.visibility}</td>
                  <td>
                    <button type="button" className="fp-btn fp-btn--ghost fp-btn--sm" onClick={() => setLogsAsset(a)}
                      title="View download log">{a.download_count} ⓘ</button>
                  </td>
                  <td>{a.is_active ? 'Yes' : 'No'}</td>
                  <td style={{ textAlign: 'right' }}>
                    {canWrite && (
                      <>
                        <button type="button" className="fp-btn fp-btn--ghost fp-btn--sm" onClick={() => setEditAsset(a)}>Edit</button>
                        <button type="button" className="fp-btn fp-btn--ghost fp-btn--sm" onClick={() => toggleActive(a)}>
                          {a.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

      {canWrite && (
        <CategoryManager token={token} role={role} categories={categories}
          reloadCategories={reloadCategories} onError={setError} onUpdate={showToast} />
      )}

      {uploadOpen && (
        <AssetModal token={token} categories={categories} editing={null}
          onClose={() => setUploadOpen(false)} onSaved={() => { reload(); showToast('Asset uploaded') }} onError={setError} />
      )}
      {editAsset && (
        <AssetModal token={token} categories={categories} editing={editAsset}
          onClose={() => setEditAsset(null)} onSaved={() => { reload(); showToast('Asset updated') }} onError={setError} />
      )}
      {logsAsset && <LogsModal token={token} asset={logsAsset} onClose={() => setLogsAsset(null)} />}

      {toast && (
        <div style={{ position: 'fixed', bottom: 20, right: 20, background: '#1B8743', color: 'white',
          padding: '10px 16px', borderRadius: 6, fontSize: 14, boxShadow: '0 2px 8px rgba(0,0,0,0.2)' }}>{toast}</div>
      )}
    </div>
  )
}
