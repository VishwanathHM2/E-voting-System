import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";
import SetupPage from "./pages/SetupPage";
import RootRedirect from "./pages/RootRedirect";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import ElectionsPage from "./pages/ElectionsPage";
import ElectionDetailPage from "./pages/ElectionDetailPage";
import VotersPage from "./pages/VotersPage";
import OfficersPage from "./pages/OfficersPage";
import AuditPage from "./pages/AuditPage";
import EnrollPage from "./pages/EnrollPage";
import TotpRecoveryPage from "./pages/TotpRecoveryPage";
import VotePage from "./pages/VotePage";

const ADMIN_ROLES = ["SUPER_ADMIN", "ELECTION_OFFICER"];

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/setup" element={<SetupPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/enroll" element={<EnrollPage />} />
          <Route path="/totp-recovery" element={<TotpRecoveryPage />} />
          <Route path="/vote" element={<VotePage />} />

          <Route path="/admin/dashboard" element={
            <ProtectedRoute roles={ADMIN_ROLES}><Layout><DashboardPage /></Layout></ProtectedRoute>
          } />
          <Route path="/admin/elections" element={
            <ProtectedRoute roles={ADMIN_ROLES}><Layout><ElectionsPage /></Layout></ProtectedRoute>
          } />
          <Route path="/admin/elections/:id" element={
            <ProtectedRoute roles={ADMIN_ROLES}><Layout><ElectionDetailPage /></Layout></ProtectedRoute>
          } />
          <Route path="/admin/voters" element={
            <ProtectedRoute roles={ADMIN_ROLES}><Layout><VotersPage /></Layout></ProtectedRoute>
          } />
          <Route path="/admin/officers" element={
            <ProtectedRoute roles={["SUPER_ADMIN"]}><Layout><OfficersPage /></Layout></ProtectedRoute>
          } />
          <Route path="/admin/audit" element={
            <ProtectedRoute roles={ADMIN_ROLES}><Layout><AuditPage /></Layout></ProtectedRoute>
          } />

          <Route path="/" element={<RootRedirect />} />
          <Route path="*" element={<RootRedirect />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
