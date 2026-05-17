import { useState, useEffect, useCallback } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const FIELDS = [
  ['applicant_name', 'Applicant name'],
  ['applicant_phone', 'Phone'],
  ['applicant_title', 'Title'],
  ['legal_name', 'Legal name'],
  ['dba_name', 'DBA name'],
  ['website', 'Website'],
  ['phone', 'Company phone'],
  ['year_established', 'Year established'],
  ['employee_count', 'Employee count'],
  ['annual_revenue', 'Annual revenue'],
  ['other_software_products', 'Other software products'],
  ['cmms_experience_description', 'CMMS experience description'],
  ['sales_marketing_strategy', 'Sales & marketing strategy'],
  ['technical_support_description', 'Technical support description'],
  ['implementation_description', 'Implementation description'],
  ['partnership_goals', 'Partnership goals'],
  ['market_growth_plan', 'Market growth plan'],
  ['additional_info', 'Additional info'],
]

export default function ApplicationResume() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const id = params.get('id')
  const draftToken = params.get('draft_token')

  const [app, setApp] = useState(null)
  const [messages, setMessages] = useState([])
  const [reply, setReply] = useState('')
  const [draft, setDraft] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [sendingMsg, setSendingMsg] = useState(false)

  const load = useCallback(() => {
    if (!id || !draftToken) {
      setError('Missing application id or draft token in URL.')
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    Promise.all([
      fetch(`${API}/applications/${id}?draft_token=${draftToken}`).then((r) => {
        if (!r.ok) throw new Error(`Application: HTTP ${r.status}`)
        return r.json()
      }),
      fetch(`${API}/applications/${id}/messages?draft_token=${draftToken}`).then((r) => {
        if (!r.ok) throw new Error(`Messages: HTTP ${r.status}`)
        return r.json()
      }),
    ])
      .then(([a, m]) => {
        setApp(a)
        setMessages(Array.isArray(m) ? m : [])
        const d = {}
        for (const [k] of FIELDS) d[k] = a[k] ?? ''
        setDraft(d)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [id, draftToken])

  useEffect(() => { load() }, [load])

  const saveFields = async () => {
    setSubmitting(true)
    setError(null)
    try {
      const r = await fetch(`${API}/applications/${id}?draft_token=${draftToken}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draft),
      })
      if (!r.ok) throw new Error(`Save: HTTP ${r.status}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  const sendMessage = async () => {
    if (!reply.trim()) return
    setSendingMsg(true)
    try {
      const r = await fetch(`${API}/applications/${id}/messages?draft_token=${draftToken}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: reply.trim(), sender_email: app?.applicant_email || '' }),
      })
      if (!r.ok) throw new Error(`Send: HTTP ${r.status}`)
      setReply('')
      load()
    } catch (e) {
      setError(e.message)
    } finally {
      setSendingMsg(false)
    }
  }

  const resubmit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      // Save first then submit
      const s = await fetch(`${API}/applications/${id}?draft_token=${draftToken}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(draft),
      })
      if (!s.ok) throw new Error(`Save: HTTP ${s.status}`)

      const r = await fetch(`${API}/applications/${id}/submit?draft_token=${draftToken}`, {
        method: 'POST',
      })
      if (!r.ok) {
        const txt = await r.text()
        throw new Error(`Submit: HTTP ${r.status} ${txt}`)
      }
      navigate(`/register/confirmation?ref=${id}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <div style={{ padding: 24, fontFamily: 'system-ui, sans-serif' }}>Loading…</div>
  if (error && !app) return <div style={{ padding: 24, color: '#c0392b', fontFamily: 'system-ui, sans-serif' }}>Error: {error}</div>
  if (!app) return null

  return (
    <div style={{ maxWidth: 880, margin: '32px auto', padding: '0 20px', fontFamily: 'system-ui, sans-serif' }}>
      <h1>Resume Application</h1>

      {app.status === 'info_required' && app.info_request_message && (
        <div style={{
          background: '#fff8e1',
          border: '1px solid #ff9800',
          padding: 16,
          borderRadius: 6,
          marginBottom: 24,
        }}>
          <h3 style={{ margin: '0 0 8px 0', color: '#e65100' }}>Reviewer needs more information</h3>
          <div style={{ whiteSpace: 'pre-wrap' }}>{app.info_request_message}</div>
        </div>
      )}

      {app.status !== 'info_required' && app.status !== 'draft' && (
        <div style={{
          background: '#e3f2fd',
          border: '1px solid #2196f3',
          padding: 12,
          borderRadius: 6,
          marginBottom: 24,
        }}>
          Status: <strong>{app.status}</strong>. You can still send messages but the form is read-only.
        </div>
      )}

      <h2 style={{ marginTop: 24 }}>Update your application</h2>
      {FIELDS.map(([name, label]) => (
        <div key={name} style={{ marginTop: 12 }}>
          <label style={{ display: 'block', fontWeight: 500, fontSize: 14 }}>{label}</label>
          {name === 'partnership_goals' || name === 'market_growth_plan' || name === 'additional_info'
            || name === 'sales_marketing_strategy' || name === 'other_software_products'
            || name === 'cmms_experience_description' || name === 'technical_support_description'
            || name === 'implementation_description' ? (
            <textarea
              value={draft[name] || ''}
              onChange={(e) => setDraft({ ...draft, [name]: e.target.value })}
              rows={3}
              style={{ width: '100%', padding: 8, fontSize: 14, marginTop: 4, fontFamily: 'inherit' }}
              disabled={app.status !== 'info_required' && app.status !== 'draft'}
            />
          ) : (
            <input
              value={draft[name] || ''}
              onChange={(e) => setDraft({ ...draft, [name]: e.target.value })}
              style={{ width: '100%', padding: 8, fontSize: 14, marginTop: 4 }}
              disabled={app.status !== 'info_required' && app.status !== 'draft'}
            />
          )}
        </div>
      ))}

      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button onClick={saveFields} disabled={submitting}>Save</button>
        {(app.status === 'info_required' || app.status === 'draft') && (
          <button
            onClick={resubmit}
            disabled={submitting}
            style={{ background: '#4caf50', color: 'white', border: 'none', padding: '8px 18px', borderRadius: 4 }}
          >
            {submitting ? 'Resubmitting…' : 'Resubmit application'}
          </button>
        )}
      </div>

      <h2 style={{ marginTop: 32 }}>Messages</h2>
      <div style={{ border: '1px solid #ddd', borderRadius: 6, padding: 12, maxHeight: 320, overflowY: 'auto' }}>
        {messages.length === 0 && <p style={{ color: '#777' }}>No messages yet.</p>}
        {messages.map((m) => (
          <div key={m.id} style={{
            marginBottom: 12,
            padding: 8,
            background: m.sender_type === 'applicant' ? '#e8f5e9' : '#f5f5f5',
            borderRadius: 4,
          }}>
            <div style={{ fontSize: 12, color: '#555' }}>
              {m.sender_type === 'applicant' ? 'You' : 'Reviewer'} · {new Date(m.created_at).toLocaleString()}
            </div>
            <div style={{ whiteSpace: 'pre-wrap', marginTop: 4 }}>{m.message}</div>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 12 }}>
        <textarea
          value={reply}
          onChange={(e) => setReply(e.target.value)}
          placeholder="Reply to the reviewer…"
          rows={3}
          style={{ width: '100%', padding: 8, fontSize: 14, fontFamily: 'inherit' }}
        />
        <button onClick={sendMessage} disabled={sendingMsg || !reply.trim()} style={{ marginTop: 4 }}>
          {sendingMsg ? 'Sending…' : 'Send message'}
        </button>
      </div>

      {error && (
        <div style={{ marginTop: 16, background: '#fdecea', color: '#c0392b', padding: 12, borderRadius: 4 }}>
          {error}
        </div>
      )}
    </div>
  )
}
