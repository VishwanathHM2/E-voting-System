import { type ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const NAV_BY_ROLE: Record<string, { to: string; label: string }[]> = {
  SUPER_ADMIN: [
    { to: "/admin/dashboard", label: "Dashboard" },
    { to: "/admin/elections", label: "Elections" },
    { to: "/admin/voters", label: "Voter Registry" },
    { to: "/admin/officers", label: "Officers" },
    { to: "/admin/audit", label: "Audit & Ledger" },
  ],
  ELECTION_OFFICER: [
    { to: "/admin/dashboard", label: "Dashboard" },
    { to: "/admin/elections", label: "Elections" },
    { to: "/admin/voters", label: "Voter Registry" },
    { to: "/admin/audit", label: "Audit & Ledger" },
  ],
};

export default function Layout({ children }: { children: ReactNode }) {
  const { role, logout } = useAuth();
  const navigate = useNavigate();
  const items = role ? NAV_BY_ROLE[role] || [] : [];

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b" style={{ borderColor: "var(--color-line)" }}>
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-baseline gap-2">
            <span style={{ fontFamily: "var(--font-display)", fontWeight: 700 }} className="text-xl">
              SecureEVote
            </span>
            <span className="label" style={{ color: "var(--color-warn)" }}>
              not certified for government elections
            </span>
          </div>
          {role && (
            <nav className="flex items-center gap-5 text-sm">
              {items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    isActive ? "font-semibold" : "text-gray-500 hover:text-black"
                  }
                  style={({ isActive }) => (isActive ? { color: "var(--color-accent)" } : {})}
                >
                  {item.label}
                </NavLink>
              ))}
              <button
                onClick={() => {
                  logout();
                  navigate("/login");
                }}
                className="btn-secondary text-xs py-1.5 px-3"
              >
                Sign out
              </button>
            </nav>
          )}
        </div>
      </header>
      <main className="flex-1 max-w-6xl mx-auto w-full px-6 py-8">{children}</main>
      <footer className="border-t py-4 text-center text-xs text-gray-400" style={{ borderColor: "var(--color-line)" }}>
        SecureEVote — organizational elections only. Not a government or Election Commission system.
      </footer>
    </div>
  );
}
