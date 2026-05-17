import { useEffect, useState } from 'react'
import { Link, useOutletContext } from 'react-router-dom'
import ActivationChecklist from '../components/ActivationChecklist.jsx'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

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
  const [activation, setActivation] = useState(null)
  const [activationError, setActivationError] = useState(null)

  useEffect(() => {
    if (!token) return
    fetch(`${API}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => (r.ok ? r.json() : null))
      .then(setMe)
      .catch(() => {})
  }, [token])

  useEffect(() => {
    if (!payload?.partner_org_id || !token) return
    fetch(`${API}/partners/${payload.partner_org_id}/activation`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        if (r.ok) return r.json()
        if (r.status === 404) {
          setActivationError('Activation checklist will appear here once your account is fully provisioned.')
          return null
        }
        throw new Error(`HTTP ${r.status}`)
      })
      .then(setActivation)
      .catch((e) => setActivationError(e.message))
  }, [payload?.partner_org_id, token])

  const fullName = me?.full_name || payload?.email?.split('@')[0] || 'Partner'
  const isActive = activation && activation.activation_complete

  const checklistItems = activation
    ? ['profile_complete', 'documents_uploaded', 'terms_signed']
    : []
  const doneCount = activation ? checklistItems.filter((k) => activation[k]).length : 0
  const totalCount = checklistItems.length || 3
  const pct = activation ? Math.round((doneCount / totalCount) * 100) : 0

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

      {activation && !activation.activation_complete && (
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontSize: 'var(--fp-fs-sm)', fontWeight: 600, color: 'var(--fp-text)' }}>
              Activation progress
            </span>
            <span style={{ fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>
              {doneCount} / {totalCount}
            </span>
          </div>
          <div className="fp-progress">
            <div className="fp-progress__fill" style={{ width: `${pct}%` }} />
          </div>
        </div>
      )}

      {activation && !activation.activation_complete && (
        <div style={{ marginBottom: 32 }}>
          <ActivationChecklist partnerId={payload.partner_org_id} token={token} />
        </div>
      )}
      {activationError && !activation && (
        <div className="fp-alert fp-alert--warning">{activationError}</div>
      )}

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
