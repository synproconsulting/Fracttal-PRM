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
import InternalLayout from './layouts/InternalLayout.jsx'
import PartnerHome from './pages/PartnerHome.jsx'
import PartnerProfile from './pages/PartnerProfile.jsx'
import PartnerDocuments from './pages/PartnerDocuments.jsx'
import DealList from './pages/DealList.jsx'
import DealRegistrationForm from './pages/DealRegistrationForm.jsx'
import DealDetail from './pages/DealDetail.jsx'
import DealQueue from './pages/DealQueue.jsx'
import InternalDealDetail from './pages/InternalDealDetail.jsx'
import CommissionRates from './pages/CommissionRates.jsx'
import InternalHome from './pages/InternalHome.jsx'
import InternalUsers from './pages/InternalUsers.jsx'
import PartnerUserManagement from './pages/PartnerUserManagement.jsx'
import InternalPartnerList from './pages/InternalPartnerList.jsx'
import ProgramConfig from './pages/ProgramConfig.jsx'
import ForgotPassword from './pages/ForgotPassword.jsx'
import ResetPassword from './pages/ResetPassword.jsx'

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

const INTERNAL_ROLES = [
  'system_admin',
  'channel_ops_admin',
  'channel_manager',
  'sales_rep',
  'sales_ops',
  'finance_approver',
]

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
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
        <Route path="commissions" element={<CommissionRates />} />
      </Route>

      <Route
        path="/internal"
        element={
          <ProtectedRoute roles={INTERNAL_ROLES}>
            <InternalLayout />
          </ProtectedRoute>
        }
      >
        <Route path="home" element={<InternalHome />} />
        <Route path="applications" element={<ApplicationQueue />} />
        <Route path="applications/:id" element={<ApplicationReview />} />
        <Route
          path="partners"
          element={
            <ProtectedRoute roles={["system_admin", "channel_ops_admin", "channel_manager"]}>
              <InternalPartnerList />
            </ProtectedRoute>
          }
        />
        <Route path="partners/:id/profile" element={<PartnerProfile />} />
        <Route path="partners/:id/documents" element={<PartnerDocuments />} />
        <Route path="deals" element={<DealQueue />} />
        <Route path="deals/:id" element={<InternalDealDetail />} />
        <Route
          path="users"
          element={
            <ProtectedRoute roles={["system_admin"]}>
              <InternalUsers />
            </ProtectedRoute>
          }
        />
        <Route
          path="partner-users"
          element={
            <ProtectedRoute roles={["system_admin", "channel_ops_admin"]}>
              <PartnerUserManagement />
            </ProtectedRoute>
          }
        />
        <Route
          path="config"
          element={
            <ProtectedRoute roles={["system_admin", "channel_ops_admin"]}>
              <ProgramConfig />
            </ProtectedRoute>
          }
        />
      </Route>
    </Routes>
  )
}
