import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const ITEMS = [
  {
    key: 'profile_complete',
    label: 'Complete your partner profile (at least 80%)',
    actionLabel: 'Complete profile',
    actionTo: '/portal/profile',
  },
  {
    key: 'documents_uploaded',
    label: 'Upload required documents (Fiscal ID + ID of legal representative)',
    actionLabel: 'Upload documents',
    actionTo: '/portal/documents',
  },
  {
    key: 'terms_signed',
    label: 'Sign the partnership agreement',
    actionLabel: null,  // contract date is set by internal team — no self-service link
    actionTo: null,
    fallbackHint: 'Your Fracttal channel manager will set this once the agreement is signed.',
  },
]

function Tick({ done }) {
  if (done) {
    return (
      <span
        aria-label="Completed"
        style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          width: 22, height: 22, borderRadius: '50%',
          background: '#4caf50', color: 'white', fontSize: 14, fontWeight: 600,
        }}
      >
        ✓
      </span>
    )
  }
  return (
    <span
      aria-label="Pending"
      style={{
        display: 'inline-block', width: 22, height: 22, borderRadius: '50%',
        border: '2px solid #bdbdbd',
      }}
    />
  )
}

export default function ActivationChecklist({ partnerId, token: tokenProp }) {
  const [checklist, setChecklist] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const token = tokenProp || localStorage.getItem('token')

  useEffect(() => {
    if (!partnerId || !token) return
    setLoading(true)
    setError(null)
    fetch(`${API}/partners/${partnerId}/activation`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        if (r.ok) return r.json()
        if (r.status === 404) {
          setChecklist(null)
          return null
        }
        throw new Error(`HTTP ${r.status}`)
      })
      .then((data) => {
        if (data) setChecklist(data)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [partnerId, token])

  if (loading) return <div style={{ padding: 16, color: '#666', fontSize: 13 }}>Loading activation status…</div>
  if (error) {
    return (
      <div
        style={{
          padding: 16, background: '#fdecea', border: '1px solid #f5c6cb',
          color: '#b71c1c', borderRadius: 6, fontSize: 13,
        }}
      >
        Could not load activation checklist: {error}
      </div>
    )
  }
  if (!checklist) return null

  const visibleItems = ITEMS  // baseline_training intentionally excluded from display
  const doneCount = visibleItems.filter((i) => checklist[i.key]).length
  const total = visibleItems.length
  const pct = Math.round((doneCount / total) * 100)
  const allDone = checklist.activation_complete

  return (
    <section
      style={{
        background: 'white',
        border: '1px solid #e0e0e0',
        borderRadius: 8,
        padding: 20,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h2 style={{ margin: 0, fontSize: 18, color: '#102a43' }}>
          {allDone ? 'Account activated' : 'Activate your account'}
        </h2>
        <span style={{ fontSize: 13, color: '#555' }}>{doneCount}/{total} complete</span>
      </div>
      <div style={{ height: 8, background: '#eee', borderRadius: 4, overflow: 'hidden', marginBottom: 16 }}>
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: allDone ? '#4caf50' : '#1976d2',
            transition: 'width 0.3s ease',
          }}
        />
      </div>

      {allDone && (
        <div
          style={{
            background: '#e8f5e9', color: '#1b5e20', padding: '10px 14px',
            borderRadius: 6, marginBottom: 12, fontSize: 14,
          }}
        >
          Your account is activated — you can now register deals.
        </div>
      )}

      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {visibleItems.map((item) => {
          const done = !!checklist[item.key]
          return (
            <li
              key={item.key}
              style={{
                display: 'flex', alignItems: 'flex-start', gap: 12,
                padding: '10px 0', borderTop: '1px solid #f0f0f0',
              }}
            >
              <Tick done={done} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, color: done ? '#444' : '#102a43', textDecoration: done ? 'line-through' : 'none' }}>
                  {item.label}
                </div>
                {!done && item.actionTo && (
                  <Link
                    to={item.actionTo}
                    style={{ fontSize: 13, color: '#1976d2', textDecoration: 'none' }}
                  >
                    {item.actionLabel} →
                  </Link>
                )}
                {!done && !item.actionTo && item.fallbackHint && (
                  <div style={{ fontSize: 12, color: '#777', marginTop: 2 }}>{item.fallbackHint}</div>
                )}
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
