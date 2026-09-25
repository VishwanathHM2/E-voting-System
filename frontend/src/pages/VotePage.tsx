import { useState } from "react";
import { api, apiErrorMessage, SERVER_ORIGIN } from "../lib/api";
import WebcamCapture from "../components/WebcamCapture";

type Stage = "voter_id" | "elections" | "face" | "ballot" | "done" | "denied";

export default function VotePage() {
  const [stage, setStage] = useState<Stage>("voter_id");
  const [voterId, setVoterId] = useState("");
  const [elections, setElections] = useState<any[]>([]);
  const [electionId, setElectionId] = useState("");
  const [candidates, setCandidates] = useState<any[]>([]);
  const [candidateId, setCandidateId] = useState("");
  const [faceToken, setFaceToken] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [ballotTx, setBallotTx] = useState("");

  const loadElections = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      const r = await api.get("/elections/public", { params: { voter_id: voterId } });
      setElections(r.data);
      setStage("elections");
    } catch (err) { setError(apiErrorMessage(err)); } finally { setLoading(false); }
  };

  const chooseElection = async (id: string) => {
    setError(""); setLoading(true);
    try {
      await api.get(`/voting/check/${voterId}/${id}`);
      const c = await api.get(`/candidates/election/${id}`);
      setCandidates(c.data);
      setElectionId(id);
      setStage("face");
    } catch (err) { setError(apiErrorMessage(err)); setStage("denied"); } finally { setLoading(false); }
  };

  const verifyFace = async (frame: string) => {
    setError(""); setLoading(true);
    try {
      await api.post("/voting/face-verify", { voter_id: voterId, image_b64: frame });
      const t = await api.post("/voting/face-session-token", null, { params: { voter_id: voterId, election_id: electionId } });
      setFaceToken(t.data.token);
      setStage("ballot");
    } catch (err) { setError(apiErrorMessage(err)); } finally { setLoading(false); }
  };

  const castVote = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      const r = await api.post("/voting/cast", {
        voter_id: voterId, election_id: electionId, candidate_id: candidateId,
        totp_code: code, face_session_token: faceToken,
      });
      setBallotTx(r.data.ballot_tx_id);
      setStage("done");
    } catch (err) { setError(apiErrorMessage(err)); } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="card p-8 w-full max-w-md">
        <h1 style={{ fontFamily: "var(--font-display)" }} className="text-2xl font-bold mb-1">Cast Your Vote</h1>
        <p className="text-sm text-gray-500 mb-6">Enter your Voter ID to begin.</p>

        {stage === "voter_id" && (
          <form onSubmit={loadElections} className="space-y-4">
            <div>
              <label className="label">Voter ID</label>
              <input className="input mt-1" required value={voterId} onChange={(e) => setVoterId(e.target.value)} />
            </div>
            {error && <p className="text-sm" style={{ color: "var(--color-danger)" }}>{error}</p>}
            <button className="btn-primary w-full" disabled={loading}>{loading ? "Loading…" : "Continue"}</button>
          </form>
        )}

        {stage === "elections" && (
          <div className="space-y-2">
            {elections.length === 0 && <p className="text-sm text-gray-400">No elections are currently open.</p>}
            {elections.map((e) => (
              <button key={e.id} onClick={() => chooseElection(e.id)} disabled={loading}
                className="w-full text-left card p-3 hover:shadow-sm">
                <div className="font-medium">{e.name}</div>
                <div className="text-xs text-gray-400">Closes {new Date(e.end_time).toLocaleString()}</div>
              </button>
            ))}
            {error && <p className="text-sm" style={{ color: "var(--color-danger)" }}>{error}</p>}
          </div>
        )}

        {stage === "denied" && (
          <div className="text-center py-4">
            <p className="font-semibold mb-2" style={{ color: "var(--color-danger)" }}>Access Denied</p>
            <p className="text-sm text-gray-500">{error}</p>
          </div>
        )}

        {stage === "face" && (
          <div className="space-y-3">
            <p className="text-sm">Look at the camera to verify your identity.</p>
            <WebcamCapture onSingleCapture={verifyFace} />
            {loading && <p className="text-xs text-gray-400 text-center">Verifying…</p>}
            {error && <p className="text-sm text-center" style={{ color: "var(--color-danger)" }}>{error}</p>}
          </div>
        )}

        {stage === "ballot" && (
          <form onSubmit={castVote} className="space-y-4">
            <p className="text-sm">Identity verified. Select a candidate and enter your authenticator code to submit.</p>
            <div className="space-y-2">
              {candidates.map((c) => (
                <label key={c.id} className="flex items-center gap-3 card p-3 cursor-pointer"
                  style={{ borderColor: candidateId === c.id ? "var(--color-accent)" : "var(--color-line)" }}>
                  <input type="radio" name="candidate" required value={c.id}
                    checked={candidateId === c.id} onChange={() => setCandidateId(c.id)} />
                  {c.symbol_url && (
                    <img src={`${SERVER_ORIGIN}${c.symbol_url}`} alt={`${c.name} symbol`}
                      className="w-10 h-10 rounded object-cover border" style={{ borderColor: "var(--color-line)" }} />
                  )}
                  <div>
                    <div className="font-medium">{c.name}</div>
                    {c.party && <div className="text-xs text-gray-400">{c.party}</div>}
                  </div>
                </label>
              ))}
            </div>
            <div>
              <label className="label">Authenticator Code</label>
              <input className="input mt-1 text-center tracking-widest" style={{ fontFamily: "var(--font-mono)" }}
                inputMode="numeric" maxLength={6} required value={code} onChange={(e) => setCode(e.target.value)} />
            </div>
            {error && <p className="text-sm" style={{ color: "var(--color-danger)" }}>{error}</p>}
            <button className="btn-primary w-full" disabled={loading || !candidateId}>{loading ? "Submitting…" : "Cast Vote"}</button>
          </form>
        )}

        {stage === "done" && (
          <div className="text-center py-6">
            <p className="text-lg font-semibold" style={{ color: "var(--color-accent)" }}>Vote recorded successfully</p>
            <p className="text-xs text-gray-400 mt-2" style={{ fontFamily: "var(--font-mono)" }}>Ledger TX: {ballotTx}</p>
            <p className="text-sm text-gray-500 mt-3">Your vote has been encrypted and recorded. Thank you for voting.</p>
          </div>
        )}
      </div>
    </div>
  );
}
