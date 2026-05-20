import { useCallback, useEffect, useState } from 'react'
import { useOutletContext } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const PARTNER_ROLE_OPTIONS = [
  { value: 'partner_user',  label: 'Partner User' },
  { value: 'partner_admin', label: 'Partner Admin' },
]
const PARTNER_ROLE_LABEL = Object.fromEntries(PARTNER_ROLE_OPTIONS.map((r) => [r.value, r.label]))
const PARTNER_ROLE_COLOR = {
  partner_admin: { bg: '#1A6EBB', fg: '#fff' },
  partner_user:  { bg: '#0D9488', fg: '#fff' },
}

function RoleBadge({ role }) {
  const tone = PARTNER_ROLE_COLOR[role] || { bg: '#5A6478', fg: '#fff' }
  return (
    <span style={{
      background: tone.bg, color: tone.fg,
      padding: '2px 10px', borderRadius: 12,
      fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap',
    }}>
      {PARTNER_ROLE_LABEL[role] || role}
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

function InviteModal({ token, orgs, onClose, onInvited }) {
  const [email, setEmail] = useState('')
  const [orgId, setOrgId] = useState(orgs[0]?.id || '')
  const [invitedRole, setInvitedRole] = useState('partner_user')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function submit(e) {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      const resp = await fetch(`${API}/internal/partner-users/invite`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ email, partner_org_id: orgId, invited_role: invitedRole }),
      })
      const body = await resp.json().catch(() => ({}))
      if (!resp.ok) throw new Error(body.detail || `HTTP ${resp.status}`)
      onInvited(body)
    } catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  return (
    <Modal title="Invite Partner User" onClose={onClose}>
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>Email</span>
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                 style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>Partner Organisation</span>
          <select required value={orgId} onChange={(e) => setOrgId(e.target.value)}
                  style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }}>
            <option value="">— select —</option>
            {orgs.map((o) => (
              <option key={o.id} value={o.id}>{o.legal_name}</option>
            ))}
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>Role</span>
          <select value={invitedRole} onChange={(e) => setInvitedRole(e.target.value)}
                  style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }}>
            {PARTNER_ROLE_OPTIONS.map((r) => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>
        </label>
        {error && <div className="fp-alert fp-alert--danger">{error}</div>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button type="button" className="fp-btn fp-btn--ghost" onClick={onClose} disabled={busy}>Cancel</button>
          <button type="submit" className="fp-btn fp-btn--primary" disabled={busy || !orgId}>
            {busy ? 'Sending…' : 'Send invite'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function RoleChangeModal({ token, user, onClose, onChanged }) {
  const [role, setRole] = useState(user.role)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  async function submit(e) {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      const resp = await fetch(`${API}/internal/partner-users/${user.id}/role`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ role }),
      })
      const body = await resp.json().catch(() => ({}))
      if (!resp.ok) throw new Error(body.detail || `HTTP ${resp.status}`)
      onChanged(body)
    } catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }
  return (
    <Modal title={`Change role — ${user.email}`} onClose={onClose}>
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>New role</span>
          <select value={role} onChange={(e) => setRole(e.target.value)}
                  style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }}>
            {PARTNER_ROLE_OPTIONS.map((r) => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>
        </label>
        {error && <div className="fp-alert fp-alert--danger">{error}</div>}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button type="button" className="fp-btn fp-btn--ghost" onClick={onClose} disabled={busy}>Cancel</button>
          <button type="submit" className="fp-btn fp-btn--primary" disabled={busy || role === user.role}>
            {busy ? 'Saving…' : 'Save'}
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

export default function PartnerUserManagement() {
  const [exporting, setExporting] = useState(false)
  async function exportCSV() {
    setExporting(true)
    try {
      const token = localStorage.getItem('token')
      const r = await fetch(`${API}/internal/partner-users?export=csv`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'partner_users_export.csv'
      document.body.appendChild(a); a.click(); document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('CSV export error:', e)
    } finally {
      setExporting(false)
    }
  }

  const ctx = useOutletContext() || {}
  const { token } = ctx

  const [orgs, setOrgs] = useState([])
  const [users, setUsers] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [orgFilter, setOrgFilter] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  const [inviteOpen, setInviteOpen] = useState(false)
  const [roleEditUser, setRoleEditUser] = useState(null)
  const [disableUser, setDisableUser] = useState(null)
  const [reactivateUser, setReactivateUser] = useState(null)
  const [toast, setToast] = useState(null)

  // Org list for the filter + invite modal
  useEffect(() => {
    fetch(`${API}/partners`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async (r) => {
        const b = await r.json().catch(() => ({}))
        if (!r.ok) throw new Error(b.detail || `HTTP ${r.status}`)
        return b
      })
      .then((b) => {
        const items = Array.isArray(b) ? b : (b.items || [])
        setOrgs(items.map((o) => ({ id: o.id, legal_name: o.legal_name })))
      })
      .catch(() => setOrgs([]))
  }, [token])

  const load = useCallback(() => {
    setLoading(true); setError(null)
    const params = new URLSearchParams()
    if (orgFilter) params.set('partner_org_id', orgFilter)
    if (roleFilter) params.set('role', roleFilter)
    if (statusFilter === 'active') params.set('is_active', 'true')
    if (statusFilter === 'disabled') params.set('is_active', 'false')
    fetch(`${API}/internal/partner-users?${params.toString()}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (r) => {
        const b = await r.json().catch(() => ({}))
        if (!r.ok) throw new Error(b.detail || `HTTP ${r.status}`)
        return b
      })
      .then((b) => { setUsers(b.items || []); setTotal(b.total || 0) })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [token, orgFilter, roleFilter, statusFilter])

  useEffect(() => { load() }, [load])

  function flash(msg) {
    setToast(msg)
    setTimeout(() => setToast(null), 3500)
  }

  function onInvited(body) {
    setInviteOpen(false)
    flash(`Invite sent to ${body.email}`)
    load()
  }
  function onRoleChanged(body) {
    setRoleEditUser(null)
    flash(`Role updated for ${body.email}`)
    load()
  }
  async function doDisable() {
    const resp = await fetch(`${API}/internal/partner-users/${disableUser.id}/disable`, {
      method: 'POST', headers: { Authorization: `Bearer ${token}` },
    })
    const b = await resp.json().catch(() => ({}))
    if (!resp.ok) throw new Error(b.detail || `HTTP ${resp.status}`)
    flash(`${disableUser.email} disabled`); load()
  }
  async function doReactivate() {
    const resp = await fetch(`${API}/internal/partner-users/${reactivateUser.id}/reactivate`, {
      method: 'POST', headers: { Authorization: `Bearer ${token}` },
    })
    const b = await resp.json().catch(() => ({}))
    if (!resp.ok) throw new Error(b.detail || `HTTP ${resp.status}`)
    flash(`${reactivateUser.email} reactivated`); load()
  }

  return (
    <div style={{ padding: 24 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: 22, margin: '0 0 4px' }}>Partner Users</h1>
          <p style={{ margin: 0, color: '#5A6478' }}>
            {total} partner user{total === 1 ? '' : 's'} across all organisations.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button type="button" onClick={exportCSV} disabled={exporting} style={{ fontSize: '0.75rem', padding: '4px 10px', border: '1px solid #CBD5E0', borderRadius: 4, backgroundColor: 'white', color: '#718096', cursor: 'pointer', fontWeight: 400 }}>{exporting ? 'Exporting...' : 'Export CSV'}</button>
          <button type="button" className="fp-btn fp-btn--primary"
                  onClick={() => setInviteOpen(true)} disabled={orgs.length === 0}>
            + Invite User
          </button>
        </div>
      </div>

      <div className="fp-card" style={{ padding: 12, marginTop: 16, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#5A6478', fontWeight: 600 }}>Partner</span>
          <select value={orgFilter} onChange={(e) => setOrgFilter(e.target.value)}
                  style={{ padding: 6, border: '1px solid #CBD5E1', borderRadius: 6, minWidth: 220 }}>
            <option value="">All partners</option>
            {orgs.map((o) => (
              <option key={o.id} value={o.id}>{o.legal_name}</option>
            ))}
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#5A6478', fontWeight: 600 }}>Role</span>
          <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}
                  style={{ padding: 6, border: '1px solid #CBD5E1', borderRadius: 6, minWidth: 160 }}>
            <option value="">All</option>
            {PARTNER_ROLE_OPTIONS.map((r) => (
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

      {loading && <div className="fp-card" style={{ padding: 18, marginTop: 16 }}>Loading partner users…</div>}
      {error && <div className="fp-alert fp-alert--danger" style={{ marginTop: 16 }}>Could not load partner users: {error}</div>}

      {!loading && !error && (
        <div className="fp-card" style={{ padding: 0, marginTop: 16, overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr style={{ background: '#F8FAFC' }}>
                <th style={{ textAlign: 'left', padding: '10px 12px' }}>Email</th>
                <th style={{ textAlign: 'left', padding: '10px 12px' }}>Full Name</th>
                <th style={{ textAlign: 'left', padding: '10px 12px' }}>Role</th>
                <th style={{ textAlign: 'left', padding: '10px 12px' }}>Partner Org</th>
                <th style={{ textAlign: 'left', padding: '10px 12px' }}>Status</th>
                <th style={{ textAlign: 'left', padding: '10px 12px' }}>Created</th>
                <th style={{ textAlign: 'right', padding: '10px 12px' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 && (
                <tr>
                  <td colSpan={7} style={{ padding: 18, textAlign: 'center', color: '#5A6478' }}>
                    No partner users match the current filters.
                  </td>
                </tr>
              )}
              {users.map((u) => (
                <tr key={u.id} style={{ borderTop: '1px solid #E5E7EB' }}>
                  <td style={{ padding: '10px 12px' }}>{u.email}</td>
                  <td style={{ padding: '10px 12px' }}>{u.full_name || '—'}</td>
                  <td style={{ padding: '10px 12px' }}><RoleBadge role={u.role} /></td>
                  <td style={{ padding: '10px 12px' }}>{u.partner_org_name || '—'}</td>
                  <td style={{ padding: '10px 12px' }}><StatusPill active={u.is_active} /></td>
                  <td style={{ padding: '10px 12px' }}>{fmtDate(u.created_at)}</td>
                  <td style={{ padding: '10px 12px', textAlign: 'right', whiteSpace: 'nowrap' }}>
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
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {inviteOpen && (
        <InviteModal token={token} orgs={orgs}
                     onClose={() => setInviteOpen(false)} onInvited={onInvited} />
      )}
      {roleEditUser && (
        <RoleChangeModal token={token} user={roleEditUser}
                         onClose={() => setRoleEditUser(null)} onChanged={onRoleChanged} />
      )}
      {disableUser && (
        <ConfirmModal
          title="Disable partner user"
          message={`Disable ${disableUser.email}? They will no longer be able to sign in.`}
          confirmLabel="Disable"
          danger
          onConfirm={doDisable}
          onClose={() => setDisableUser(null)}
        />
      )}
      {reactivateUser && (
        <ConfirmModal
          title="Reactivate partner user"
          message={`Reactivate ${reactivateUser.email}? They will be able to sign in again.`}
          confirmLabel="Reactivate"
          onConfirm={doReactivate}
          onClose={() => setReactivateUser(null)}
        />
      )}

      {toast && (
        <div style={{
          position: 'fixed', bottom: 24, right: 24,
          background: '#1B2236', color: '#fff',
          padding: '10px 16px', borderRadius: 8,
          fontSize: 13, fontWeight: 600, zIndex: 100,
          boxShadow: '0 8px 20px rgba(15,23,42,0.25)',
        }}>
          {toast}
        </div>
      )}
    </div>
  )
}
