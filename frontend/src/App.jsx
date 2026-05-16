import { Routes, Route, Link } from 'react-router-dom'
import RegisterPartner from './pages/RegisterPartner.jsx'

function Landing() {
  return (
    <div style={{ maxWidth: 720, margin: '64px auto', padding: '0 20px', fontFamily: 'system-ui, sans-serif' }}>
      <h1>Fracttal PRM</h1>
      <p>Partner Relationship Management System</p>
      <p>
        <Link to="/register">Apply to become a Fracttal Distribution Partner</Link>
      </p>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/register" element={<RegisterPartner />} />
    </Routes>
  )
}
