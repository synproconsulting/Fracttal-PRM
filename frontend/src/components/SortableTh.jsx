// Shared clickable column header for list-page tables.
//
// Pattern (all list pages):
//   const [sort, setSort] = useState({ field: 'created_at', dir: 'desc' })
//   function toggleSort(field) {
//     setSort((s) => s.field === field
//       ? { field, dir: s.dir === 'asc' ? 'desc' : 'asc' }
//       : { field, dir: 'asc' })
//   }
//   ...
//   <SortableTh field="deal_name" sort={sort} onSort={toggleSort}>Deal</SortableTh>
//
// The backend honours ?sort_by=<field>&sort_dir=asc|desc and falls back to
// the endpoint's default silently for unknown fields, so SortableTh is safe
// to wire to any column even before the backend allowlists it.
export function SortableTh({ field, sort, onSort, children, style = {}, align = 'left' }) {
  const active = sort && sort.field === field
  const arrow = active ? (sort.dir === 'asc' ? '↑' : '↓') : '↕'
  const baseStyle = {
    textAlign: align,
    cursor: 'pointer',
    userSelect: 'none',
    whiteSpace: 'nowrap',
    ...style,
  }
  return (
    <th
      style={baseStyle}
      onClick={() => onSort && onSort(field)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if ((e.key === 'Enter' || e.key === ' ') && onSort) {
          e.preventDefault()
          onSort(field)
        }
      }}
      aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}
    >
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
        <span style={{ fontWeight: active ? 700 : 'inherit' }}>{children}</span>
        <span style={{ opacity: active ? 1 : 0.35, fontSize: 11, lineHeight: 1 }}>{arrow}</span>
      </span>
    </th>
  )
}

// Helper to append sort_by/sort_dir to an existing URLSearchParams or query
// fragment. Use when the page already builds the query string by hand.
export function appendSortParams(params, sort) {
  if (!sort) return params
  if (params instanceof URLSearchParams) {
    if (sort.field) params.set('sort_by', sort.field)
    if (sort.dir) params.set('sort_dir', sort.dir)
    return params
  }
  return params
}

export default SortableTh
