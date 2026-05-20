import { useEffect, useMemo, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import ActivationChecklist from '../components/ActivationChecklist.jsx'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const STATUS_LABEL = {
  draft: 'Draft',
  submitted: 'Submitted',
  under_review: 'Under Review',
  approved: 'Approved',
  rejected: 'Rejected',
  info_required: 'Info Required',
  expired: 'Expired',
}

const STATUS_TONE = {
  draft: 'neutral',
  submitted: 'neutral',
  under_review: 'neutral',
  approved: 'success',
  rejected: 'warning',
  info_required: 'warning',
  expired: 'warning',
}

function StatusBadge({ status }) {
  const tone = STATUS_TONE[status] || 'neutral'
  return (
    <span className={`fp-badge fp-badge--${tone}`}>{STATUS_LABEL[status] || status}</span>
  )
}

function KpiTile({ label, value, sub, accent, linkTo, linkLabel }) {
  return (
    <div
      className="fp-card"
      style={{
        padding: 18,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        borderLeft: accent ? `4px solid ${accent}` : '4px solid var(--fp-primary, #1A6EBB)',
      }}
    >
      <div style={{ fontSize: 'var(--fp-fs-sm, 13px)', color: 'var(--fp-text-secondary, #5A6478)', textTransform: 'uppercase', letterSpacing: 0.5, fontWeight: 600 }}>
        {label}
      </div>
      <div style={{ fontSize: 32, fontWeight: 700, lineHeight: 1, color: 'var(--fp-text, #1B2236)' }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontSize: 'var(--fp-fs-sm, 13px)', color: 'var(--fp-text-secondary, #5A6478)' }}>
          {sub}
        </div>
      )}
      {linkTo && (
        <Link
          to={linkTo}
          style={{ marginTop: 4, fontSize: 'var(--fp-fs-sm, 13px)', color: 'var(--fp-primary, #1A6EBB)', fontWeight: 600, textDecoration: 'none' }}
        >
          {linkLabel || 'View →'}
        </Link>
      )}
    </div>
  )
}

function Tile({ label, description, icon, to, disabled, badge }) {
  const content = (
    <>
      <div className="fp-tile__icon">{icon}</div>
      <h3 className="fp-tile__title">{label}</h3>
      <p className="fp-tile__description">{description}</p>
      {badge && (
        <span className={`fp-badge ${badge.tone === 'success' ? 'fp-badge--success' : 'fp-badge--neutral'} fp-tile__badge`}>
          {badge.label}
        </span>
      )}
    </>
  )
  if (disabled || !to) {
    return (
      <div className="fp-tile fp-tile--disabled" aria-disabled="true" title={disabled ? 'Coming soon' : undefined}>
        {content}
        {disabled && !badge && (
          <span className="fp-badge fp-badge--neutral fp-tile__badge">Coming soon</span>
        )}
      </div>
    )
  }
  return (
    <Link to={to} className="fp-tile">
      {content}
    </Link>
  )
}

export default function PartnerHome() {
  const ctx = useOutletContext() || {}
  const { payload, orgName, token } = ctx
  const [me, setMe] = useState(null)
  const [summary, setSummary] = useState(null)
  const [summaryError, setSummaryError] = useState(null)
  const [recentDeals, setRecentDeals] = useState([])
  const [recentDealsError, setRecentDealsError] = useState(null)
  const [pipelineSummary, setPipelineSummary] = useState(null)
  // FPRM-270 / Sprint 17 — dynamic activation criteria for the progress
  // widget. Source of truth for required-item count instead of the
  // dashboard summary's hardcoded ``items_total``.
  const [criteriaSummary, setCriteriaSummary] = useState(null)

  useEffect(() => {
    if (!token) return
    fetch(`${API}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then(setMe)
      .catch(() => {})
  }, [token])

  useEffect(() => {
    if (!payload?.partner_org_id || !token) return
    fetch(`${API}/partners/${payload.partner_org_id}/dashboard/summary`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        if (r.ok) return r.json()
        const body = await r.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${r.status}`)
      })
      .then(setSummary)
      .catch((e) => setSummaryError(e.message))
  }, [payload?.partner_org_id, token])

  useEffect(() => {
    if (!payload?.partner_org_id || !token) return
    fetch(`${API}/partners/${payload.partner_org_id}/activation/criteria`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data && Array.isArray(data.required_criteria)) {
          setCriteriaSummary({
            total: data.required_criteria.length,
            done: data.required_criteria.filter((c) => c.is_met).length,
            complete: Boolean(data.activation_complete),
          })
        }
      })
      .catch(() => {})
  }, [payload?.partner_org_id, token])

  useEffect(() => {
    if (!payload?.partner_org_id || !token) return
    fetch(`${API}/partners/${payload.partner_org_id}/pipeline`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then(setPipelineSummary)
      .catch(() => {})
  }, [payload?.partner_org_id, token])

  useEffect(() => {
    if (!payload?.partner_org_id || !token) return
    fetch(`${API}/deal-registrations?limit=5`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        if (r.ok) return r.json()
        if (r.status === 404) return { items: [] }
        const body = await r.json().catch(() => ({}))
        throw new Error(body.detail || `HTTP ${r.status}`)
      })
      .then((data) => {
        const items = Array.isArray(data?.items) ? data.items : (Array.isArray(data) ? data : [])
        setRecentDeals(items.slice(0, 5))
      })
      .catch((e) => setRecentDealsError(e.message))
  }, [payload?.partner_org_id, token])

  const fullName = me?.full_name || payload?.email?.split('@')[0] || 'Partner'

  const totalDeals = useMemo(() => {
    if (!summary?.deals) return 0
    return Object.values(summary.deals).reduce((acc, v) => acc + (Number(v) || 0), 0)
  }, [summary])

  // Prefer the dynamic criteria endpoint (FPRM-270) when available — it
  // reflects whatever ``activation_checklist_config`` says is required for
  // this partner's category/tier. Fall back to the dashboard summary's
  // pre-computed counts for the brief window before the criteria fetch
  // resolves, or if the criteria fetch failed.
  const isActive = criteriaSummary
    ? criteriaSummary.complete
    : (summary ? summary.activation.complete : false)
  const itemsComplete = criteriaSummary?.done ?? summary?.activation?.items_complete ?? 0
  const itemsTotal = criteriaSummary?.total ?? summary?.activation?.items_total ?? 4
  const pct = itemsTotal > 0 ? Math.round((itemsComplete / itemsTotal) * 100) : 0
  const docsPending = summary?.documents?.pending_review ?? 0
  const dealsInfoRequired = summary?.deals?.info_required ?? 0

  return (
    <div>
      <div className="fp-page-header">
        <div>
          <h1 className="fp-page-title">
            Welcome, {fullName}
            {orgName ? <span style={{ color: 'var(--fp-text-secondary)', fontWeight: 500 }}>{' — '}{orgName}</span> : null}
          </h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 8 }}>
            <span className={`fp-badge ${isActive ? 'fp-badge--success' : 'fp-badge--warning'}`}>
              {isActive ? 'Active' : 'Pending Activation'}
            </span>
            <span style={{ fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>{payload?.email}</span>
          </div>
        </div>
      </div>

      {summaryError && (
        <div className="fp-alert fp-alert--warning" style={{ marginBottom: 16 }}>
          Could not load dashboard summary: {summaryError}
        </div>
      )}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 16,
          marginBottom: 24,
        }}
      >
        <KpiTile
          label="My Deals"
          value={totalDeals}
          sub="All registered opportunities"
          linkTo="/portal/deals"
        />
        <KpiTile
          label="Info Required"
          value={dealsInfoRequired}
          sub="Deals awaiting your response"
          accent={dealsInfoRequired > 0 ? '#D14343' : undefined}
          linkTo="/portal/deals?status=info_required"
        />
        <KpiTile
          label="Documents Pending"
          value={docsPending}
          sub="Awaiting Fracttal review"
          linkTo="/portal/documents"
        />
      </div>

      {summary && !isActive && (
        <div className="fp-card" style={{ padding: 18, marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontSize: 'var(--fp-fs-sm)', fontWeight: 700, color: 'var(--fp-text)' }}>
              Activation progress
            </span>
            <span style={{ fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>
              {itemsComplete} of {itemsTotal} items complete ({pct}%)
            </span>
          </div>
          <div className="fp-progress">
            <div className="fp-progress__fill" style={{ width: `${pct}%` }} />
          </div>
          <div style={{ marginTop: 12 }}>
            <ActivationChecklist partnerId={payload.partner_org_id} token={token} />
          </div>
        </div>
      )}
      {summary && isActive && (
        <div className="fp-alert fp-alert--success" style={{ marginBottom: 24 }}>
          ✅ Your account is active — all activation steps complete.
        </div>
      )}

      <h2 className="fp-section-title">My pipeline</h2>
      <div className="fp-card" style={{ padding: 18, marginBottom: 24 }}>
        {pipelineSummary ? (
          <>
            <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
              <div>
                <div style={{ fontSize: 11, color: '#64748B', textTransform: 'uppercase', fontWeight: 600 }}>Total Deals</div>
                <div style={{ fontSize: 22, fontWeight: 700 }}>
                  {Object.values(pipelineSummary).reduce((acc, arr) => acc + (Array.isArray(arr) ? arr.length : 0), 0)}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: '#64748B', textTransform: 'uppercase', fontWeight: 600 }}>Approved</div>
                <div style={{ fontSize: 22, fontWeight: 700, color: '#22C55E' }}>
                  {(pipelineSummary.approved || []).length}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: '#64748B', textTransform: 'uppercase', fontWeight: 600 }}>In Review</div>
                <div style={{ fontSize: 22, fontWeight: 700, color: '#F59E0B' }}>
                  {(pipelineSummary.under_review || []).length + (pipelineSummary.submitted || []).length}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 11, color: '#64748B', textTransform: 'uppercase', fontWeight: 600 }}>Info Required</div>
                <div style={{ fontSize: 22, fontWeight: 700, color: '#8B5CF6' }}>
                  {(pipelineSummary.info_required || []).length}
                </div>
              </div>
            </div>
            <Link to="/portal/deals?view=pipeline" style={{ display: 'inline-block', marginTop: 12, fontSize: 13, color: 'var(--fp-primary, #1A6EBB)', textDecoration: 'none', fontWeight: 600 }}>
              View Pipeline →
            </Link>
          </>
        ) : (
          <div style={{ color: 'var(--fp-text-secondary)' }}>No deals registered yet.</div>
        )}
      </div>

      <h2 className="fp-section-title">Recent deals</h2>
      <div className="fp-card" style={{ padding: 0, marginBottom: 24 }}>
        {recentDealsError && (
          <div className="fp-alert fp-alert--warning" style={{ margin: 12 }}>
            Could not load recent deals: {recentDealsError}
          </div>
        )}
        {!recentDealsError && recentDeals.length === 0 && (
          <div style={{ padding: 18, color: 'var(--fp-text-secondary)' }}>
            No deals yet.{' '}
            <Link to="/portal/deals/new" style={{ color: 'var(--fp-primary, #1A6EBB)', fontWeight: 600 }}>
              Register a Deal →
            </Link>
          </div>
        )}
        {recentDeals.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--fp-bg, #F5F7FA)', textAlign: 'left' }}>
                <th style={{ padding: '12px 14px', fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>Deal</th>
                <th style={{ padding: '12px 14px', fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>Customer</th>
                <th style={{ padding: '12px 14px', fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>Status</th>
                <th style={{ padding: '12px 14px', fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>Submitted</th>
              </tr>
            </thead>
            <tbody>
              {recentDeals.map((d) => (
                <tr key={d.id} style={{ borderTop: '1px solid var(--fp-border, #E0E4EA)' }}>
                  <td style={{ padding: '12px 14px' }}>
                    <Link to={`/portal/deals/${d.id}`} style={{ color: 'var(--fp-primary, #1A6EBB)', textDecoration: 'none', fontWeight: 600 }}>
                      {d.deal_name || '(unnamed)'}
                    </Link>
                  </td>
                  <td style={{ padding: '12px 14px', color: 'var(--fp-text-secondary)' }}>{d.customer_name || '—'}</td>
                  <td style={{ padding: '12px 14px' }}><StatusBadge status={d.status} /></td>
                  <td style={{ padding: '12px 14px', color: 'var(--fp-text-secondary)', fontSize: 'var(--fp-fs-sm)' }}>
                    {d.submitted_at ? new Date(d.submitted_at).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div style={{ padding: 14, borderTop: '1px solid var(--fp-border, #E0E4EA)' }}>
          <Link to="/portal/deals/new" className="fp-btn fp-btn--primary fp-btn--sm">
            Register a Deal →
          </Link>
        </div>
      </div>

      <h2 className="fp-section-title">What you can do</h2>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: 16,
          marginBottom: 32,
        }}
      >
        <Tile
          label="Register a Deal"
          description="Submit a new opportunity for protection and approval."
          icon="🤝"
          to="/portal/deals/new"
          badge={isActive ? null : { tone: 'neutral', label: 'Activation required' }}
        />
        <Tile
          label="My Pipeline"
          description="Track all your registered deals and their status."
          icon="📈"
          to="/portal/deals"
        />
        <Tile
          label="Profile"
          description="Update your organisation and business details."
          icon="🏢"
          to="/portal/profile"
        />
        <Tile
          label="Documents"
          description="Upload and manage your partnership documents."
          icon="📄"
          to="/portal/documents"
        />
        <Tile
          label="Access Training"
          description="Browse certification courses and partner enablement."
          icon="🎓"
          disabled
        />
        <Tile
          label="Browse Assets"
          description="Logos, brochures, sales collateral and demo videos."
          icon="🎨"
          disabled
        />
      </div>
    </div>
  )
}
