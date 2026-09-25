import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../context/AuthContext";

export default function AuditPage() {
  const { role } = useAuth();
  const [logs, setLogs] = useState<any[]>([]);
  const [ledger, setLedger] = useState<any[]>([]);
  const [verify, setVerify] = useState<any>(null);

  useEffect(() => {
    if (role === "SUPER_ADMIN") {
      api.get("/audit/logs").then((r) => setLogs(r.data.logs));
    }
    api.get("/audit/ledger").then((r) => setLedger(r.data));
    api.get("/audit/ledger/verify").then((r) => setVerify(r.data));
  }, [role]);

  return (
    <div>
      <h1 style={{ fontFamily: "var(--font-display)" }} className="text-3xl font-bold mb-6">Audit & Ledger</h1>

      {verify && (
        <div className="card p-4 mb-6 flex items-center gap-3">
          <span className="badge" style={{
            background: verify.valid ? "#e6f2ef" : "#fbe9e7",
            color: verify.valid ? "var(--color-accent-dark)" : "var(--color-danger)",
          }}>
            {verify.valid ? "LEDGER VALID" : "TAMPERING DETECTED"}
          </span>
          <span className="text-sm text-gray-500">
            {verify.valid ? `${verify.blocks_verified} blocks verified` : verify.reason}
          </span>
        </div>
      )}

      <h2 className="font-semibold mb-3">Blockchain Ledger ({ledger.length} blocks)</h2>
      <div className="card overflow-auto mb-8" style={{ maxHeight: 300 }}>
        <table className="w-full text-xs">
          <thead className="sticky top-0" style={{ background: "var(--color-paper-raised)" }}>
            <tr className="text-left border-b" style={{ borderColor: "var(--color-line)" }}>
              <th className="p-2">#</th><th className="p-2">Event</th><th className="p-2">TX ID</th>
              <th className="p-2">Block Hash</th><th className="p-2">Time</th>
            </tr>
          </thead>
          <tbody style={{ fontFamily: "var(--font-mono)" }}>
            {ledger.map((b) => (
              <tr key={b.id} className="border-b" style={{ borderColor: "var(--color-line)" }}>
                <td className="p-2">{b.id}</td>
                <td className="p-2">{b.event_type}</td>
                <td className="p-2">{b.tx_id.slice(0, 8)}…</td>
                <td className="p-2">{b.block_hash.slice(0, 16)}…</td>
                <td className="p-2">{new Date(b.timestamp).toLocaleTimeString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {role === "SUPER_ADMIN" && (
        <>
          <h2 className="font-semibold mb-3">Audit Log</h2>
          <div className="card divide-y overflow-auto" style={{ borderColor: "var(--color-line)", maxHeight: 400 }}>
            {logs.map((l) => (
              <div key={l.id} className="px-4 py-2.5 flex items-center justify-between text-sm">
                <div><span className="font-medium">{l.action}</span> {l.actor_role && <span className="text-gray-400">· {l.actor_role}</span>}</div>
                <div className="flex items-center gap-3">
                  <span style={{ color: l.success ? "var(--color-accent)" : "var(--color-danger)" }}>{l.success ? "OK" : "FAILED"}</span>
                  <span className="text-gray-400 text-xs">{new Date(l.timestamp).toLocaleString()}</span>
                </div>
              </div>
            ))}
            {logs.length === 0 && <p className="p-4 text-sm text-gray-400">No activity yet.</p>}
          </div>
        </>
      )}
    </div>
  );
}
