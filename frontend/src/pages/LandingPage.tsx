import { useNavigate } from "react-router-dom";

export default function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen flex items-center justify-center px-4 relative">
      <button onClick={() => navigate("/login")}
        className="absolute top-6 left-6 text-sm text-gray-400 hover:text-black flex items-center gap-1">
        ← Back
      </button>

      <div className="w-full max-w-md text-center">
        <h1 style={{ fontFamily: "var(--font-display)" }} className="text-4xl font-bold mb-2">Evote</h1>
        <p className="text-sm mb-10 text-gray-500">
          Every vote encrypted. Every result verifiable.
        </p>

        <button onClick={() => navigate("/vote")} className="card p-8 text-left hover:shadow-sm transition w-full mb-4">
          <div className="text-xl font-semibold mb-1">Cast Your Vote</div>
          <p className="text-sm text-gray-500">
            Already enrolled? Vote in an open election using your Voter ID.
          </p>
        </button>

        <button onClick={() => navigate("/enroll")} className="btn-secondary w-full">
          Enroll to Vote
        </button>

        <p className="text-xs text-gray-400 mt-8">
          Lost your authenticator after enrolling? <button onClick={() => navigate("/totp-recovery")} className="underline">Re-enroll it here</button>
        </p>
      </div>
    </div>
  );
}
