import { type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({ children, roles }: { children: ReactNode; roles: string[] }) {
  const { token, role } = useAuth();
  if (!token || !role) return <Navigate to="/login" replace />;
  if (!roles.includes(role)) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
