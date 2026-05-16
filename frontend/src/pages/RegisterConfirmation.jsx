import { useSearchParams, Link } from 'react-router-dom'

export default function RegisterConfirmation() {
  const [searchParams] = useSearchParams()
  const ref = searchParams.get('ref')

  return (
    <div style={{ maxWidth: 640, margin: '80px auto', padding: '0 20px', textAlign: 'center', fontFamily: 'system-ui, sans-serif' }}>
      <h1 style={{ color: '#28a745' }}>Application Submitted</h1>
      <p style={{ fontSize: 16 }}>
        Thank you for applying to become a Fracttal Distribution Partner. Your application has been received
        and will be reviewed by our team.
      </p>
      {ref && (
        <p style={{ marginTop: 24, fontSize: 14, color: '#555' }}>
          Your application reference number is:
          <br />
          <strong style={{ fontFamily: 'monospace', fontSize: 16 }}>{ref}</strong>
        </p>
      )}
      <p style={{ marginTop: 24, fontSize: 14, color: '#555' }}>
        We will contact you at the email address you provided. Please keep your reference number for your records.
      </p>
      <p style={{ marginTop: 32 }}>
        <Link to="/">Return to home</Link>
      </p>
    </div>
  )
}
