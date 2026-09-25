import { useEffect, useState } from "react";
import { api, apiErrorMessage } from "../lib/api";

export default function VotersPage() {
  const [voters, setVoters] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploadResult, setUploadResult] = useState<any>(null);
  const [error, setError] = useState("");

  const load = () => api.get("/voters", { params: { q } }).then((r) => {
    setVoters(r.data.voters);
    setTotal(r.data.total);
  });

  useEffect(() => { load(); }, [q]);

  const resetTotp = async (voterId: string) => {
    if (!confirm(`Reset TOTP for ${voterId}? They will need to re-enroll their authenticator before voting.`)) return;
    await api.post(`/voters/${voterId}/reset-totp`);
    load();
  };

  const deleteVoter = async (voterId: string) => {
    if (!confirm(`Delete voter ${voterId} from the registry? This cannot be undone.`)) return;
    setError("");
    try {
      await api.delete(`/voters/${voterId}`);
      load();
    } catch (err) { setError(apiErrorMessage(err)); }
  };

  const upload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setError(""); setUploadResult(null);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const r = await api.post("/voters/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setUploadResult(r.data);
      load();
    } catch (err) { setError(apiErrorMessage(err)); }
  };

  return (
    <div>
      <h1 style={{ fontFamily: "var(--font-display)" }} className="text-3xl font-bold mb-6">Voter Registry</h1>

      <div className="card p-5 mb-6">
        <h2 className="font-semibold mb-2">Upload Registry (CSV or Excel)</h2>
        <p className="text-xs text-gray-500 mb-3">Required columns: voter_id, name. Optional: date_of_birth, email, mobile, address, constituency.</p>
        <form onSubmit={upload} className="flex gap-2 items-center">
          <input type="file" accept=".csv,.xlsx,.xls" onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="text-sm" />
          <button className="btn-primary" disabled={!file}>Upload</button>
        </form>
        {error && <p className="text-sm mt-2" style={{ color: "var(--color-danger)" }}>{error}</p>}
        {uploadResult && (
          <div className="text-sm mt-3 space-y-1">
            <p>Created: {uploadResult.created} · Skipped (already existed): {uploadResult.skipped_existing} · Errors: {uploadResult.errors.length}</p>
            {uploadResult.errors.length > 0 && (
              <ul className="text-xs text-gray-500 list-disc pl-5 max-h-32 overflow-auto">
                {uploadResult.errors.map((e: any, i: number) => <li key={i}>Row {e.row}: {e.reason}</li>)}
              </ul>
            )}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold">Registered Voters ({total})</h2>
        <input className="input w-64" placeholder="Search by Voter ID or name" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left border-b" style={{ borderColor: "var(--color-line)" }}>
              <th className="p-3">Voter ID</th><th className="p-3">Name</th><th className="p-3">Constituency</th>
              <th className="p-3">Eligible</th><th className="p-3">Enrolled</th><th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {voters.map((v) => (
              <tr key={v.id} className="border-b" style={{ borderColor: "var(--color-line)" }}>
                <td className="p-3" style={{ fontFamily: "var(--font-mono)" }}>{v.voter_id}</td>
                <td className="p-3">{v.name}</td>
                <td className="p-3 text-gray-500">{v.constituency || "—"}</td>
                <td className="p-3">{v.is_eligible ? "Yes" : "No"}</td>
                <td className="p-3">{v.is_enrolled ? "Yes" : "No"}</td>
                <td className="p-3 text-right space-x-2">
                  {v.is_enrolled && (
                    <button className="btn-secondary text-xs py-1 px-2" onClick={() => resetTotp(v.voter_id)}>
                      Reset TOTP
                    </button>
                  )}
                  <button className="btn-secondary text-xs py-1 px-2" style={{ color: "var(--color-danger)" }}
                    onClick={() => deleteVoter(v.voter_id)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {voters.length === 0 && <p className="p-4 text-sm text-gray-400">No voters found.</p>}
      </div>
    </div>
  );
}
