import { useEffect, useMemo, useState } from 'react'
import { useOutletContext } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line,
} from 'recharts'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const PALETTE = ['#1A6EBB', '#22C55E', '#F59E0B', '#EF4444', '#8B5CF6', '#06B6D4']
const EXPORT_ROLES = new Set(['system_admin', 'channel_ops_admin', 'channel_manager', 'sales_ops', 'finance_approver'])

const PRESETS = [
  { key: '30',  label: 'Last 30 days', days: 30 },
  { key: '90',  label: 'Last 90 days', days: 90 },
  { key: 'ytd', label: 'This Year' },
  { key: 'all', label: 'All Time' },
]

const CATEGORIES = ['master', 'promotor', 'reseller']
const TIERS = ['Registered', 'Silver', 'Gold']

function toDateStr(d) {
  return d.toISOString().slice(0, 10)
}

function rangeFromPreset(key) {
  const today = new Date()
  if (key === 'all') return { from_date: null, to_date: null }
  if (key === 'ytd') return { from_date: `${today.getFullYear()}-01-01`, to_date: toDateStr(today) }
  if (key === '30') {
    const from = new Date(today); from.setDate(from.getDate() - 30)
    return { from_date: toDateStr(from), to_date: toDateStr(today) }
  }
  if (key === '90') {
    const from = new Date(today); from.setDate(from.getDate() - 90)
    return { from_date: toDateStr(from), to_date: toDateStr(today) }
  }
  return { from_date: null, to_date: null }
}

function formatCurrency(value) {
  if (value == null) return '—'
  try {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)
  } catch (_) {
    return `$${Math.round(value).toLocaleString()}`
  }
}

function buildQuery(filters) {
  const params = new URLSearchParams()
  if (filters.from_date) params.set('from_date', filters.from_date)
  if (filters.to_date) params.set('to_date', filters.to_date)
  if (filters.partner_category) params.set('partner_category', filters.partner_category)
  if (filters.tier) params.set('tier', filters.tier)
  const q = params.toString()
  return q ? `?${q}` : ''
}

function shimmerStyle(h = 16) {
  return {
    height: h,
    background: 'linear-gradient(90deg, #F1F5F9 25%, #E2E8F0 50%, #F1F5F9 75%)',
    backgroundSize: '200% 100%',
    borderRadius: 6,
    animation: 'fpr-shimmer 1.5s infinite',
  }
}

function Card({ children, style }) {
  return (
    <div
      style={{
        background: '#fff',
        border: '1px solid #E0E4EA',
        borderRadius: 8,
        boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
        padding: 20,
        ...style,
      }}
    >
      {children}
    </div>
  )
}

function SectionHeader({ children }) {
  return (
    <h2 style={{ fontSize: 16, fontWeight: 600, color: '#1E293B', margin: '0 0 16px' }}>{children}</h2>
  )
}

function Tile({ label, value, accent = '#1A6EBB' }) {
  return (
    <div
      style={{
        background: '#fff',
        border: '1px solid #E0E4EA',
        borderRadius: 8,
        padding: 20,
        flex: '1 1 18%',
        minWidth: 120,
      }}
    >
      <div style={{ fontSize: 32, fontWeight: 700, color: accent, lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: 13, color: '#64748B', marginTop: 8 }}>{label}</div>
    </div>
  )
}

function ErrorBanner({ message, onRetry }) {
  return (
    <div style={{ background: '#FEE2E2', color: '#991B1B', padding: 12, borderRadius: 6, marginBottom: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span>{message}</span>
      <button type="button" onClick={onRetry} style={{ background: '#fff', color: '#991B1B', border: '1px solid #DC2626', borderRadius: 4, padding: '4px 12px', cursor: 'pointer' }}>Retry</button>
    </div>
  )
}

function truncate(s, n = 14) {
  if (!s) return ''
  return s.length > n ? `${s.slice(0, n)}…` : s
}

export default function InternalReports() {
  const ctx = useOutletContext() || {}
  const { token, payload } = ctx
  const role = payload && payload.role
  const canExport = role && EXPORT_ROLES.has(role)

  const [preset, setPreset] = useState('90')
  const [category, setCategory] = useState('')
  const [tier, setTier] = useState('')

  const filters = useMemo(() => {
    const r = rangeFromPreset(preset)
    return {
      from_date: r.from_date,
      to_date: r.to_date,
      partner_category: category || null,
      tier: tier || null,
    }
  }, [preset, category, tier])

  const [pipeline, setPipeline] = useState(null)
  const [cycle, setCycle] = useState(null)
  const [conflicts, setConflicts] = useState(null)
  const [loading, setLoading] = useState({ pipeline: true, cycle: true, conflict: true })
  const [error, setError] = useState({ pipeline: null, cycle: null, conflict: null })
  const [sort, setSort] = useState({ key: 'total_deals', dir: 'desc' })

  function fetchPipeline() {
    setLoading((l) => ({ ...l, pipeline: true }))
    setError((e) => ({ ...e, pipeline: null }))
    fetch(`${API}/internal/reports/pipeline${buildQuery(filters)}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`)
        return r.json()
      })
      .then((d) => setPipeline(d))
      .catch((e) => setError((er) => ({ ...er, pipeline: e.message })))
      .finally(() => setLoading((l) => ({ ...l, pipeline: false })))
  }

  function fetchCycle() {
    setLoading((l) => ({ ...l, cycle: true }))
    setError((e) => ({ ...e, cycle: null }))
    fetch(`${API}/internal/reports/cycle-times`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`)
        return r.json()
      })
      .then((d) => setCycle(d))
      .catch((e) => setError((er) => ({ ...er, cycle: e.message })))
      .finally(() => setLoading((l) => ({ ...l, cycle: false })))
  }

  function fetchConflicts() {
    setLoading((l) => ({ ...l, conflict: true }))
    setError((e) => ({ ...e, conflict: null }))
    fetch(`${API}/internal/reports/conflicts${buildQuery(filters)}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (r) => {
        if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`)
        return r.json()
      })
      .then((d) => setConflicts(d))
      .catch((e) => setError((er) => ({ ...er, conflict: e.message })))
      .finally(() => setLoading((l) => ({ ...l, conflict: false })))
  }

  useEffect(() => { fetchPipeline(); fetchConflicts() /* eslint-disable-line */ }, [preset, category, tier])
  useEffect(() => { fetchCycle() /* eslint-disable-line */ }, [])

  async function downloadCsv() {
    try {
      const r = await fetch(`${API}/internal/reports/pipeline/export${buildQuery(filters)}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) return
      const blob = await r.blob()
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = 'pipeline_export.csv'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(a.href)
    } catch (_) { /* silent */ }
  }

  const totals = pipeline ? pipeline.totals : { total_deals: 0, approved: 0, under_review: 0, rejected: 0, total_value: 0 }
  const topPartners = pipeline ? [...pipeline.by_partner].sort((a, b) => b.total_deals - a.total_deals).slice(0, 10) : []
  const chartPartners = topPartners.map((p) => ({
    name: truncate(p.partner_name),
    approved: p.approved,
    under_review: 0,
    rejected: 0,
  }))
  // Build stacked chart data from totals (we only have approved + total in by_partner — approximate)
  const stackedData = topPartners.map((p) => ({
    name: truncate(p.partner_name),
    approved: p.approved,
    other: Math.max(p.total_deals - p.approved, 0),
  }))

  // partner table sort
  const sortedPartners = pipeline ? [...pipeline.by_partner].sort((a, b) => {
    const va = a[sort.key]; const vb = b[sort.key]
    if (va === vb) return 0
    return (sort.dir === 'desc' ? -1 : 1) * (va < vb ? -1 : 1)
  }) : []

  function setSortKey(k) {
    setSort((s) => ({ key: k, dir: s.key === k && s.dir === 'desc' ? 'asc' : 'desc' }))
  }

  // donut data
  const donut = pipeline ? pipeline.by_category.map((c) => ({ name: c.category, value: c.total_deals })) : []

  // cycle months -> categories pivot
  const cycleData = useMemo(() => {
    if (!cycle) return { rows: [], categories: [] }
    const cats = Array.from(new Set(cycle.by_category_and_month.map((r) => r.category)))
    const months = Array.from(new Set(cycle.by_category_and_month.map((r) => r.month))).sort()
    const rows = months.map((m) => {
      const row = { month: m }
      cats.forEach((c) => {
        const hit = cycle.by_category_and_month.find((r) => r.category === c && r.month === m)
        row[c] = hit ? hit.avg_days : null
      })
      return row
    })
    return { rows, categories: cats }
  }, [cycle])

  const conflictPctBadge = conflicts && (
    conflicts.conflict_rate_pct > 10
      ? { bg: '#FEE2E2', text: '#DC2626' }
      : conflicts.conflict_rate_pct > 5
        ? { bg: '#FEF3C7', text: '#D97706' }
        : { bg: '#DCFCE7', text: '#16A34A' }
  )

  return (
    <div style={{ background: '#F5F7FA', padding: 20, minHeight: '100%' }}>
      <style>{`@keyframes fpr-shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
        .fpr-th { cursor: pointer; user-select: none; }
        .fpr-th:hover { color: #1A6EBB; }
        @media (max-width: 768px) {
          .fpr-tilerow { flex-wrap: wrap; }
          .fpr-tilerow > * { flex: 1 1 45%; min-width: 0; }
          .fpr-tworow { flex-direction: column; }
          .fpr-filterbar { flex-wrap: wrap; }
          .fpr-filterbar > * { flex: 1 1 auto; }
        }
      `}</style>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: '#1E293B', margin: 0 }}>Reports & Analytics</h1>
        {canExport && (
          <button
            type="button"
            onClick={downloadCsv}
            style={{ background: '#fff', border: '1px solid #1A6EBB', color: '#1A6EBB', padding: '8px 16px', borderRadius: 6, fontWeight: 600, cursor: 'pointer' }}
          >
            Export CSV ↓
          </button>
        )}
      </div>

      <Card style={{ marginBottom: 16 }}>
        <div className="fpr-filterbar" style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: 8 }}>
            {PRESETS.map((p) => (
              <button
                key={p.key}
                type="button"
                onClick={() => setPreset(p.key)}
                style={{
                  padding: '6px 12px',
                  borderRadius: 6,
                  border: preset === p.key ? '1px solid #1A6EBB' : '1px solid #E0E4EA',
                  background: preset === p.key ? '#1A6EBB' : '#fff',
                  color: preset === p.key ? '#fff' : '#64748B',
                  cursor: 'pointer',
                  fontWeight: 600,
                  fontSize: 13,
                }}
              >{p.label}</button>
            ))}
          </div>
          <select value={category} onChange={(e) => setCategory(e.target.value)} style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #E0E4EA', background: '#fff' }}>
            <option value="">All Categories</option>
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <select value={tier} onChange={(e) => setTier(e.target.value)} style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #E0E4EA', background: '#fff' }}>
            <option value="">All Tiers</option>
            {TIERS.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
      </Card>

      {/* Section 1 — Pipeline Overview */}
      <Card style={{ marginBottom: 16 }}>
        <SectionHeader>Pipeline Overview</SectionHeader>
        {loading.pipeline && (
          <>
            <div className="fpr-tilerow" style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
              {[1,2,3,4,5].map((i) => <div key={i} style={{ ...shimmerStyle(80), flex: '1 1 18%' }} />)}
            </div>
            <div style={shimmerStyle(280)} />
          </>
        )}
        {!loading.pipeline && error.pipeline && (
          <ErrorBanner message={`Failed to load Pipeline Overview: ${error.pipeline}`} onRetry={fetchPipeline} />
        )}
        {!loading.pipeline && !error.pipeline && pipeline && (
          <>
            <div className="fpr-tilerow" style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
              <Tile label="Total Deals" value={totals.total_deals} />
              <Tile label="Accepted" value={totals.approved} accent="#22C55E" />
              <Tile label="In Review" value={totals.under_review} accent="#3B82F6" />
              <Tile label="Rejected" value={totals.rejected} accent="#EF4444" />
              <Tile label="Total Value" value={formatCurrency(totals.total_value)} />
            </div>

            {topPartners.length === 0 ? (
              <div style={{ textAlign: 'center', color: '#94A3B8', fontStyle: 'italic', padding: 32 }}>
                No deal data for selected period.
              </div>
            ) : (
              <>
                <div style={{ height: 280, marginBottom: 16 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={stackedData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Bar dataKey="approved" stackId="a" fill="#22C55E" name="Accepted" />
                      <Bar dataKey="other" stackId="a" fill="#3B82F6" name="In Pipeline" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className="fpr-tworow" style={{ display: 'flex', gap: 20 }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>By Category</h3>
                    <div style={{ height: 240 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie data={donut} dataKey="value" nameKey="name" outerRadius={80} innerRadius={50}>
                            {donut.map((_, i) => <Cell key={i} fill={PALETTE[i % PALETTE.length]} />)}
                          </Pie>
                          <Tooltip />
                          <Legend />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Top Partners</h3>
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                        <thead>
                          <tr style={{ background: '#F8FAFC' }}>
                            <th className="fpr-th" style={{ padding: 8, textAlign: 'left' }} onClick={() => setSortKey('partner_name')}>Partner Name</th>
                            <th className="fpr-th" style={{ padding: 8, textAlign: 'right' }} onClick={() => setSortKey('total_deals')}>Total Deals</th>
                            <th className="fpr-th" style={{ padding: 8, textAlign: 'right' }} onClick={() => setSortKey('approved')}>Accepted</th>
                            <th className="fpr-th" style={{ padding: 8, textAlign: 'right' }} onClick={() => setSortKey('total_value')}>Pipeline Value</th>
                          </tr>
                        </thead>
                        <tbody>
                          {sortedPartners.map((p) => (
                            <tr key={p.org_id} style={{ borderBottom: '1px solid #E0E4EA' }}>
                              <td style={{ padding: 8 }}>{p.partner_name}</td>
                              <td style={{ padding: 8, textAlign: 'right' }}>{p.total_deals}</td>
                              <td style={{ padding: 8, textAlign: 'right' }}>{p.approved}</td>
                              <td style={{ padding: 8, textAlign: 'right' }}>{formatCurrency(p.total_value)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </>
            )}
          </>
        )}
      </Card>

      {/* Section 2 — Cycle Times */}
      <Card style={{ marginBottom: 16 }}>
        <SectionHeader>Cycle Times</SectionHeader>
        {loading.cycle && <div style={shimmerStyle(240)} />}
        {!loading.cycle && error.cycle && (
          <ErrorBanner message={`Failed to load Cycle Times: ${error.cycle}`} onRetry={fetchCycle} />
        )}
        {!loading.cycle && !error.cycle && cycle && (
          <>
            <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', marginBottom: 16, flexWrap: 'wrap' }}>
              <div style={{ background: '#fff', border: '1px solid #E0E4EA', borderRadius: 8, padding: 20, minWidth: 200 }}>
                <div style={{ fontSize: 48, fontWeight: 700, color: '#1A6EBB', lineHeight: 1 }}>
                  {cycle.overall_avg_days != null ? cycle.overall_avg_days.toFixed(1) : '—'}
                </div>
                <div style={{ fontSize: 13, color: '#64748B', marginTop: 8 }}>avg. days to decision</div>
              </div>
              <div style={{ flex: 1, minWidth: 300, height: 240 }}>
                {cycleData.rows.length === 0 ? (
                  <div style={{ textAlign: 'center', color: '#94A3B8', fontStyle: 'italic', padding: 32 }}>
                    No completed deals to analyse yet.
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={cycleData.rows}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="month" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      {cycleData.categories.map((cat, i) => (
                        <Line key={cat} type="monotone" dataKey={cat} stroke={PALETTE[i % PALETTE.length]} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>

            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Slowest 5 Deals</h3>
            {cycle.slowest_deals.length === 0 ? (
              <div style={{ textAlign: 'center', color: '#94A3B8', fontStyle: 'italic', padding: 16 }}>
                No completed deals yet.
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ background: '#F8FAFC' }}>
                    <th style={{ padding: 8, textAlign: 'left' }}>Deal Name</th>
                    <th style={{ padding: 8, textAlign: 'left' }}>Partner</th>
                    <th style={{ padding: 8, textAlign: 'right' }}>Days to Decision</th>
                    <th style={{ padding: 8, textAlign: 'left' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {cycle.slowest_deals.map((d) => (
                    <tr key={d.deal_id} style={{ borderBottom: '1px solid #E0E4EA' }}>
                      <td style={{ padding: 8 }}>{d.deal_name}</td>
                      <td style={{ padding: 8 }}>{d.partner_name}</td>
                      <td style={{ padding: 8, textAlign: 'right' }}>{d.days_to_decision.toFixed(1)}</td>
                      <td style={{ padding: 8 }}>{d.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </Card>

      {/* Section 3 — Conflict Report */}
      <Card>
        <SectionHeader>Conflict Report</SectionHeader>
        {loading.conflict && <div style={shimmerStyle(120)} />}
        {!loading.conflict && error.conflict && (
          <ErrorBanner message={`Failed to load Conflict Report: ${error.conflict}`} onRetry={fetchConflicts} />
        )}
        {!loading.conflict && !error.conflict && conflicts && (
          <>
            <div style={{ display: 'flex', gap: 20, alignItems: 'center', marginBottom: 16, flexWrap: 'wrap' }}>
              <div style={{ background: conflictPctBadge.bg, color: conflictPctBadge.text, borderRadius: 8, padding: 20, minWidth: 200 }}>
                <div style={{ fontSize: 48, fontWeight: 700, lineHeight: 1 }}>{conflicts.conflict_rate_pct}%</div>
                <div style={{ fontSize: 13, marginTop: 8 }}>conflict rate</div>
              </div>
              <div style={{ color: '#64748B', fontSize: 13 }}>
                {conflicts.conflict_count} of {conflicts.total_deals} deals flagged
              </div>
            </div>

            {conflicts.unresolved_conflicts.length === 0 ? (
              <div style={{ color: '#16A34A', textAlign: 'center', padding: 16 }}>
                No unresolved conflicts ✓
              </div>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ background: '#F8FAFC' }}>
                    <th style={{ padding: 8, textAlign: 'left' }}>Deal</th>
                    <th style={{ padding: 8, textAlign: 'left' }}>Partner</th>
                    <th style={{ padding: 8, textAlign: 'left' }}>Customer Domain</th>
                    <th style={{ padding: 8, textAlign: 'left' }}>Submitted</th>
                  </tr>
                </thead>
                <tbody>
                  {conflicts.unresolved_conflicts.map((u) => (
                    <tr key={u.deal_id} style={{ borderBottom: '1px solid #E0E4EA' }}>
                      <td style={{ padding: 8 }}>{u.deal_name}</td>
                      <td style={{ padding: 8 }}>{u.partner_name}</td>
                      <td style={{ padding: 8 }}>{u.customer_domain || '—'}</td>
                      <td style={{ padding: 8 }}>{u.submitted_at ? new Date(u.submitted_at).toLocaleDateString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </Card>
    </div>
  )
}
