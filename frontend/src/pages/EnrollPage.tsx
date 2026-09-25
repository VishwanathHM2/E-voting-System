import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiErrorMessage } from "../lib/api";
import WebcamCapture from "../components/WebcamCapture";

type Stage = "voter_id" | "password" | "totp" | "face" | "done";

export default function EnrollPage() {
  const navigate = useNavigate();
  const [stage, setStage] = useState<Stage>("voter_id");
  const [voterId, setVoterId] = useState("");
  const [voterName, setVoterName] = useState("");
  const [enrollToken, setEnrollToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [qr, setQr] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [alreadyEnrolled, setAlreadyEnrolled] = useState(false);
  const [loading, setLoading] = useState(false);

  const startEnrollment = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setAlreadyEnrolled(false); setLoading(true);
    try {
      const r = await api.post("/enrollment/start", { voter_id: voterId });
      setEnrollToken(r.data.enroll_token);
      setVoterName(r.data.voter_name);
      setStage("password");
    } catch (err: any) {
      const msg = apiErrorMessage(err);
      setError(msg);
      // Voter already has an account - most likely just lost their
      // authenticator. Point them at the right flow instead of a dead end.
      if (err?.response?.status === 400 && /already enrolled/i.test(msg)) {
        setAlreadyEnrolled(true);
      }
    } finally { setLoading(false); }
  };

  const setPasswordStep = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      const r = await api.post("/enrollment/set-password", {
        enroll_token: enrollToken, password, confirm_password: confirmPassword,
      });
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
      const r = await api.post("/enrollment/totp/confirm", { code }, { params: { enroll_token: enrollToken } });
      setEnrollToken(r.data.enroll_token);
      setStage("face");
    } catch (err) { setError(apiErrorMessage(err)); } finally { setLoading(false); }
  };

  const submitFace = async (frames: string[]) => {
    setError(""); setLoading(true);
    try {
      await api.post("/enrollment/face", { voter_id: voterId, images_b64: frames }, { params: { enroll_token: enrollToken } });
      setStage("done");
    } catch (err) { setError(apiErrorMessage(err)); } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="card p-8 w-full max-w-md">
        <h1 style={{ fontFamily: "var(--font-display)" }} className="text-2xl font-bold mb-1">Voter Enrollment</h1>
        <p className="text-sm text-gray-500 mb-6">One-time setup so you can vote. You must already be on the authorized voter registry.</p>

        {stage === "voter_id" && (
          <form onSubmit={startEnrollment} className="space-y-4">
            <div>
              <label className="label">Voter ID</label>
              <input className="input mt-1" required value={voterId} onChange={(e) => setVoterId(e.target.value)} />
            </div>
            {error && <p className="text-sm" style={{ color: "var(--color-danger)" }}>{error}</p>}
            {alreadyEnrolled && (
              <button type="button" className="btn-secondary w-full"
                onClick={() => navigate("/totp-recovery", { state: { voterId } })}>
                Re-enroll my authenticator instead
              </button>
            )}
            <button className="btn-primary w-full" disabled={loading}>{loading ? "Checking…" : "Continue"}</button>
            <p className="text-xs text-gray-400 text-center">
              Already enrolled but lost your authenticator?{" "}
              <button type="button" className="underline" onClick={() => navigate("/totp-recovery", { state: { voterId } })}>
                Re-enroll it here
              </button>
            </p>
          </form>
        )}

        {stage === "password" && (
          <form onSubmit={setPasswordStep} className="space-y-4">
            <p className="text-sm">Welcome, {voterName}. Set a password for your voter account.</p>
            <div>
              <label className="label">Password</label>
              <input className="input mt-1" type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
            <div>
              <label className="label">Confirm Password</label>
              <input className="input mt-1" type="password" required value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} />
            </div>
            {error && <p className="text-sm" style={{ color: "var(--color-danger)" }}>{error}</p>}
            <button className="btn-primary w-full" disabled={loading}>{loading ? "Saving…" : "Continue"}</button>
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
            <button className="btn-primary w-full" disabled={loading}>{loading ? "Verifying…" : "Continue"}</button>
          </form>
        )}

        {stage === "face" && (
          <div className="space-y-3">
            <p className="text-sm">Look at the camera. We'll capture a few frames to enroll your face.</p>
            <WebcamCapture autoCapture={5} onFrames={submitFace} />
            {loading && <p className="text-xs text-gray-400 text-center">Submitting…</p>}
            {error && <p className="text-sm text-center" style={{ color: "var(--color-danger)" }}>{error}</p>}
          </div>
        )}

        {stage === "done" && (
          <div className="text-center py-6">
            <p className="text-lg font-semibold" style={{ color: "var(--color-accent)" }}>Enrollment complete</p>
            <p className="text-sm text-gray-500 mt-2">You can now vote in open elections using your Voter ID, face, and authenticator code.</p>
          </div>
        )}
      </div>
    </div>
  );
}
