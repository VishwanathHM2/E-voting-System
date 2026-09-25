import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import LandingPage from "./LandingPage";

/**
 * `/` (and any unknown path) lands here.
 *   - not initialized yet -> /setup
 *   - already signed in    -> /admin/dashboard
 *   - otherwise            -> render the landing page (Enroll / Vote / Staff Sign In)
 */
export default function RootRedirect() {
  const { token } = useAuth();
  const [status, setStatus] = useState<"loading" | "needs_setup" | "ready">(
    token ? "ready" : "loading"
  );

  useEffect(() => {
    if (token) return;
    api.get("/setup/status")
      .then((r) => setStatus(r.data.initialized ? "ready" : "needs_setup"))
      .catch(() => setStatus("ready"));
  }, [token]);

  if (token) return <Navigate to="/admin/dashboard" replace />;
  if (status === "loading") return null;
  if (status === "needs_setup") return <Navigate to="/setup" replace />;
  return <LandingPage />;
}
