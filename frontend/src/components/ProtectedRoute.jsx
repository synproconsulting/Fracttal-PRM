import { Navigate } from 'react-router-dom'

function decodeJwt(token) {
  try {
    const parts = token.split('.')
    if (parts.length < 2) return null
    const padded = parts[1] + '==='.slice((parts[1].length + 3) % 4)
    const json = atob(padded.replace(/-/g, '+').replace(/_/g, '/'))
    return JSON.parse(json)
  } catch (_) {
    return null
  }
}

export default function ProtectedRoute({ children, roles }) {
  const token = localStorage.getItem('token')
  if (!token) return <Navigate to="/login" replace />
  const payload = decodeJwt(token)
  if (!payload) return <Navigate to="/login" replace />
  if (roles && roles.length > 0 && !roles.includes(payload.role)) {
    return <Navigate to="/login" replace />
  }
  return children
}
