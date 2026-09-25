import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiErrorMessage } from "../lib/api";
import { useAuth } from "../context/AuthContext";

const STATUS_COLORS: Record<string, string> = {
  DRAFT: "#999", SCHEDULED: "#a15c00", OPEN: "#0f6e5c", CLOSED: "#555",
  COUNTING: "#0b5346", VERIFICATION: "#0b5346", APPROVED: "#0b5346", PUBLISHED: "#14213d",
};

const LEVEL_OPTIONS = ["Lok Sabha", "Rajya Sabha", "Municipal", "Panchayat", "Other"];

export default function ElectionsPage() {
  const { role } = useAuth();
  const [elections, setElections] = useState<any[]>([]);
  const [officers, setOfficers] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    name: "", description: "", start_time: "", end_time: "",
    election_level: "", eligible_constituency: "", officer_ids: [] as string[],
  });
  const [error, setError] = useState("");

  const load = (query?: string) => api.get("/elections", { params: query ? { q: query } : {} }).then((r) => setElections(r.data));

  useEffect(() => {
    load();
    if (role === "SUPER_ADMIN") {
      api.get("/admin/officers").then((r) => setOfficers(r.data.filter((o: any) => o.is_active)));
    }
  }, [role]);

  useEffect(() => {
    const t = setTimeout(() => load(q), 250);
    return () => clearTimeout(t);
  }, [q]);

  const toggleOfficer = (id: string) => {
    setForm((f) => ({
      ...f,
      officer_ids: f.officer_ids.includes(id) ? f.officer_ids.filter((o) => o !== id) : [...f.officer_ids, id],
    }));
  };

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await api.post("/elections", {
        ...form,
        election_level: form.election_level || null,
        eligible_constituency: form.eligible_constituency || null,
      });
      setShowCreate(false);
      setForm({ name: "", description: "", start_time: "", end_time: "", election_level: "", eligible_constituency: "", officer_ids: [] });
      load(q);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  };

  const remove = async (e: React.MouseEvent, id: string, name: string, status: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (status !== "DRAFT") {
      alert("Only DRAFT elections can be deleted. Use the lifecycle actions on the election page instead.");
      return;
    }
    if (!confirm(`Delete draft election "${name}"? This cannot be undone.`)) return;
    try {
      await api.delete(`/elections/${id}`);
      load(q);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 style={{ fontFamily: "var(--font-display)" }} className="text-3xl font-bold">Elections</h1>
        {role === "SUPER_ADMIN" && (
          <button className="btn-primary" onClick={() => setShowCreate(!showCreate)}>
            {showCreate ? "Cancel" : "+ New Election"}
          </button>
        )}
      </div>

      <input className="input mb-4" placeholder="Search elections by name or region…"
        value={q} onChange={(e) => setQ(e.target.value)} />

      {showCreate && (
        <form onSubmit={create} className="card p-5 mb-6 space-y-3">
          <div>
            <label className="label">Election Name</label>
            <input className="input mt-1" required value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <label className="label">Description</label>
            <textarea className="input mt-1" value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Start Time</label>
              <input className="input mt-1" type="datetime-local" required value={form.start_time}
                onChange={(e) => setForm({ ...form, start_time: e.target.value })} />
            </div>
            <div>
              <label className="label">End Time</label>
              <input className="input mt-1" type="datetime-local" required value={form.end_time}
                onChange={(e) => setForm({ ...form, end_time: e.target.value })} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Level / Type of Election</label>
              <select className="input mt-1" value={form.election_level}
                onChange={(e) => setForm({ ...form, election_level: e.target.value })}>
                <option value="">— Not specified —</option>
                {LEVEL_OPTIONS.map((lvl) => <option key={lvl} value={lvl}>{lvl}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Region / Constituency</label>
              <input className="input mt-1" placeholder="e.g. North — leave blank for all"
                value={form.eligible_constituency}
                onChange={(e) => setForm({ ...form, eligible_constituency: e.target.value })} />
            </div>
          </div>
          <p className="text-xs text-gray-400">
            Region must exactly match the "constituency" value in the voter registry. Only voters from
            that region will see and be able to vote in this election; leave blank to allow everyone.
          </p>
          <div>
            <label className="label">Assign Election Officers (optional, multiple allowed)</label>
            <div className="mt-1 space-y-1 max-h-32 overflow-auto border rounded p-2" style={{ borderColor: "var(--color-line)" }}>
              {officers.length === 0 && <p className="text-xs text-gray-400">No officers yet — create one on the Officers page.</p>}
              {officers.map((o) => (
                <label key={o.id} className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={form.officer_ids.includes(o.id)} onChange={() => toggleOfficer(o.id)} />
                  {o.name} ({o.email})
                </label>
              ))}
            </div>
          </div>
          {error && <p className="text-sm" style={{ color: "var(--color-danger)" }}>{error}</p>}
          <button className="btn-primary">Create (starts as DRAFT)</button>
        </form>
      )}

      <div className="grid gap-3">
        {elections.map((e) => (
          <Link to={`/admin/elections/${e.id}`} key={e.id} className="card p-4 flex items-center justify-between hover:shadow-sm">
            <div>
              <div className="font-semibold">{e.name}</div>
              <div className="text-xs text-gray-400">
                {new Date(e.start_time).toLocaleString()} → {new Date(e.end_time).toLocaleString()}
                {e.election_level && <> · {e.election_level}</>}
                {e.eligible_constituency && <> · Region: {e.eligible_constituency}</>}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="badge" style={{ background: "#f0efe9", color: STATUS_COLORS[e.status] }}>{e.status}</span>
              {role === "SUPER_ADMIN" && (
                <button className="btn-secondary text-xs py-1 px-2" style={{ color: "var(--color-danger)" }}
                  onClick={(ev) => remove(ev, e.id, e.name, e.status)}>
                  Delete
                </button>
              )}
            </div>
          </Link>
        ))}
        {elections.length === 0 && <p className="text-gray-400 text-sm">No elections found.</p>}
      </div>
    </div>
  );
}
