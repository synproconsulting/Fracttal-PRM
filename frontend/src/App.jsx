import { Routes, Route, Link } from 'react-router-dom'
import RegisterPartner from './pages/RegisterPartner.jsx'
import RegisterConfirmation from './pages/RegisterConfirmation.jsx'
import ApplicationQueue from './pages/ApplicationQueue.jsx'
import ApplicationReview from './pages/ApplicationReview.jsx'
import ApplicationResume from './pages/ApplicationResume.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import Login from './pages/Login.jsx'
import AcceptInvite from './pages/AcceptInvite.jsx'
import PartnerPortalLayout from './layouts/PartnerPortalLayout.jsx'
import PartnerHome from './pages/PartnerHome.jsx'
import PartnerProfile from './pages/PartnerProfile.jsx'
import PartnerDocuments from './pages/PartnerDocuments.jsx'
import DealList from './pages/DealList.jsx'
import DealRegistrationForm from './pages/DealRegistrationForm.jsx'
import DealDetail from './pages/DealDetail.jsx'
import DealQueue from './pages/DealQueue.jsx'
import InternalDealDetail from './pages/InternalDealDetail.jsx'

function Landing() {
  return (
    <div style={{ maxWidth: 720, margin: '64px auto', padding: '0 20px', fontFamily: 'system-ui, sans-serif' }}>
      <h1>Fracttal PRM</h1>
      <p>Partner Relationship Management System</p>
      <p>
        <Link to="/register">Apply to become a Fracttal Distribution Partner</Link>
      </p>
      <p>
        <Link to="/login">Sign in to the partner portal</Link>
      </p>
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<RegisterPartner />} />
      <Route path="/register/confirmation" element={<RegisterConfirmation />} />
      <Route path="/resume-application" element={<ApplicationResume />} />
      <Route path="/accept-invite" element={<AcceptInvite />} />

      <Route
        path="/portal"
        element={
          <ProtectedRoute roles={["partner_user", "partner_admin"]}>
            <PartnerPortalLayout />
          </ProtectedRoute>
        }
      >
        <Route path="home" element={<PartnerHome />} />
        <Route path="profile" element={<PartnerProfile />} />
        <Route path="documents" element={<PartnerDocuments />} />
        <Route path="deals" element={<DealList />} />
        <Route path="deals/new" element={<DealRegistrationForm />} />
        <Route path="deals/:id" element={<DealDetail />} />
        <Route path="deals/:id/edit" element={<DealRegistrationForm />} />
      </Route>

      <Route
        path="/internal/applications"
        element={
          <ProtectedRoute roles={["channel_manager", "channel_ops_admin", "system_admin"]}>
            <ApplicationQueue />
          </ProtectedRoute>
        }
      />
      <Route
        path="/internal/applications/:id"
        element={
          <ProtectedRoute roles={["channel_manager", "channel_ops_admin", "system_admin"]}>
            <ApplicationReview />
          </ProtectedRoute>
        }
      />
      <Route
        path="/internal/partners/:id/profile"
        element={
          <ProtectedRoute roles={["channel_manager", "channel_ops_admin", "system_admin"]}>
            <PartnerProfile />
          </ProtectedRoute>
        }
      />
      <Route
        path="/internal/partners/:id/documents"
        element={
          <ProtectedRoute roles={["channel_manager", "channel_ops_admin", "system_admin"]}>
            <PartnerDocuments />
          </ProtectedRoute>
        }
      />
      <Route
        path="/internal/deals"
        element={
          <ProtectedRoute roles={["channel_manager", "channel_ops_admin", "system_admin"]}>
            <DealQueue />
          </ProtectedRoute>
        }
      />
      <Route
        path="/internal/deals/:id"
        element={
          <ProtectedRoute roles={["channel_manager", "channel_ops_admin", "system_admin"]}>
            <InternalDealDetail />
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}
