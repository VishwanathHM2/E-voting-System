import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api, apiErrorMessage } from "../lib/api";
import { useAuth } from "../context/AuthContext";

type Stage = "credentials" | "totp_setup" | "totp_verify";

export default function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [stage, setStage] = useState<Stage>("credentials");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [preToken, setPreToken] = useState("");
  const [qr, setQr] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submitCredentials = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const r = await api.post("/auth/login", { email, password });
      setPreToken(r.data.pre_auth_token);
      if (r.data.requires_totp_setup) {
        const qrRes = await api.post("/auth/totp/setup/begin", null, {
          params: { pre_auth_token: r.data.pre_auth_token },
        });
        setQr(qrRes.data.qr_code);
        setStage("totp_setup");
      } else {
        setStage("totp_verify");
      }
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const submitTotpSetup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const r = await api.post("/auth/totp/setup/confirm", { code }, { params: { pre_auth_token: preToken } });
      login(r.data.access_token, r.data.role);
      navigate("/admin/dashboard");
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const submitTotpVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const r = await api.post("/auth/totp/verify", { code }, { params: { pre_auth_token: preToken } });
      login(r.data.access_token, r.data.role);
      navigate("/admin/dashboard");
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="card p-8 w-full max-w-md">
        <h1 style={{ fontFamily: "var(--font-display)" }} className="text-2xl font-bold mb-1">
          Sign in
        </h1>
        <p className="text-sm text-gray-500 mb-6">Super Admin and Election Officer login.</p>

        {stage === "credentials" && (
          <form onSubmit={submitCredentials} className="space-y-4">
            <div>
              <label className="label">Email</label>
              <input className="input mt-1" type="email" required value={email}
                onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div>
              <label className="label">Password</label>
              <input className="input mt-1" type="password" required value={password}
                onChange={(e) => setPassword(e.target.value)} />
            </div>
            {error && <p className="text-sm" style={{ color: "var(--color-danger)" }}>{error}</p>}
            <button className="btn-primary w-full" disabled={loading}>{loading ? "Checking…" : "Continue"}</button>
          </form>
        )}

        {stage === "totp_setup" && (
          <form onSubmit={submitTotpSetup} className="space-y-4">
            <p className="text-sm">Scan this QR code with Google Authenticator, Aegis, or any TOTP app, then enter the 6-digit code.</p>
            {qr && <img src={qr} alt="TOTP QR code" className="mx-auto border rounded" style={{ borderColor: "var(--color-line)" }} />}
            <div>
              <label className="label">Authenticator Code</label>
              <input className="input mt-1 text-center tracking-widest" style={{ fontFamily: "var(--font-mono)" }}
                inputMode="numeric" maxLength={6} required value={code}
                onChange={(e) => setCode(e.target.value)} />
            </div>
            {error && <p className="text-sm" style={{ color: "var(--color-danger)" }}>{error}</p>}
            <button className="btn-primary w-full" disabled={loading}>{loading ? "Verifying…" : "Confirm & Sign in"}</button>
          </form>
        )}

        {stage === "totp_verify" && (
          <form onSubmit={submitTotpVerify} className="space-y-4">
            <p className="text-sm">Enter the 6-digit code from your authenticator app.</p>
            <div>
              <label className="label">Authenticator Code</label>
              <input className="input mt-1 text-center tracking-widest" style={{ fontFamily: "var(--font-mono)" }}
                inputMode="numeric" maxLength={6} required value={code}
                onChange={(e) => setCode(e.target.value)} />
            </div>
            {error && <p className="text-sm" style={{ color: "var(--color-danger)" }}>{error}</p>}
            <button className="btn-primary w-full" disabled={loading}>{loading ? "Verifying…" : "Sign in"}</button>
          </form>
        )}

        <p className="text-xs text-gray-400 mt-6 text-center">
          Voting as a registered voter? <Link to="/" className="underline">Go to the voter portal</Link>
        </p>
      </div>
    </div>
  );
}
