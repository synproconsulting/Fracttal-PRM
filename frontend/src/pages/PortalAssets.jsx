import { useEffect, useMemo, useState } from 'react'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const PAGE_SIZE = 20

function fileTypeIcon(fileType, fileName) {
  const t = (fileType || '').toLowerCase()
  const n = (fileName || '').toLowerCase()
  if (t.includes('pdf') || n.endsWith('.pdf')) return '📕'
  if (t.includes('image') || /\.(png|jpe?g|gif|webp|svg)$/.test(n)) return '🖼️'
  if (t.includes('zip') || /\.(zip|rar|7z)$/.test(n)) return '🗜️'
  if (/\.(ppt|pptx)$/.test(n) || t.includes('presentation')) return '📊'
  if (/\.(xls|xlsx|csv)$/.test(n) || t.includes('spreadsheet')) return '📈'
  if (/\.(doc|docx)$/.test(n) || t.includes('word')) return '📝'
  if (t.includes('video') || /\.(mp4|mov|avi|webm)$/.test(n)) return '🎬'
  return '📄'
}

export default function PortalAssets() {
  const token = localStorage.getItem('token')
  const [assets, setAssets] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [categoryId, setCategoryId] = useState('')
  const [search, setSearch] = useState('')
  const [categories, setCategories] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Build the category filter options from a broad fetch (categories aren't
  // exposed to partners via a dedicated endpoint; derive from the assets).
  useEffect(() => {
    if (!token) return
    fetch(`${API}/assets?page=1&page_size=100`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : { items: [] }))
      .then((data) => {
        const seen = new Map()
        for (const a of data.items || []) {
          if (a.category_id && !seen.has(a.category_id)) {
            seen.set(a.category_id, a.category_name || a.category_id)
          }
        }
        setCategories(Array.from(seen, ([id, name]) => ({ id, name })))
      })
      .catch(() => {})
  }, [token])

  const reload = useMemo(() => () => {
    if (!token) return
    setLoading(true); setError(null)
    const qs = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) })
    if (categoryId) qs.set('category_id', categoryId)
    if (search.trim()) qs.set('search', search.trim())
    fetch(`${API}/assets?${qs.toString()}`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then((data) => { setAssets(data.items || []); setTotal(data.total || 0) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [token, page, categoryId, search])

  useEffect(() => { reload() }, [reload])

  async function download(asset) {
    try {
      const r = await fetch(`${API}/assets/${asset.id}/download`, {
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
      a.download = asset.file_name || asset.title || 'asset'
      document.body.appendChild(a); a.click(); document.body.removeChild(a)
      URL.revokeObjectURL(url)
      reload()  // refresh download counts
    } catch (e) {
      setError(e.message)
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <>
      <div className="fp-page-header" style={{ marginBottom: 16 }}>
        <h1 className="fp-page-title">Resources</h1>
        <p style={{ color: 'var(--fp-text-secondary)', margin: '4px 0 0', fontSize: 14 }}>
          Marketing and enablement assets shared by the channel team.
        </p>
      </div>

      <section className="fp-card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <select value={categoryId}
            onChange={(e) => { setPage(1); setCategoryId(e.target.value) }}
            style={{ padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }}>
            <option value="">All categories</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <input type="search" placeholder="Search assets…"
            value={search} onChange={(e) => { setPage(1); setSearch(e.target.value) }}
            style={{ flex: 1, minWidth: 200, padding: '8px 10px', border: '1px solid #E0E4EA', borderRadius: 6, fontSize: 14 }} />
        </div>
      </section>

      {error && <div className="fp-alert fp-alert--danger">{error}</div>}
      {loading && <div className="fp-card" style={{ color: 'var(--fp-text-secondary)' }}>Loading resources…</div>}

      {!loading && assets.length === 0 && (
        <div className="fp-card" style={{ color: 'var(--fp-text-secondary)', textAlign: 'center', padding: 40 }}>
          <div style={{ fontSize: 36, marginBottom: 8 }}>📦</div>
          <div>No resources match the current filters.</div>
        </div>
      )}

      {!loading && assets.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 16 }}>
          {assets.map((a) => (
            <div key={a.id} className="fp-card" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 28 }}>{fileTypeIcon(a.file_type, a.file_name)}</span>
                <div style={{ fontWeight: 600, color: '#1E293B' }}>{a.title}</div>
              </div>
              {a.category_name && (
                <span style={{ alignSelf: 'flex-start', fontSize: 11, fontWeight: 600, color: '#1A6EBB',
                  background: '#EAF2FB', borderRadius: 12, padding: '2px 8px' }}>{a.category_name}</span>
              )}
              {a.description && (
                <div style={{ fontSize: 13, color: '#64748B', flex: 1 }}>{a.description}</div>
              )}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 4 }}>
                <span style={{ fontSize: 12, color: '#94A3B8' }}>{a.download_count} downloads</span>
                <button type="button" className="fp-btn fp-btn--primary fp-btn--sm" onClick={() => download(a)}>
                  Download
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && total > PAGE_SIZE && (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 12, marginTop: 16 }}>
          <button type="button" className="fp-btn fp-btn--ghost fp-btn--sm"
            disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
            ← Prev
          </button>
          <span style={{ fontSize: 13, color: '#64748B' }}>Page {page} of {totalPages}</span>
          <button type="button" className="fp-btn fp-btn--ghost fp-btn--sm"
            disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>
            Next →
          </button>
        </div>
      )}
    </>
  )
}
