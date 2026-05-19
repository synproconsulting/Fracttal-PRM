import { useCallback, useEffect, useMemo, useState } from 'react'
import { useOutletContext } from 'react-router-dom'

const API = (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_URL)
  || 'https://fracttal-prm-backend-production.up.railway.app'

const TABS = [
  { key: 'workflow',   label: 'Approval Workflow' },
  { key: 'tiers',      label: 'Partner Tiers' },
  { key: 'criteria',   label: 'Activation Checklist' },
]

const ROLE_OPTIONS = [
  { value: 'channel_ops_admin', label: 'Channel Ops Admin' },
  { value: 'channel_manager',   label: 'Channel Manager' },
  { value: 'system_admin',      label: 'System Admin' },
  { value: 'finance_approver',  label: 'Finance Approver' },
]

const RULE_TYPE_LABEL = {
  min_deals_approved:     'Min Deals Approved',
  min_revenue:            'Min Revenue',
  required_certification: 'Required Certification',
  min_win_rate:           'Min Win Rate',
}

function humaniseKey(s) {
  if (!s) return ''
  return s.split('_').map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

function authHeader(token) {
  return { Authorization: `Bearer ${token}` }
}

async function call(token, method, path, body) {
  const r = await fetch(`${API}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...authHeader(token) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  const text = await r.text()
  const data = text ? JSON.parse(text) : null
  if (!r.ok) throw new Error((data && data.detail) || `HTTP ${r.status}`)
  return data
}

function Toast({ message }) {
  if (!message) return null
  return (
    <div style={{
      position: 'fixed', bottom: 24, right: 24, zIndex: 1100,
      background: '#166534', color: '#fff',
      padding: '10px 16px', borderRadius: 8,
      boxShadow: '0 8px 20px rgba(15,23,42,0.2)', fontSize: 14, fontWeight: 600,
    }}>
      {message}
    </div>
  )
}

function Modal({ title, onClose, children }) {
  return (
    <div role="dialog" aria-modal="true" style={{
      position: 'fixed', inset: 0, background: 'rgba(15,23,42,0.45)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }}>
      <div style={{
        background: '#fff', borderRadius: 10, padding: 24,
        maxWidth: 520, width: 'calc(100% - 32px)',
        boxShadow: '0 10px 30px rgba(15,23,42,0.2)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h2 style={{ margin: 0, fontSize: 18 }}>{title}</h2>
          <button type="button" onClick={onClose} aria-label="Close"
                  style={{ background: 'transparent', border: 'none', fontSize: 22, cursor: 'pointer', color: '#475569' }}>×</button>
        </div>
        {children}
      </div>
    </div>
  )
}

// ---- Tab 1 — Approval Workflow ---------------------------------------------

function WorkflowPanel({ token, workflowType, title, onUpdate, onError }) {
  const [steps, setSteps] = useState([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)
  const [draftName, setDraftName] = useState('')
  const [draftRole, setDraftRole] = useState('channel_ops_admin')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await call(token, 'GET', `/internal/config/approval-steps?workflow_type=${workflowType}`)
      setSteps(data.items || [])
    } catch (err) { onError(err.message) }
    finally { setLoading(false) }
  }, [token, workflowType, onError])

  useEffect(() => { load() }, [load])

  async function patchStep(step, patch) {
    try {
      await call(token, 'PATCH', `/internal/config/approval-steps/${step.id}`, patch)
      onUpdate('Approval step updated')
      load()
    } catch (err) { onError(err.message) }
  }

  async function deleteStep(step) {
    try {
      await call(token, 'DELETE', `/internal/config/approval-steps/${step.id}`)
      onUpdate('Approval step removed')
      load()
    } catch (err) { onError(err.message) }
  }

  async function moveStep(step, direction) {
    const idx = steps.findIndex((s) => s.id === step.id)
    const swapIdx = direction === 'up' ? idx - 1 : idx + 1
    if (swapIdx < 0 || swapIdx >= steps.length) return
    const other = steps[swapIdx]
    try {
      await call(token, 'PATCH', `/internal/config/approval-steps/${step.id}`, { step_order: other.step_order })
      await call(token, 'PATCH', `/internal/config/approval-steps/${other.id}`, { step_order: step.step_order })
      onUpdate('Step reordered')
      load()
    } catch (err) { onError(err.message) }
  }

  async function addStep(e) {
    e.preventDefault()
    if (!draftName.trim()) return
    setAdding(true)
    try {
      const order = (steps.reduce((m, s) => Math.max(m, s.step_order), 0) || 0) + 1
      await call(token, 'POST', '/internal/config/approval-steps', {
        workflow_type: workflowType, step_order: order,
        step_name: draftName.trim(), required_role: draftRole,
      })
      setDraftName(''); setDraftRole('channel_ops_admin')
      onUpdate('Approval step added')
      load()
    } catch (err) { onError(err.message) }
    finally { setAdding(false) }
  }

  return (
    <section className="fp-card" style={{ marginBottom: 24 }}>
      <h3 style={{ margin: '0 0 12px', fontSize: 16 }}>{title}</h3>
      {loading ? <p style={{ color: '#5A6478' }}>Loading…</p> : (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
          <thead>
            <tr style={{ background: '#F8FAFC' }}>
              <th style={{ textAlign: 'left', padding: '8px 10px', width: 60 }}>Order</th>
              <th style={{ textAlign: 'left', padding: '8px 10px' }}>Step name</th>
              <th style={{ textAlign: 'left', padding: '8px 10px', width: 200 }}>Required role</th>
              <th style={{ textAlign: 'left', padding: '8px 10px', width: 100 }}>Active</th>
              <th style={{ textAlign: 'right', padding: '8px 10px', width: 140 }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {steps.length === 0 && (
              <tr><td colSpan={5} style={{ padding: 14, textAlign: 'center', color: '#5A6478' }}>
                No steps yet — add one below.
              </td></tr>
            )}
            {steps.map((s, i) => (
              <tr key={s.id} style={{ borderTop: '1px solid #E5E7EB' }}>
                <td style={{ padding: '8px 10px' }}>
                  <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                    <button type="button" onClick={() => moveStep(s, 'up')}   disabled={i === 0}
                            style={{ padding: '0 6px', border: '1px solid #CBD5E1', background: '#fff', borderRadius: 4, cursor: i === 0 ? 'default' : 'pointer' }}>↑</button>
                    <button type="button" onClick={() => moveStep(s, 'down')} disabled={i === steps.length - 1}
                            style={{ padding: '0 6px', border: '1px solid #CBD5E1', background: '#fff', borderRadius: 4, cursor: i === steps.length - 1 ? 'default' : 'pointer' }}>↓</button>
                    <span style={{ marginLeft: 6 }}>{s.step_order}</span>
                  </div>
                </td>
                <td style={{ padding: '8px 10px' }}>
                  <input
                    defaultValue={s.step_name}
                    onBlur={(e) => { if (e.target.value !== s.step_name) patchStep(s, { step_name: e.target.value }) }}
                    style={{ border: '1px solid transparent', padding: 4, width: '100%' }}
                    onFocus={(e) => (e.target.style.border = '1px solid #CBD5E1')}
                    onMouseOut={(e) => { if (document.activeElement !== e.target) e.target.style.border = '1px solid transparent' }}
                  />
                </td>
                <td style={{ padding: '8px 10px' }}>
                  <select value={s.required_role}
                          onChange={(e) => patchStep(s, { required_role: e.target.value })}
                          style={{ padding: 4, border: '1px solid #CBD5E1', borderRadius: 4 }}>
                    {ROLE_OPTIONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                  </select>
                </td>
                <td style={{ padding: '8px 10px' }}>
                  <input type="checkbox" checked={s.is_active}
                         onChange={(e) => patchStep(s, { is_active: e.target.checked })} />
                </td>
                <td style={{ padding: '8px 10px', textAlign: 'right' }}>
                  <button type="button" onClick={() => deleteStep(s)}
                          style={{ background: 'transparent', border: '1px solid #991B1B', color: '#991B1B',
                                   padding: '4px 10px', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <form onSubmit={addStep} style={{ display: 'flex', gap: 8, marginTop: 12, alignItems: 'flex-end' }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4, flex: 1 }}>
          <span style={{ fontSize: 12, color: '#5A6478', fontWeight: 600 }}>New step name</span>
          <input value={draftName} onChange={(e) => setDraftName(e.target.value)}
                 placeholder="e.g. Channel Manager Review"
                 style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#5A6478', fontWeight: 600 }}>Required role</span>
          <select value={draftRole} onChange={(e) => setDraftRole(e.target.value)}
                  style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }}>
            {ROLE_OPTIONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </label>
        <button type="submit" className="fp-btn fp-btn--primary" disabled={adding || !draftName.trim()}>
          Add step
        </button>
      </form>
    </section>
  )
}

function ApprovalWorkflowTab({ token, onUpdate, onError }) {
  return (
    <>
      <WorkflowPanel token={token} workflowType="partner_application" title="Partner Application Workflow"
                     onUpdate={onUpdate} onError={onError} />
      <WorkflowPanel token={token} workflowType="deal_registration"   title="Deal Registration Workflow"
                     onUpdate={onUpdate} onError={onError} />
    </>
  )
}

// ---- Tab 2 — Partner Tiers -------------------------------------------------

function TiersTab({ token, onUpdate, onError }) {
  const [tiers, setTiers] = useState([])
  const [loading, setLoading] = useState(true)
  const [editingTier, setEditingTier] = useState(null)   // {tier?} - null means closed
  const [addRuleFor, setAddRuleFor] = useState(null)     // {tierId}

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const data = await call(token, 'GET', '/internal/config/tiers')
      setTiers(data.items || [])
    } catch (err) { onError(err.message) }
    finally { setLoading(false) }
  }, [token, onError])

  useEffect(() => { load() }, [load])

  async function deleteRule(tierId, ruleId) {
    try {
      await call(token, 'DELETE', `/internal/config/tiers/${tierId}/eligibility-rules/${ruleId}`)
      onUpdate('Eligibility rule removed')
      load()
    } catch (err) { onError(err.message) }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
        <button type="button" className="fp-btn fp-btn--primary"
                onClick={() => setEditingTier({ tier: null })}>+ Add Tier</button>
      </div>
      {loading ? <p style={{ color: '#5A6478' }}>Loading…</p> : (
        <div style={{ display: 'grid', gap: 16 }}>
          {tiers.length === 0 && (
            <div className="fp-card" style={{ padding: 20, textAlign: 'center', color: '#5A6478' }}>
              No tiers configured.
            </div>
          )}
          {tiers.map((t) => (
            <div key={t.id} className="fp-card" style={{ padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <h3 style={{ margin: 0, fontSize: 16 }}>{t.tier_name}</h3>
                <span style={{
                  background: '#E0E7FF', color: '#3730A3', padding: '2px 8px',
                  borderRadius: 10, fontSize: 12, fontWeight: 600,
                }}>Rank {t.tier_rank}</span>
                <span style={{
                  background: t.is_active ? '#DCFCE7' : '#E5E7EB',
                  color: t.is_active ? '#166534' : '#475569',
                  padding: '2px 8px', borderRadius: 10, fontSize: 12, fontWeight: 600,
                }}>{t.is_active ? 'Active' : 'Inactive'}</span>
                <button type="button" onClick={() => setEditingTier({ tier: t })}
                        style={{ marginLeft: 'auto', background: 'transparent', border: '1px solid #CBD5E1',
                                 padding: '4px 10px', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}>
                  Edit
                </button>
              </div>
              {t.description && (
                <p style={{ margin: '8px 0 12px', color: '#475569', fontSize: 14 }}>{t.description}</p>
              )}
              <div style={{ marginTop: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <strong style={{ fontSize: 13, color: '#5A6478' }}>Eligibility rules</strong>
                  <button type="button" onClick={() => setAddRuleFor({ tierId: t.id })}
                          style={{ background: 'transparent', border: '1px solid #1A6EBB', color: '#1A6EBB',
                                   padding: '3px 10px', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}>
                    + Add Rule
                  </button>
                </div>
                {(t.eligibility_rules || []).length === 0 ? (
                  <p style={{ margin: 0, color: '#94A3B8', fontSize: 13 }}>No rules defined.</p>
                ) : (
                  <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
                    {t.eligibility_rules.map((r) => (
                      <li key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 8,
                                                padding: '6px 0', borderTop: '1px solid #F1F5F9' }}>
                        <span style={{ fontSize: 13, fontWeight: 600 }}>{RULE_TYPE_LABEL[r.rule_type] || r.rule_type}</span>
                        <span style={{ fontSize: 13, color: '#475569' }}>= {r.rule_value}</span>
                        {r.description && <span style={{ fontSize: 12, color: '#94A3B8' }}>· {r.description}</span>}
                        <button type="button" onClick={() => deleteRule(t.id, r.id)}
                                style={{ marginLeft: 'auto', background: 'transparent', border: 'none',
                                         color: '#991B1B', fontSize: 12, cursor: 'pointer' }}>Delete</button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {editingTier && (
        <TierFormModal
          token={token}
          tier={editingTier.tier}
          onClose={() => setEditingTier(null)}
          onSaved={(msg) => { setEditingTier(null); onUpdate(msg); load() }}
          onError={onError}
        />
      )}
      {addRuleFor && (
        <AddRuleModal
          token={token}
          tierId={addRuleFor.tierId}
          onClose={() => setAddRuleFor(null)}
          onSaved={(msg) => { setAddRuleFor(null); onUpdate(msg); load() }}
          onError={onError}
        />
      )}
    </div>
  )
}

function TierFormModal({ token, tier, onClose, onSaved, onError }) {
  const editing = !!tier
  const [name, setName] = useState(tier?.tier_name || '')
  const [rank, setRank] = useState(tier?.tier_rank || 1)
  const [description, setDescription] = useState(tier?.description || '')
  const [saving, setSaving] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setSaving(true)
    try {
      if (editing) {
        await call(token, 'PATCH', `/internal/config/tiers/${tier.id}`,
          { tier_name: name, tier_rank: Number(rank), description: description || null })
        onSaved('Tier updated')
      } else {
        await call(token, 'POST', '/internal/config/tiers',
          { tier_name: name, tier_rank: Number(rank), description: description || null })
        onSaved('Tier created')
      }
    } catch (err) { onError(err.message) }
    finally { setSaving(false) }
  }

  return (
    <Modal title={editing ? `Edit ${tier.tier_name}` : 'Add Partner Tier'} onClose={onClose}>
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#5A6478', fontWeight: 600 }}>Tier name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} required
                 style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#5A6478', fontWeight: 600 }}>Rank (1 = lowest)</span>
          <input type="number" min="1" value={rank} onChange={(e) => setRank(e.target.value)} required
                 style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#5A6478', fontWeight: 600 }}>Description</span>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3}
                    style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
        </label>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button type="button" className="fp-btn fp-btn--ghost" onClick={onClose} disabled={saving}>Cancel</button>
          <button type="submit" className="fp-btn fp-btn--primary" disabled={saving}>
            {saving ? 'Saving…' : (editing ? 'Save changes' : 'Create tier')}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function AddRuleModal({ token, tierId, onClose, onSaved, onError }) {
  const [ruleType, setRuleType] = useState('min_deals_approved')
  const [ruleValue, setRuleValue] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setSaving(true)
    try {
      await call(token, 'POST', `/internal/config/tiers/${tierId}/eligibility-rules`,
        { rule_type: ruleType, rule_value: ruleValue, description: description || null })
      onSaved('Eligibility rule added')
    } catch (err) { onError(err.message) }
    finally { setSaving(false) }
  }

  return (
    <Modal title="Add Eligibility Rule" onClose={onClose}>
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#5A6478', fontWeight: 600 }}>Rule type</span>
          <select value={ruleType} onChange={(e) => setRuleType(e.target.value)}
                  style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }}>
            {Object.entries(RULE_TYPE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#5A6478', fontWeight: 600 }}>Value</span>
          <input value={ruleValue} onChange={(e) => setRuleValue(e.target.value)} required
                 style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#5A6478', fontWeight: 600 }}>Description (optional)</span>
          <input value={description} onChange={(e) => setDescription(e.target.value)}
                 style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
        </label>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button type="button" className="fp-btn fp-btn--ghost" onClick={onClose} disabled={saving}>Cancel</button>
          <button type="submit" className="fp-btn fp-btn--primary" disabled={saving}>
            {saving ? 'Saving…' : 'Add rule'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

// ---- Tab 3 — Activation Checklist ------------------------------------------

function ActivationTab({ token, onUpdate, onError }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [showInactive, setShowInactive] = useState(false)
  const [adding, setAdding] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const qs = showInactive ? '' : '?is_active=true'
      const data = await call(token, 'GET', `/internal/config/activation-criteria${qs}`)
      setRows(data.items || [])
    } catch (err) { onError(err.message) }
    finally { setLoading(false) }
  }, [token, showInactive, onError])

  useEffect(() => { load() }, [load])

  async function patch(crit, body, msg) {
    try {
      await call(token, 'PATCH', `/internal/config/activation-criteria/${crit.id}`, body)
      onUpdate(msg)
      load()
    } catch (err) { onError(err.message) }
  }

  async function softDelete(crit) {
    try {
      await call(token, 'DELETE', `/internal/config/activation-criteria/${crit.id}`)
      onUpdate('Criterion deactivated')
      load()
    } catch (err) { onError(err.message) }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14 }}>
          <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} />
          Show inactive
        </label>
        <button type="button" className="fp-btn fp-btn--primary" onClick={() => setAdding(true)}>
          + Add Criterion
        </button>
      </div>
      {loading ? <p style={{ color: '#5A6478' }}>Loading…</p> : (
        <div className="fp-card" style={{ padding: 0, overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
            <thead>
              <tr style={{ background: '#F8FAFC' }}>
                <th style={{ textAlign: 'left',  padding: '10px 12px' }}>Criterion</th>
                <th style={{ textAlign: 'left',  padding: '10px 12px' }}>Category</th>
                <th style={{ textAlign: 'left',  padding: '10px 12px' }}>Tier</th>
                <th style={{ textAlign: 'left',  padding: '10px 12px' }}>Required</th>
                <th style={{ textAlign: 'left',  padding: '10px 12px' }}>Active</th>
                <th style={{ textAlign: 'left',  padding: '10px 12px' }}>Description</th>
                <th style={{ textAlign: 'right', padding: '10px 12px' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr><td colSpan={7} style={{ padding: 18, textAlign: 'center', color: '#5A6478' }}>
                  No activation criteria.
                </td></tr>
              )}
              {rows.map((c) => (
                <tr key={c.id} style={{ borderTop: '1px solid #E5E7EB' }}>
                  <td style={{ padding: '8px 12px', fontWeight: 600 }}>{humaniseKey(c.criterion_key)}</td>
                  <td style={{ padding: '8px 12px', color: '#475569' }}>{c.partner_category_code || 'All'}</td>
                  <td style={{ padding: '8px 12px', color: '#475569' }}>{c.tier_name || 'All'}</td>
                  <td style={{ padding: '8px 12px' }}>
                    <input type="checkbox" checked={c.is_required}
                           onChange={(e) => patch(c, { is_required: e.target.checked }, 'Criterion updated')} />
                  </td>
                  <td style={{ padding: '8px 12px' }}>
                    <input type="checkbox" checked={c.is_active}
                           onChange={(e) => patch(c, { is_active: e.target.checked }, 'Criterion updated')} />
                  </td>
                  <td style={{ padding: '8px 12px', color: '#475569' }}>{c.description || '—'}</td>
                  <td style={{ padding: '8px 12px', textAlign: 'right' }}>
                    <button type="button" onClick={() => softDelete(c)}
                            style={{ background: 'transparent', border: '1px solid #991B1B', color: '#991B1B',
                                     padding: '4px 10px', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}>
                      Deactivate
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {adding && (
        <AddCriterionModal
          token={token}
          onClose={() => setAdding(false)}
          onSaved={(msg) => { setAdding(false); onUpdate(msg); load() }}
          onError={onError}
        />
      )}
    </div>
  )
}

function AddCriterionModal({ token, onClose, onSaved, onError }) {
  const [criterionKey, setCriterionKey] = useState('')
  const [category, setCategory] = useState('')
  const [tier, setTier] = useState('')
  const [isRequired, setIsRequired] = useState(true)
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setSaving(true)
    try {
      await call(token, 'POST', '/internal/config/activation-criteria', {
        criterion_key: criterionKey.trim(),
        partner_category_code: category || null,
        tier_name: tier || null,
        is_required: isRequired,
        description: description || null,
      })
      onSaved('Activation criterion created')
    } catch (err) { onError(err.message) }
    finally { setSaving(false) }
  }

  return (
    <Modal title="Add Activation Criterion" onClose={onClose}>
      <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#5A6478', fontWeight: 600 }}>Criterion key (snake_case)</span>
          <input value={criterionKey} onChange={(e) => setCriterionKey(e.target.value)} required
                 placeholder="e.g. compliance_review_done"
                 style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#5A6478', fontWeight: 600 }}>Category (blank = all)</span>
          <select value={category} onChange={(e) => setCategory(e.target.value)}
                  style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }}>
            <option value="">All categories</option>
            <option value="master">Master</option>
            <option value="promotor">Promotor</option>
            <option value="reseller">Reseller</option>
          </select>
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#5A6478', fontWeight: 600 }}>Tier (blank = all)</span>
          <input value={tier} onChange={(e) => setTier(e.target.value)} placeholder="e.g. Gold"
                 style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input type="checkbox" checked={isRequired} onChange={(e) => setIsRequired(e.target.checked)} />
          Required
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={{ fontSize: 12, color: '#5A6478', fontWeight: 600 }}>Description</span>
          <input value={description} onChange={(e) => setDescription(e.target.value)}
                 style={{ padding: 8, border: '1px solid #CBD5E1', borderRadius: 6 }} />
        </label>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button type="button" className="fp-btn fp-btn--ghost" onClick={onClose} disabled={saving}>Cancel</button>
          <button type="submit" className="fp-btn fp-btn--primary" disabled={saving}>
            {saving ? 'Saving…' : 'Create criterion'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

// ---- Root page -------------------------------------------------------------

export default function ProgramConfig() {
  const ctx = useOutletContext() || {}
  const { token } = ctx
  const [active, setActive] = useState('workflow')
  const [toast, setToast] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 3000)
    return () => clearTimeout(t)
  }, [toast])

  const onUpdate = (msg) => { setToast(msg); setError(null) }
  const onError = (msg) => setError(msg)

  return (
    <div style={{ padding: 24 }}>
      <h1 style={{ fontSize: 22, margin: '0 0 4px' }}>Program Configuration</h1>
      <p style={{ margin: 0, color: '#5A6478' }}>
        Approval workflows, partner tiers, and activation criteria. Available to system_admin and channel_ops_admin.
      </p>

      <div role="tablist" style={{ display: 'flex', gap: 4, borderBottom: '1px solid #E5E7EB', marginTop: 20 }}>
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            aria-selected={active === t.key}
            onClick={() => setActive(t.key)}
            style={{
              padding: '10px 16px', border: 'none', background: 'transparent',
              borderBottom: active === t.key ? '2px solid #1A6EBB' : '2px solid transparent',
              color: active === t.key ? '#1A6EBB' : '#475569',
              fontWeight: 600, fontSize: 14, cursor: 'pointer',
            }}
          >{t.label}</button>
        ))}
      </div>

      {error && (
        <div className="fp-alert fp-alert--danger" style={{ marginTop: 16 }}>
          {error}
          <button type="button" onClick={() => setError(null)}
                  style={{ marginLeft: 12, background: 'transparent', border: 'none', cursor: 'pointer', color: 'inherit' }}>
            Dismiss
          </button>
        </div>
      )}

      <div style={{ marginTop: 16 }}>
        {active === 'workflow' && <ApprovalWorkflowTab token={token} onUpdate={onUpdate} onError={onError} />}
        {active === 'tiers'    && <TiersTab            token={token} onUpdate={onUpdate} onError={onError} />}
        {active === 'criteria' && <ActivationTab       token={token} onUpdate={onUpdate} onError={onError} />}
      </div>

      <Toast message={toast} />
    </div>
  )
}
