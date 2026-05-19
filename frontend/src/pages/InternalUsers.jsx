import { useCallback, useEffect, useMemo, useState } from 'react'
import { useOutletContext } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const INTERNAL_ROLE_OPTIONS = [
  { value: 'system_admin', label: 'System Admin' },
  { value: 'channel_ops_admin', label: 'Channel Ops Admin' },
  { value: 'channel_manager', label: 'Channel Manager' },
  { value: 'sales_rep', label: 'Sales Rep' },
  { value: 'sales_ops', label: 'Sales Ops' },
  { value: 'finance_approver', label: 'Finance Approver' },
]

const ROLE_LABEL = Object.fromEntries(INTERNAL_ROLE_OPTIONS.map((r) => [r.value, r.label]))

const ROLE_COLOR = {
  system_admin:       { bg: '#7C3AED', fg: '#fff' },
  channel_ops_admin:  { bg: '#1A6EBB', fg: '#fff' },
  channel_manager:    { bg: '#0D9488', fg: '#fff' },
  sales_rep:          { bg: '#16A34A', fg: '#fff' },
  sales_ops:          { bg: '#EA580C', fg: '#fff' },
  finance_approver:   { bg: '#CA8A04', fg: '#fff' },
}

function RoleBadge({ role }) {
  const tone = ROLE_COLOR[role] || { bg: '#5A6478', fg: '#fff' }
  return (
    <span style={{
      background: tone.bg, color: tone.fg,
      padding: '2px 10px', borderRadius: 12,
      fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap',
    }}>
      {ROLE_LABEL[role] || role}
    </span>
  )
}

function StatusPill({ active }) {
  return (
    <span style={{
      background: active ? '#DCFCE7' : '#E5E7EB',
      color: active ? '#166534' : '#475569',
      padding: '2px 10px', borderRadius: 12,
      fontSize: 12, fontWeight: 600,
    }}>
      {active ? 'Active' : 'Disabled'}
    </span>
  )
}

function fmtDate(value) {
  if (!value) return '—'
  try { return new Date(value).toISOString().slice(0, 10) }
  catch (_) { return value }
}

function Modal({ title, children, onClose }) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      style={{
        position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.45)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50,
      }}
      onClick={onClose}
    >
      <div
        className="fp-card"
        style={{ maxWidth: 480, width: '90%', padding: 24, background: '#fff' }}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 style={{ fontSize: 18, margin: '0 0 12px' }}>{title}</h2>
        {children}
      </div>
    </div>
  )
}

// -----------------------------------------------------------------------------

function InviteUserModal({ token, onClose, onInvited }) {
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [role, setRole] = useState('channel_manager')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  async function submit(e) {
    e.preventDefault()
    setError(null); setSubmitting(true)
    try {
      const resp = await fetch(`${API}/internal/users/invite`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ email, full_name: fullName || null, role }),
      })
      const body = await resp.json().catch(() => ({}))
      if (!resp.ok) {
        if (resp.status === 409) throw new Error('A user with this email already exists')
        throw new Error(body.detail || `HTTP ${resp.status}`)
      }
      onInvited(body)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal title="Invite Internal User" onClose={onClose}>
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>Email</span>
          <input type="email" required value={email}
                 onChange={(e) => setEmail(e.target.value)}
                 style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>Full Name</span>
          <input type="text" value={fullName}
                 onChange={(e) => setFullName(e.target.value)}
                 style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>Role</span>
          <select value={role} onChange={(e) => setRole(e.target.value)}
                  style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }}>
            {INTERNAL_ROLE_OPTIONS.map((r) => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>
        </label>
        {error && <div className="fp-alert fp-alert--danger">{error}</div>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button type="button" className="fp-btn fp-btn--ghost" onClick={onClose} disabled={submitting}>Cancel</button>
          <button type="submit" className="fp-btn fp-btn--primary" disabled={submitting}>
            {submitting ? 'Sending…' : 'Send invite'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function RoleChangeModal({ token, user, onClose, onChanged }) {
  const [role, setRole] = useState(user.role)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  async function submit(e) {
    e.preventDefault()
    setError(null); setSubmitting(true)
    try {
      const resp = await fetch(`${API}/internal/users/${user.id}/role`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ role }),
      })
      const body = await resp.json().catch(() => ({}))
      if (!resp.ok) throw new Error(body.detail || `HTTP ${resp.status}`)
      onChanged(body)
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal title={`Change role — ${user.email}`} onClose={onClose}>
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>New role</span>
          <select value={role} onChange={(e) => setRole(e.target.value)}
                  style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }}>
            {INTERNAL_ROLE_OPTIONS.map((r) => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>
        </label>
        {error && <div className="fp-alert fp-alert--danger">{error}</div>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button type="button" className="fp-btn fp-btn--ghost" onClick={onClose} disabled={submitting}>Cancel</button>
          <button type="submit" className="fp-btn fp-btn--primary" disabled={submitting || role === user.role}>
            {submitting ? 'Saving…' : 'Save'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function ConfirmModal({ title, message, confirmLabel, onConfirm, onClose, danger }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  async function go() {
    setBusy(true); setError(null)
    try { await onConfirm() }
    catch (err) { setError(err.message); return }
    finally { setBusy(false) }
    onClose()
  }
  return (
    <Modal title={title} onClose={onClose}>
      <p style={{ margin: '0 0 16px', color: '#475569' }}>{message}</p>
      {error && <div className="fp-alert fp-alert--danger">{error}</div>}
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <button type="button" className="fp-btn fp-btn--ghost" onClick={onClose} disabled={busy}>Cancel</button>
        <button type="button"
                className={`fp-btn ${danger ? 'fp-btn--danger' : 'fp-btn--primary'}`}
                onClick={go} disabled={busy}>
          {busy ? 'Working…' : confirmLabel}
        </button>
      </div>
    </Modal>
  )
}

// -----------------------------------------------------------------------------

const PERMISSION_COLUMNS = [
  'Manage Users', 'Program Config', 'Approve Applications', 'Approve Deals',
  'Override Conflict', 'View Reports', 'View Partners', 'View Deals',
]

const PERMISSION_MATRIX = [
  ['system_admin',      ['Y','Y','Y','Y','Y','Y','Y','Y']],
  ['channel_ops_admin', ['—','Y','Y','Y','Y','Y','Y','Y']],
  ['channel_manager',   ['—','—','Y','Y','—','Y','Y','Y']],
  ['sales_rep',         ['—','—','—','—','—','Y','—','own']],
  ['sales_ops',         ['—','—','—','—','—','Y','—','Y']],
  ['finance_approver',  ['—','—','—','—','—','Y','—','Y']],
]

function PermissionMatrix() {
  return (
    <div className="fp-card" style={{ padding: 18, marginTop: 24 }}>
      <h2 style={{ fontSize: 16, margin: '0 0 8px' }}>Role permission matrix</h2>
      <p style={{ margin: '0 0 12px', color: '#5A6478', fontSize: 13 }}>
        Read-only reference. Edit at the source (backend role checks) until a
        program-config UI lands.
      </p>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'left', padding: '6px 8px', borderBottom: '1px solid #CBD5E1' }}>Role</th>
              {PERMISSION_COLUMNS.map((c) => (
                <th key={c} style={{ textAlign: 'center', padding: '6px 8px', borderBottom: '1px solid #CBD5E1', whiteSpace: 'nowrap' }}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {PERMISSION_MATRIX.map(([role, values]) => (
              <tr key={role}>
                <td style={{ padding: '8px', borderBottom: '1px solid #E5E7EB' }}>
                  <RoleBadge role={role} />
                </td>
                {values.map((v, i) => (
                  <td key={i} style={{ padding: '8px', borderBottom: '1px solid #E5E7EB', textAlign: 'center' }}>
                    {v === 'Y' ? '✔' : v}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// -----------------------------------------------------------------------------

export default function InternalUsers() {
  const ctx = useOutletContext() || {}
  const { payload, token } = ctx
  const selfId = payload?.sub

  const [users, setUsers] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const [inviteOpen, setInviteOpen] = useState(false)
  const [roleEditUser, setRoleEditUser] = useState(null)
  const [disableUser, setDisableUser] = useState(null)
  const [reactivateUser, setReactivateUser] = useState(null)
  const [toast, setToast] = useState(null)

  const load = useCallback(() => {
    setLoading(true); setError(null)
    const params = new URLSearchParams()
    if (roleFilter) params.set('role', roleFilter)
    if (statusFilter === 'active') params.set('is_active', 'true')
    if (statusFilter === 'disabled') params.set('is_active', 'false')
    fetch(`${API}/internal/users?${params.toString()}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (resp) => {
        const body = await resp.json().catch(() => ({}))
        if (!resp.ok) throw new Error(body.detail || `HTTP ${resp.status}`)
        return body
      })
      .then((body) => {
        setUsers(body.items || [])
        setTotal(body.total || 0)
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [token, roleFilter, statusFilter])

  useEffect(() => { load() }, [load])

  function flash(msg) {
    setToast(msg)
    setTimeout(() => setToast(null), 3500)
  }

  function onInvited(user) {
    setInviteOpen(false)
    flash(`Invite sent to ${user.email}`)
    load()
  }
  function onRoleChanged(user) {
    setRoleEditUser(null)
    flash(`Role updated for ${user.email}`)
    load()
  }
  async function doDisable() {
    const resp = await fetch(`${API}/internal/users/${disableUser.id}/disable`, {
      method: 'POST', headers: { Authorization: `Bearer ${token}` },
    })
    const body = await resp.json().catch(() => ({}))
    if (!resp.ok) throw new Error(body.detail || `HTTP ${resp.status}`)
    flash(`${disableUser.email} disabled`)
    load()
  }
  async function doReactivate() {
    const resp = await fetch(`${API}/internal/users/${reactivateUser.id}/reactivate`, {
      method: 'POST', headers: { Authorization: `Bearer ${token}` },
    })
    const body = await resp.json().catch(() => ({}))
    if (!resp.ok) throw new Error(body.detail || `HTTP ${resp.status}`)
    flash(`${reactivateUser.email} reactivated`)
    load()
  }

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: 22, margin: '0 0 4px' }}>Internal Users</h1>
          <p style={{ margin: 0, color: '#5A6478' }}>
            {total} internal user{total === 1 ? '' : 's'}.
          </p>
        </div>
        <button
          type="button"
          className="fp-btn fp-btn--primary"
          onClick={() => setInviteOpen(true)}
        >
          + Invite User
        </button>
      </div>

      <div className="fp-card" style={{ padding: 12, marginTop: 16, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#5A6478', fontWeight: 600 }}>Role</span>
          <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}
                  style={{ padding: 6, border: '1px solid #CBD5E1', borderRadius: 6, minWidth: 180 }}>
            <option value="">All</option>
            {INTERNAL_ROLE_OPTIONS.map((r) => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#5A6478', fontWeight: 600 }}>Status</span>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
                  style={{ padding: 6, border: '1px solid #CBD5E1', borderRadius: 6, minWidth: 140 }}>
            <option value="">All</option>
            <option value="active">Active</option>
            <option value="disabled">Disabled</option>
          </select>
        </label>
      </div>

      {loading && <div className="fp-card" style={{ padding: 18, marginTop: 16 }}>Loading users…</div>}
      {error && <div className="fp-alert fp-alert--danger" style={{ marginTop: 16 }}>Could not load users: {error}</div>}

      {!loading && !error && (
        <div className="fp-card" style={{ padding: 0, marginTop: 16, overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr style={{ background: '#F8FAFC' }}>
                <th style={{ textAlign: 'left', padding: '10px 12px' }}>Email</th>
                <th style={{ textAlign: 'left', padding: '10px 12px' }}>Full Name</th>
                <th style={{ textAlign: 'left', padding: '10px 12px' }}>Role</th>
                <th style={{ textAlign: 'left', padding: '10px 12px' }}>Status</th>
                <th style={{ textAlign: 'left', padding: '10px 12px' }}>Created</th>
                <th style={{ textAlign: 'left', padding: '10px 12px' }}>Last Login</th>
                <th style={{ textAlign: 'right', padding: '10px 12px' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ padding: 18, textAlign: 'center', color: '#5A6478' }}>
                    No internal users match the current filters.
                  </td>
                </tr>
              )}
              {users.map((u) => {
                const isSelf = u.id === selfId
                return (
                  <tr key={u.id} style={{ borderTop: '1px solid #E5E7EB' }}>
                    <td style={{ padding: '10px 12px' }}>{u.email}{isSelf && <span style={{ marginLeft: 6, fontSize: 11, color: '#5A6478' }}>(you)</span>}</td>
                    <td style={{ padding: '10px 12px' }}>{u.full_name || '—'}</td>
                    <td style={{ padding: '10px 12px' }}><RoleBadge role={u.role} /></td>
                    <td style={{ padding: '10px 12px' }}><StatusPill active={u.is_active} /></td>
                    <td style={{ padding: '10px 12px' }}>{fmtDate(u.created_at)}</td>
                    <td style={{ padding: '10px 12px' }}>{fmtDate(u.last_login_at)}</td>
                    <td style={{ padding: '10px 12px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                      {isSelf ? (
                        <span style={{ color: '#5A6478', fontSize: 12 }}>—</span>
                      ) : (
                        <>
                          <button type="button" className="fp-btn fp-btn--ghost fp-btn--sm"
                                  onClick={() => setRoleEditUser(u)}>
                            Change role
                          </button>
                          {u.is_active ? (
                            <button type="button" className="fp-btn fp-btn--ghost fp-btn--sm"
                                    style={{ marginLeft: 4 }}
                                    onClick={() => setDisableUser(u)}>
                              Disable
                            </button>
                          ) : (
                            <button type="button" className="fp-btn fp-btn--primary fp-btn--sm"
                                    style={{ marginLeft: 4 }}
                                    onClick={() => setReactivateUser(u)}>
                              Reactivate
                            </button>
                          )}
                        </>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <PermissionMatrix />

      {inviteOpen && (
        <InviteUserModal token={token} onClose={() => setInviteOpen(false)} onInvited={onInvited} />
      )}
      {roleEditUser && (
        <RoleChangeModal token={token} user={roleEditUser}
                         onClose={() => setRoleEditUser(null)} onChanged={onRoleChanged} />
      )}
      {disableUser && (
        <ConfirmModal
          title="Disable user"
          message={`Disable ${disableUser.email}? They will no longer be able to sign in.`}
          confirmLabel="Disable"
          danger
          onConfirm={doDisable}
          onClose={() => setDisableUser(null)}
        />
      )}
      {reactivateUser && (
        <ConfirmModal
          title="Reactivate user"
          message={`Reactivate ${reactivateUser.email}? They will be able to sign in again.`}
          confirmLabel="Reactivate"
          onConfirm={doReactivate}
          onClose={() => setReactivateUser(null)}
        />
      )}

      {toast && (
        <div
          style={{
            position: 'fixed', bottom: 24, right: 24,
            background: '#1B2236', color: '#fff',
            padding: '10px 16px', borderRadius: 8,
            fontSize: 13, fontWeight: 600, zIndex: 100,
            boxShadow: '0 8px 20px rgba(15,23,42,0.25)',
          }}
        >
          {toast}
        </div>
      )}
    </div>
  )
}
