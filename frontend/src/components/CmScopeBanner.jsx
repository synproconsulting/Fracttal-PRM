// Sprint 24 PR B / FPRM-425 / AD-41 -- queue scope indicator for the
// channel_manager role. ``scope`` comes from the queue response's ``cm_scope``
// field: 'assigned' (queue is filtered to the CM's partners), 'all' (bootstrap
// — no assignment exists anywhere, so the CM sees all), or null (any other
// role — nothing rendered).
export default function CmScopeBanner({ scope }) {
  if (!scope) return null
  const assigned = scope === 'assigned'
  return (
    <div
      role="status"
      style={{
        marginBottom: 16,
        padding: '8px 12px',
        borderRadius: 6,
        fontSize: 13,
        background: assigned ? '#EFF6FF' : '#F5F7FA',
        color: assigned ? '#1A6EBB' : '#64748B',
        border: `1px solid ${assigned ? '#BFDBFE' : '#E0E4EA'}`,
      }}
    >
      {assigned
        ? 'Showing your assigned partners'
        : 'Showing all partners (no assignments configured yet)'}
    </div>
  )
}
