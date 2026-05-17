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
    actionLabel: null,
    actionTo: null,
    fallbackHint: 'Your Fracttal channel manager will set this once the agreement is signed.',
  },
]

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

  if (loading) {
    return <div className="fp-card" style={{ color: 'var(--fp-text-secondary)', fontSize: 'var(--fp-fs-sm)' }}>Loading activation status…</div>
  }
  if (error) {
    return (
      <div className="fp-alert fp-alert--danger">
        Could not load activation checklist: {error}
      </div>
    )
  }
  if (!checklist) return null

  const doneCount = ITEMS.filter((i) => checklist[i.key]).length
  const total = ITEMS.length
  const pct = Math.round((doneCount / total) * 100)
  const allDone = checklist.activation_complete

  return (
    <section className="fp-card">
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h2 className="fp-section-title" style={{ margin: 0 }}>
          {allDone ? 'Account activated' : 'Activate your account'}
        </h2>
        <span style={{ fontSize: 'var(--fp-fs-sm)', color: 'var(--fp-text-secondary)' }}>
          {doneCount} / {total}
        </span>
      </div>
      <div className="fp-progress" style={{ marginBottom: 16 }}>
        <div className={`fp-progress__fill${allDone ? ' fp-progress__fill--success' : ''}`} style={{ width: `${pct}%` }} />
      </div>

      {allDone && (
        <div className="fp-alert fp-alert--success" style={{ marginBottom: 12 }}>
          Your account is activated — you can now register deals.
        </div>
      )}

      <ul style={{ listStyle: 'none', padding: 0, margin: '8px 0 0 16px' }}>
        {ITEMS.map((item) => {
          const done = !!checklist[item.key]
          return (
            <li
              key={item.key}
              className={`fp-checklist__item${done ? ' fp-checklist__item--done' : ''}`}
            >
              <span className={`fp-checklist__tick${done ? ' fp-checklist__tick--done' : ''}`}>
                {done ? '✓' : ''}
              </span>
              <div style={{ flex: 1 }}>
                <div className={`fp-checklist__label${done ? ' fp-checklist__label--done' : ''}`}>
                  {item.label}
                </div>
                {!done && item.actionTo && (
                  <Link to={item.actionTo} className="fp-checklist__link">
                    {item.actionLabel} →
                  </Link>
                )}
                {!done && !item.actionTo && item.fallbackHint && (
                  <div style={{ fontSize: 'var(--fp-fs-xs)', color: 'var(--fp-text-secondary)', marginTop: 4 }}>
                    {item.fallbackHint}
                  </div>
                )}
              </div>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
