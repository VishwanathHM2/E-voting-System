import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";

export default function DashboardPage() {
  const { role } = useAuth();
  const [data, setData] = useState<any>(null);
  const [showActivity, setShowActivity] = useState(false);

  useEffect(() => {
    api.get("/admin/dashboard").then((r) => setData(r.data));
  }, []);

  if (!data) return <p className="text-gray-400">Loading…</p>;

  const stats = [
    { label: "Total Elections", value: data.total_elections },
    { label: "Active Elections", value: data.active_elections },
    { label: "Completed Elections", value: data.completed_elections },
    { label: "Eligible Voters", value: data.eligible_voters },
    { label: "Enrolled Voters", value: data.enrolled_voters },
    { label: "Votes Cast", value: data.votes_cast },
    { label: "Turnout", value: `${data.turnout_pct}%` },
    { label: "Auth Failures", value: data.auth_failures },
  ];

  return (
    <div>
      <h1 style={{ fontFamily: "var(--font-display)" }} className="text-3xl font-bold mb-6">Dashboard</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-5 mb-8">
        {stats.map((s) => (
          <div key={s.label} className="card p-6">
            <div className="text-4xl font-bold" style={{ fontFamily: "var(--font-mono)" }}>{s.value}</div>
            <div className="label mt-2">{s.label}</div>
          </div>
        ))}
      </div>

      {role === "SUPER_ADMIN" && (
        <>
          {!showActivity ? (
            <button className="btn-secondary" onClick={() => setShowActivity(true)}>
              View Recent Activity
            </button>
          ) : (
            <>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-lg font-semibold">Recent Activity</h2>
                <button className="btn-secondary text-xs py-1.5 px-3" onClick={() => setShowActivity(false)}>Hide</button>
              </div>
              <div className="card divide-y" style={{ borderColor: "var(--color-line)" }}>
                {data.recent_activity.map((a: any, i: number) => (
                  <div key={i} className="px-4 py-2.5 flex items-center justify-between text-sm">
                    <div>
                      <span className="font-medium">{a.action}</span>
                      {a.actor_role && <span className="text-gray-400"> · {a.actor_role}</span>}
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="badge" style={{
                        background: a.success ? "#e6f2ef" : "#fbe9e7",
                        color: a.success ? "var(--color-accent-dark)" : "var(--color-danger)",
                      }}>{a.success ? "OK" : "FAILED"}</span>
                      <span className="text-gray-400 text-xs">{new Date(a.timestamp).toLocaleString()}</span>
                    </div>
                  </div>
                ))}
                {data.recent_activity.length === 0 && <p className="p-4 text-sm text-gray-400">No activity yet.</p>}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
