import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

// FPRM-270 / Sprint 17 — per-criterion CTA / hint vocabulary. The criterion
// keys themselves now come from the backend ``/activation/criteria``
// endpoint, so this map only enriches each row with a friendly action.
const KEY_ACTIONS = {
  profile_complete: {
    actionLabel: 'Complete profile',
    actionTo: '/portal/profile',
  },
  documents_uploaded: {
    actionLabel: 'Upload documents',
    actionTo: '/portal/documents',
  },
  terms_signed: {
    fallbackHint: 'Your Fracttal channel manager will set this once the agreement is signed.',
  },
  contract_signed: {
    fallbackHint: 'Awaiting countersignature from Fracttal.',
  },
  baseline_training_complete: {
    fallbackHint: 'Your Fracttal channel manager will mark training complete once you finish baseline modules.',
  },
  training_complete: {
    fallbackHint: 'Your Fracttal channel manager will mark training complete once you finish baseline modules.',
  },
  training_advanced_complete: {
    fallbackHint: 'Advanced training is tracked by your Fracttal channel manager.',
  },
}

export default function ActivationChecklist({ partnerId, token: tokenProp }) {
  const [criteria, setCriteria] = useState(null)
  const [activationComplete, setActivationComplete] = useState(false)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const token = tokenProp || localStorage.getItem('token')

  useEffect(() => {
    if (!partnerId || !token) return
    setLoading(true)
    setError(null)
    fetch(`${API}/partners/${partnerId}/activation/criteria`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        if (r.ok) return r.json()
        if (r.status === 404) {
          setCriteria([])
          return null
        }
        throw new Error(`HTTP ${r.status}`)
      })
      .then((data) => {
        if (data) {
          setCriteria(Array.isArray(data.required_criteria) ? data.required_criteria : [])
          setActivationComplete(Boolean(data.activation_complete))
        }
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
  if (!criteria) return null

  const doneCount = criteria.filter((c) => c.is_met).length
  const total = criteria.length
  const pct = total > 0 ? Math.round((doneCount / total) * 100) : 0
  const allDone = activationComplete

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
        {criteria.map((c) => {
          const done = Boolean(c.is_met)
          const action = KEY_ACTIONS[c.criterion_key] || {}
          return (
            <li
              key={c.criterion_key}
              className={`fp-checklist__item${done ? ' fp-checklist__item--done' : ''}`}
            >
              <span className={`fp-checklist__tick${done ? ' fp-checklist__tick--done' : ''}`}>
                {done ? '✓' : ''}
              </span>
              <div style={{ flex: 1 }}>
                <div className={`fp-checklist__label${done ? ' fp-checklist__label--done' : ''}`}>
                  {c.description}
                </div>
                {!done && action.actionTo && (
                  <Link to={action.actionTo} className="fp-checklist__link">
                    {action.actionLabel} →
                  </Link>
                )}
                {!done && !action.actionTo && action.fallbackHint && (
                  <div style={{ fontSize: 'var(--fp-fs-xs)', color: 'var(--fp-text-secondary)', marginTop: 4 }}>
                    {action.fallbackHint}
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
