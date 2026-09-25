import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { PieChart, Pie, Cell, Tooltip, BarChart, Bar, XAxis, YAxis, ResponsiveContainer } from "recharts";
import { api, apiErrorMessage, downloadAuthenticated, SERVER_ORIGIN } from "../lib/api";
import { useAuth } from "../context/AuthContext";

const NEXT_STEPS: Record<string, { status: string; label: string }[]> = {
  DRAFT: [{ status: "SCHEDULED", label: "Mark as Scheduled" }],
  SCHEDULED: [{ status: "OPEN", label: "Open for Voting" }],
  OPEN: [{ status: "CLOSED", label: "Close Voting" }],
  CLOSED: [{ status: "OPEN", label: "Reopen (Super Admin only)" }],
};

const COLORS = ["#0f6e5c", "#a15c00", "#14213d", "#b3261e", "#6b8f9e", "#8a6d3b"];

export default function ElectionDetailPage() {
  const { id } = useParams();
  const { role } = useAuth();
  const [election, setElection] = useState<any>(null);
  const [candidates, setCandidates] = useState<any[]>([]);
  const [allOfficers, setAllOfficers] = useState<any[]>([]);
  const [addOfficerId, setAddOfficerId] = useState("");
  const [newCand, setNewCand] = useState({ name: "", candidate_type: "INDIVIDUAL", party: "" });
  const [newCandPhoto, setNewCandPhoto] = useState<File | null>(null);
  const [newCandPartySymbol, setNewCandPartySymbol] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [countResult, setCountResult] = useState<any>(null);
  const [publicResults, setPublicResults] = useState<any>(null);

  const load = async () => {
    const [eRes, cRes] = await Promise.all([
      api.get(`/elections/${id}`),
      api.get(`/candidates/election/${id}`),
    ]);
    setElection(eRes.data);
    setCandidates(cRes.data);
    if (eRes.data.status === "PUBLISHED") {
      const pr = await api.get(`/results/${id}/public`);
      setPublicResults(pr.data);
    }
  };

  useEffect(() => { load(); }, [id]);

  useEffect(() => {
    if (role === "SUPER_ADMIN") {
      api.get("/admin/officers").then((r) => setAllOfficers(r.data));
    }
  }, [role]);

  const addCandidate = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      const r = await api.post("/candidates", { election_id: id, ...newCand });
      if (newCandPhoto) {
        const fd = new FormData();
        fd.append("file", newCandPhoto);
        await api.post(`/candidates/${r.data.id}/photo`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      }
      if (newCand.candidate_type === "PARTY" && newCandPartySymbol) {
        const fd = new FormData();
        fd.append("file", newCandPartySymbol);
        await api.post(`/candidates/${r.data.id}/party-symbol`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      }
      setNewCand({ name: "", candidate_type: "INDIVIDUAL", party: "" });
      setNewCandPhoto(null);
      setNewCandPartySymbol(null);
      load();
    } catch (err) { setError(apiErrorMessage(err)); }
  };

  const addOfficer = async () => {
    if (!addOfficerId) return;
    setError("");
    try {
      await api.post(`/elections/${id}/officers`, null, { params: { officer_id: addOfficerId } });
      setAddOfficerId("");
      load();
    } catch (err) { setError(apiErrorMessage(err)); }
  };

  const removeOfficer = async (officerId: string) => {
    setError("");
    try {
      await api.delete(`/elections/${id}/officers/${officerId}`);
      load();
    } catch (err) { setError(apiErrorMessage(err)); }
  };

  const transition = async (status: string) => {
    setError(""); setBusy(true);
    try {
      await api.post(`/elections/${id}/status`, { status });
      await load();
    } catch (err) { setError(apiErrorMessage(err)); } finally { setBusy(false); }
  };

  const doCount = async () => {
    setError(""); setBusy(true);
    try {
      await api.post(`/results/${id}/verify-ledger`);
      const r = await api.post(`/results/${id}/count`);
      setCountResult(r.data);
      await load();
    } catch (err) { setError(apiErrorMessage(err)); } finally { setBusy(false); }
  };

  const doApprove = async () => {
    setError(""); setBusy(true);
    try { await api.post(`/results/${id}/approve`); await load(); }
    catch (err) { setError(apiErrorMessage(err)); } finally { setBusy(false); }
  };

  const doPublish = async () => {
    setError(""); setBusy(true);
    try { await api.post(`/results/${id}/publish`); await load(); }
    catch (err) { setError(apiErrorMessage(err)); } finally { setBusy(false); }
  };

  const downloadPdf = async () => {
    setError(""); setBusy(true);
    try { await downloadAuthenticated(`/reports/${id}/pdf`, `election_${id}_report.pdf`); }
    catch (err) { setError(apiErrorMessage(err)); } finally { setBusy(false); }
  };

  const downloadExcel = async () => {
    setError(""); setBusy(true);
    try { await downloadAuthenticated(`/reports/${id}/excel`, `election_${id}_report.xlsx`); }
    catch (err) { setError(apiErrorMessage(err)); } finally { setBusy(false); }
  };

  if (!election) return <p className="text-gray-400">Loading…</p>;

  const chartData = (publicResults?.results || countResult?.results || []).map((r: any) => ({ name: r.name, votes: r.votes }));
  const editable = ["DRAFT", "SCHEDULED"].includes(election.status);
  const assignedOfficers = allOfficers.filter((o) => (election.officer_ids || []).includes(o.id));
  const unassignedOfficers = allOfficers.filter((o) => !(election.officer_ids || []).includes(o.id));

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <h1 style={{ fontFamily: "var(--font-display)" }} className="text-3xl font-bold">{election.name}</h1>
        <span className="badge" style={{ background: "#f0efe9", color: "var(--color-ink)" }}>{election.status}</span>
      </div>
      <p className="text-sm text-gray-500 mb-1">{election.description}</p>
      <p className="text-xs text-gray-400 mb-6">
        {election.election_level && <>{election.election_level} · </>}
        {election.eligible_constituency ? `Region: ${election.eligible_constituency}` : "Open to all regions"}
      </p>
      {error && <p className="text-sm mb-4" style={{ color: "var(--color-danger)" }}>{error}</p>}

      {role === "SUPER_ADMIN" && (
        <div className="card p-5 mb-6">
          <h2 className="font-semibold mb-3">Assigned Officers</h2>
          <div className="flex flex-wrap gap-2 mb-3">
            {assignedOfficers.map((o) => (
              <span key={o.id} className="badge flex items-center gap-1.5" style={{ background: "#f0efe9" }}>
                {o.name}
                <button onClick={() => removeOfficer(o.id)} className="text-xs" style={{ color: "var(--color-danger)" }}>×</button>
              </span>
            ))}
            {assignedOfficers.length === 0 && <p className="text-sm text-gray-400">No officers assigned yet.</p>}
          </div>
          <div className="flex gap-2">
            <select className="input" value={addOfficerId} onChange={(e) => setAddOfficerId(e.target.value)}>
              <option value="">— Select an officer to add —</option>
              {unassignedOfficers.map((o) => <option key={o.id} value={o.id}>{o.name} ({o.email})</option>)}
            </select>
            <button className="btn-secondary whitespace-nowrap" onClick={addOfficer} disabled={!addOfficerId}>Add</button>
          </div>
        </div>
      )}

      {editable && (
        <div className="card p-5 mb-6">
          <h2 className="font-semibold mb-3">Candidates</h2>
          <div className="space-y-2 mb-4">
            {candidates.map((c) => (
              <div key={c.id} className="flex items-center justify-between text-sm border-b pb-2" style={{ borderColor: "var(--color-line)" }}>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400" style={{ fontFamily: "var(--font-mono)" }}>#{c.candidate_number}</span>
                  {c.symbol_url && (
                    <img src={`${SERVER_ORIGIN}${c.symbol_url}`} alt={`${c.name} photo`}
                      className="w-8 h-8 rounded object-cover border" style={{ borderColor: "var(--color-line)" }} />
                  )}
                  {c.party_symbol_url && (
                    <img src={`${SERVER_ORIGIN}${c.party_symbol_url}`} alt="party symbol"
                      className="w-8 h-8 rounded object-cover border" style={{ borderColor: "var(--color-line)" }} />
                  )}
                  <span>{c.name}</span>
                  <span className="badge" style={{ background: "#f0efe9" }}>{c.candidate_type}</span>
                </div>
                <span className="text-gray-400">{c.party}</span>
              </div>
            ))}
            {candidates.length === 0 && <p className="text-sm text-gray-400">No candidates yet.</p>}
          </div>
          <form onSubmit={addCandidate} className="space-y-2">
            <div className="flex gap-2">
              <input className="input" placeholder="Candidate name" required value={newCand.name}
                onChange={(e) => setNewCand({ ...newCand, name: e.target.value })} />
              <select className="input" value={newCand.candidate_type}
                onChange={(e) => setNewCand({ ...newCand, candidate_type: e.target.value })}>
                <option value="INDIVIDUAL">Individual</option>
                <option value="PARTY">By Party</option>
              </select>
            </div>
            {newCand.candidate_type === "PARTY" && (
              <input className="input" placeholder="Party name" value={newCand.party}
                onChange={(e) => setNewCand({ ...newCand, party: e.target.value })} />
            )}
            <div>
              <label className="label">Candidate Photo</label>
              <input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" className="text-xs w-full mt-1"
                onChange={(e) => setNewCandPhoto(e.target.files?.[0] || null)} />
            </div>
            {newCand.candidate_type === "PARTY" && (
              <div>
                <label className="label">Party Symbol</label>
                <input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" className="text-xs w-full mt-1"
                  onChange={(e) => setNewCandPartySymbol(e.target.files?.[0] || null)} />
              </div>
            )}
            <button className="btn-secondary whitespace-nowrap">Add Candidate</button>
          </form>
        </div>
      )}

      {!editable && candidates.length > 0 && (
        <div className="card p-5 mb-6">
          <h2 className="font-semibold mb-3">Candidates</h2>
          <div className="flex flex-wrap gap-3">
            {candidates.map((c) => (
              <span key={c.id} className="badge flex items-center gap-1.5" style={{ background: "#f0efe9" }}>
                {(c.symbol_url || c.party_symbol_url) && (
                  <img src={`${SERVER_ORIGIN}${c.symbol_url || c.party_symbol_url}`} alt="" className="w-4 h-4 rounded-full object-cover" />
                )}
                #{c.candidate_number} {c.name}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="card p-5 mb-6">
        <h2 className="font-semibold mb-3">Election Lifecycle</h2>
        <div className="flex flex-wrap gap-2">
          {(NEXT_STEPS[election.status] || []).map((step) => (
            <button key={step.status} className="btn-primary" disabled={busy} onClick={() => transition(step.status)}>
              {step.label}
            </button>
          ))}
          {election.status === "CLOSED" && (
            <button className="btn-primary" disabled={busy} onClick={doCount}>
              Verify Ledger & Count Votes
            </button>
          )}
          {election.status === "VERIFICATION" && (
            <button className="btn-primary" disabled={busy} onClick={doApprove}>Approve Results</button>
          )}
          {election.status === "APPROVED" && (
            <button className="btn-primary" disabled={busy} onClick={doPublish}>Publish Results</button>
          )}
          {election.status === "PUBLISHED" && (
            <div className="flex gap-2">
              <button className="btn-secondary" disabled={busy} onClick={downloadPdf}>
                Download PDF Report
              </button>
              <button className="btn-secondary" disabled={busy} onClick={downloadExcel}>
                Download Excel Report
              </button>
            </div>
          )}
        </div>
      </div>

      {(countResult || publicResults) && (
        <div className="card p-5">
          <h2 className="font-semibold mb-4">Results</h2>
          {publicResults && (
            <div className="grid grid-cols-3 gap-4 mb-4 text-sm">
              <div><span className="label block">Eligible</span>{publicResults.eligible_voters}</div>
              <div><span className="label block">Votes Cast</span>{publicResults.votes_cast}</div>
              <div><span className="label block">Turnout</span>{publicResults.turnout_pct}%</div>
              <div><span className="label block">Winner</span>{publicResults.winner}</div>
              <div><span className="label block">Ledger Integrity</span>
                <span style={{ color: publicResults.integrity_verified ? "var(--color-accent)" : "var(--color-danger)" }}>
                  {publicResults.integrity_verified ? "Verified" : "FAILED"}
                </span>
              </div>
            </div>
          )}
          <div className="grid md:grid-cols-2 gap-6">
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={chartData} dataKey="votes" nameKey="name" outerRadius={80} label>
                  {chartData.map((_: any, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData}>
                <XAxis dataKey="name" fontSize={11} />
                <YAxis allowDecimals={false} fontSize={11} />
                <Tooltip />
                <Bar dataKey="votes" fill="var(--color-accent)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
