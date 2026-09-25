import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiErrorMessage } from "../lib/api";

export default function SetupPage() {
  const navigate = useNavigate();
  const [checked, setChecked] = useState(false);
  const [form, setForm] = useState({
    org_name: "", admin_name: "", email: "", password: "", confirm_password: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get("/setup/status").then((r) => {
      if (r.data.initialized) navigate("/login");
      setChecked(true);
    });
  }, [navigate]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.post("/setup/initialize", form);
      navigate("/login");
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  if (!checked) return null;

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="card p-8 w-full max-w-md">
        <h1 style={{ fontFamily: "var(--font-display)" }} className="text-2xl font-bold mb-1">
          Initial System Setup
        </h1>
        <p className="text-sm text-gray-500 mb-6">
          This runs once. It creates the founding Super Admin account and permanently disables this page.
        </p>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label">Organization / Election Authority Name</label>
            <input className="input mt-1" required value={form.org_name}
              onChange={(e) => setForm({ ...form, org_name: e.target.value })} />
          </div>
          <div>
            <label className="label">Super Admin Name</label>
            <input className="input mt-1" required value={form.admin_name}
              onChange={(e) => setForm({ ...form, admin_name: e.target.value })} />
          </div>
          <div>
            <label className="label">Official Email</label>
            <input className="input mt-1" type="email" required value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </div>
          <div>
            <label className="label">Password</label>
            <input className="input mt-1" type="password" required minLength={8} value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </div>
          <div>
            <label className="label">Confirm Password</label>
            <input className="input mt-1" type="password" required value={form.confirm_password}
              onChange={(e) => setForm({ ...form, confirm_password: e.target.value })} />
          </div>
          {error && <p className="text-sm" style={{ color: "var(--color-danger)" }}>{error}</p>}
          <button className="btn-primary w-full" disabled={loading}>
            {loading ? "Initializing…" : "Initialize System"}
          </button>
        </form>
      </div>
    </div>
  );
}
