import { useEffect, useState } from "react";
import { api, apiErrorMessage } from "../lib/api";

export default function OfficersPage() {
  const [officers, setOfficers] = useState<any[]>([]);
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<any>(null);

  const load = () => api.get("/admin/officers").then((r) => setOfficers(r.data));
  useEffect(() => { load(); }, []);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await api.post("/admin/officers", form);
      setForm({ name: "", email: "", password: "" });
      load();
    } catch (err) { setError(apiErrorMessage(err)); }
  };

  const toggle = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await api.post(`/admin/officers/${id}/toggle-active`);
    load();
    if (selected?.id === id) openDetail(id);
  };

  const remove = async (e: React.MouseEvent, id: string, name: string) => {
    e.stopPropagation();
    if (!confirm(`Delete officer ${name}? This removes their account and election assignments. This cannot be undone.`)) return;
    setError("");
    try {
      await api.delete(`/admin/officers/${id}`);
      if (selected?.id === id) setSelected(null);
      load();
    } catch (err) { setError(apiErrorMessage(err)); }
  };

  const openDetail = async (id: string) => {
    const r = await api.get(`/admin/officers/${id}`);
    setSelected(r.data);
  };

  return (
    <div>
      <h1 style={{ fontFamily: "var(--font-display)" }} className="text-3xl font-bold mb-6">Election Officers</h1>
      <form onSubmit={create} className="card p-5 mb-6 flex gap-2 items-end flex-wrap">
        <div>
          <label className="label">Name</label>
          <input className="input mt-1" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </div>
        <div>
          <label className="label">Email</label>
          <input className="input mt-1" type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </div>
        <div>
          <label className="label">Password</label>
          <input className="input mt-1" type="password" required value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        </div>
        <button className="btn-primary">Create Officer</button>
      </form>
      {error && <p className="text-sm mb-4" style={{ color: "var(--color-danger)" }}>{error}</p>}

      <div className="card divide-y mb-6" style={{ borderColor: "var(--color-line)" }}>
        {officers.map((o) => (
          <div key={o.id} className="p-4 flex items-center justify-between cursor-pointer hover:bg-black/[0.02]"
            onClick={() => openDetail(o.id)}>
            <div>
              <div className="font-medium">{o.name}</div>
              <div className="text-xs text-gray-400">{o.email}</div>
            </div>
            <div className="flex items-center gap-2">
              <button className="btn-secondary text-xs py-1.5 px-3" onClick={(e) => toggle(e, o.id)}>
                {o.is_active ? "Deactivate" : "Activate"}
              </button>
              <button className="btn-secondary text-xs py-1.5 px-3" style={{ color: "var(--color-danger)" }}
                onClick={(e) => remove(e, o.id, o.name)}>
                Delete
              </button>
            </div>
          </div>
        ))}
        {officers.length === 0 && <p className="p-4 text-sm text-gray-400">No officers yet.</p>}
      </div>

      {selected && (
        <div className="card p-5">
          <h2 className="font-semibold mb-1">{selected.name}</h2>
          <p className="text-xs text-gray-400 mb-4">{selected.email} · {selected.is_active ? "Active" : "Deactivated"}</p>

          <h3 className="text-sm font-semibold mb-2">Election History</h3>
          <div className="space-y-1 mb-4">
            {selected.elections.map((e: any) => (
              <div key={e.id} className="flex justify-between text-sm border-b pb-1" style={{ borderColor: "var(--color-line)" }}>
                <span>{e.name}</span><span className="text-gray-400">{e.status}</span>
              </div>
            ))}
            {selected.elections.length === 0 && <p className="text-sm text-gray-400">Not assigned to any elections.</p>}
          </div>

          <h3 className="text-sm font-semibold mb-2">Activity</h3>
          <div className="space-y-1 max-h-64 overflow-auto">
            {selected.activity.map((a: any, i: number) => (
              <div key={i} className="flex items-center justify-between text-xs border-b pb-1" style={{ borderColor: "var(--color-line)" }}>
                <span>{a.action}</span>
                <span className="flex items-center gap-2">
                  <span style={{ color: a.success ? "var(--color-accent)" : "var(--color-danger)" }}>{a.success ? "OK" : "FAILED"}</span>
                  <span className="text-gray-400">{new Date(a.timestamp).toLocaleString()}</span>
                </span>
              </div>
            ))}
            {selected.activity.length === 0 && <p className="text-sm text-gray-400">No activity yet.</p>}
          </div>
        </div>
      )}
    </div>
  );
}
