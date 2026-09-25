import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api, apiErrorMessage } from "../lib/api";

type Stage = "credentials" | "totp" | "done";

export default function TotpRecoveryPage() {
  const location = useLocation();
  const prefillVoterId = (location.state as { voterId?: string } | null)?.voterId || "";
  const [stage, setStage] = useState<Stage>("credentials");
  const [voterId, setVoterId] = useState(prefillVoterId);
  const [password, setPassword] = useState("");
  const [enrollToken, setEnrollToken] = useState("");
  const [qr, setQr] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submitCredentials = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      const r = await api.post("/enrollment/totp-recovery/start", { voter_id: voterId, password });
      setEnrollToken(r.data.enroll_token);
      const qrRes = await api.post("/enrollment/totp/begin", null, { params: { enroll_token: r.data.enroll_token } });
      setQr(qrRes.data.qr_code);
      setStage("totp");
    } catch (err) { setError(apiErrorMessage(err)); } finally { setLoading(false); }
  };

  const confirmTotp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      await api.post("/enrollment/totp/confirm", { code }, { params: { enroll_token: enrollToken } });
      setStage("done");
    } catch (err) { setError(apiErrorMessage(err)); } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="card p-8 w-full max-w-md">
        <h1 style={{ fontFamily: "var(--font-display)" }} className="text-2xl font-bold mb-1">Re-enroll Authenticator</h1>
        <p className="text-sm text-gray-500 mb-6">
          Only works if an administrator has already reset your TOTP after you reported losing access.
        </p>

        {stage === "credentials" && (
          <form onSubmit={submitCredentials} className="space-y-4">
            <div>
              <label className="label">Voter ID</label>
              <input className="input mt-1" required value={voterId} onChange={(e) => setVoterId(e.target.value)} />
            </div>
            <div>
              <label className="label">Your Voter Account Password</label>
              <input className="input mt-1" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            {error && <p className="text-sm" style={{ color: "var(--color-danger)" }}>{error}</p>}
            <button className="btn-primary w-full" disabled={loading}>{loading ? "Checking…" : "Continue"}</button>
          </form>
        )}

        {stage === "totp" && (
          <form onSubmit={confirmTotp} className="space-y-4">
            <p className="text-sm">Scan this with your authenticator app, then enter the 6-digit code.</p>
            {qr && <img src={qr} alt="QR" className="mx-auto border rounded" style={{ borderColor: "var(--color-line)" }} />}
            <div>
              <label className="label">Authenticator Code</label>
              <input className="input mt-1 text-center tracking-widest" style={{ fontFamily: "var(--font-mono)" }}
                inputMode="numeric" maxLength={6} required value={code} onChange={(e) => setCode(e.target.value)} />
            </div>
            {error && <p className="text-sm" style={{ color: "var(--color-danger)" }}>{error}</p>}
            <button className="btn-primary w-full" disabled={loading}>{loading ? "Verifying…" : "Confirm"}</button>
          </form>
        )}

        {stage === "done" && (
          <div className="text-center py-6">
            <p className="text-lg font-semibold" style={{ color: "var(--color-accent)" }}>Authenticator re-enrolled</p>
            <p className="text-sm text-gray-500 mt-2">
              You can now vote using your Voter ID, face, and the new authenticator code.
            </p>
          </div>
        )}

        <p className="text-xs text-gray-400 mt-6 text-center">
          <Link to="/enroll" className="underline">Back to enrollment</Link>
        </p>
      </div>
    </div>
  );
}
