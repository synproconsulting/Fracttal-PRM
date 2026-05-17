import { useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

function Tile({ label, description, disabled }) {
  return (
    <div
      style={{
        background: 'white',
        border: '1px solid #e0e0e0',
        borderRadius: 8,
        padding: 20,
        opacity: disabled ? 0.55 : 1,
        cursor: disabled ? 'not-allowed' : 'default',
        position: 'relative',
      }}
    >
      <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 6, color: '#102a43' }}>{label}</div>
      <div style={{ fontSize: 13, color: '#555' }}>{description}</div>
      {disabled && (
        <span
          style={{
            position: 'absolute',
            top: 12,
            right: 12,
            background: '#eee',
            color: '#666',
            fontSize: 11,
            padding: '2px 8px',
            borderRadius: 10,
          }}
        >
          Coming soon
        </span>
      )}
    </div>
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

  return (
    <div>
      <h1 style={{ margin: '0 0 6px', color: '#102a43' }}>
        Welcome, {fullName}
        {orgName ? ` — ${orgName}` : ''}
      </h1>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
        <span
          style={{
            background: isActive ? '#4caf50' : '#ff9800',
            color: 'white',
            padding: '4px 12px',
            borderRadius: 12,
            fontSize: 12,
            fontWeight: 500,
          }}
        >
          {isActive ? 'Active' : 'Pending Activation'}
        </span>
        <span style={{ fontSize: 13, color: '#666' }}>{payload?.email}</span>
      </div>

      {activationError && !activation && (
        <div
          style={{
            background: '#fff8e1',
            border: '1px solid #ffe082',
            color: '#7d6608',
            padding: 12,
            borderRadius: 6,
            marginBottom: 24,
            fontSize: 13,
          }}
        >
          {activationError}
        </div>
      )}

      <h2 style={{ color: '#102a43', fontSize: 18, margin: '0 0 12px' }}>What you can do</h2>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 16,
          marginBottom: 32,
        }}
      >
        <Tile
          label="Register a Deal"
          description="Submit a new opportunity for protection and approval."
          disabled
        />
        <Tile
          label="View Pipeline"
          description="Track all your registered deals and their status."
          disabled
        />
        <Tile
          label="Access Training"
          description="Browse certification courses and partner enablement."
          disabled
        />
        <Tile
          label="Browse Assets"
          description="Logos, brochures, sales collateral and demo videos."
          disabled
        />
      </div>

      <h2 style={{ color: '#102a43', fontSize: 18, margin: '0 0 12px' }}>Pending items</h2>
      <div
        style={{
          background: 'white',
          border: '1px solid #e0e0e0',
          borderRadius: 8,
          padding: 20,
          color: '#666',
          fontSize: 14,
        }}
      >
        No pending items.
      </div>
    </div>
  )
}
