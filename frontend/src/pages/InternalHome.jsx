import { useEffect, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

function formatCurrency(value) {
  if (value == null) return '—'
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
    }).format(value)
  } catch (_) {
    return `$${Math.round(value).toLocaleString()}`
  }
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

function SectionHeader({ children }) {
  return (
    <h2 style={{ fontSize: 16, margin: '24px 0 12px', color: 'var(--fp-text, #1B2236)', fontWeight: 700 }}>
      {children}
    </h2>
  )
}

export default function InternalHome() {
  const ctx = useOutletContext() || {}
  const { token } = ctx
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fetch(`${API}/internal/dashboard/summary`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (resp) => {
        if (!resp.ok) {
          const detail = (await resp.json().catch(() => ({}))).detail || `HTTP ${resp.status}`
          throw new Error(detail)
        }
        return resp.json()
      })
      .then((data) => { if (!cancelled) setSummary(data) })
      .catch((err) => { if (!cancelled) setError(err.message || 'Failed to load dashboard') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [token])

  if (loading) {
    return (
      <div style={{ padding: 24 }}>
        <h1 style={{ fontSize: 22, margin: '0 0 16px' }}>Internal Home</h1>
        <div className="fp-card" style={{ padding: 18 }}>Loading dashboard…</div>
      </div>
    )
  }

  if (error) {
    return (
      <div style={{ padding: 24 }}>
        <h1 style={{ fontSize: 22, margin: '0 0 16px' }}>Internal Home</h1>
        <div className="fp-alert fp-alert--danger">Could not load dashboard: {error}</div>
      </div>
    )
  }

  const apps = summary?.applications || {}
  const deals = summary?.deals || {}
  const partners = summary?.partners || {}
  const conflicts = summary?.conflicts || {}

  return (
    <div style={{ padding: 24 }}>
      <h1 style={{ fontSize: 22, margin: '0 0 4px' }}>Internal Home</h1>
      <p style={{ margin: '0 0 16px', color: 'var(--fp-text-secondary, #5A6478)' }}>
        Pipeline, applications, partner health at a glance.
      </p>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 16,
        }}
      >
        <KpiTile
          label="Applications Pending"
          value={apps.pending_review ?? 0}
          sub="Submitted or in review"
          linkTo="/internal/applications?status=under_review"
        />
        <KpiTile
          label="Info Required"
          value={apps.info_required ?? 0}
          sub="Awaiting applicant"
          accent={(apps.info_required ?? 0) > 0 ? '#D14343' : undefined}
          linkTo="/internal/applications?status=info_required"
        />
        <KpiTile
          label="Deals in Review"
          value={deals.under_review ?? 0}
          sub={`${deals.submitted ?? 0} submitted awaiting review`}
          linkTo="/internal/deals?status=under_review"
        />
        <KpiTile
          label="Open Conflicts"
          value={conflicts.open ?? 0}
          sub="Unresolved conflict_detected"
          accent={(conflicts.open ?? 0) > 0 ? '#D14343' : undefined}
          linkTo="/internal/deals?conflict=open"
        />
      </div>

      <SectionHeader>Pipeline this month</SectionHeader>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 16,
        }}
      >
        <KpiTile
          label="Pipeline Value"
          value={formatCurrency(deals.total_pipeline_value)}
          sub="Submitted, in review, or approved"
        />
        <KpiTile
          label="Approved This Month"
          value={deals.approved_this_month ?? 0}
          sub="Reviewed and approved"
        />
        <KpiTile
          label="Applications This Month"
          value={apps.total_this_month ?? 0}
          sub="Created since the 1st"
        />
      </div>

      <SectionHeader>Partner health</SectionHeader>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 16,
        }}
      >
        <KpiTile
          label="Active Partners"
          value={partners.active ?? 0}
          sub="Status = active"
        />
        <KpiTile
          label="Pending Activation"
          value={partners.pending_activation ?? 0}
          sub="Awaiting first-step completion"
        />
        <KpiTile
          label="Total Partners"
          value={partners.total ?? 0}
          sub="All organisations on file"
        />
      </div>

      <SectionHeader>Quick actions</SectionHeader>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <Link to="/internal/applications" className="fp-btn fp-btn--primary">
          Review Applications →
        </Link>
        <Link to="/internal/deals" className="fp-btn fp-btn--ghost">
          Review Deals →
        </Link>
      </div>
    </div>
  )
}
