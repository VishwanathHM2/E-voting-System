# SecureEVote — Local Setup Guide

E-voting system: TOTP 2FA, face-recognition
verification, AES-256-GCM encrypted ballots, and a tamper-evident hash-chain
ledger.
**Not certified for government or public elections.** This is an
organizational/institutional election platform.

## What's real vs. simplified

Be upfront about these — a panel will ask, and it's better to have already
answered it in your report.

| Feature | What the spec asked for | What's built | Why |
|---|---|---|---|
| Blockchain | Hyperledger Fabric (multi-node permissioned network) | A genuine SHA-256 hash-chain ledger: every block commits to the previous block's hash, append-only, tamper-evident, integrity-verifiable. Only the backend service can write to it (no anonymous writes). | Fabric needs Docker, multiple peer/orderer nodes, chaincode in Go, and days of setup even for people who've done it before. Not viable in 4 days. The `ledger.py` module is small and swappable — `add_block()`/`verify_chain()` is the only interface the rest of the app depends on. |
| Liveness detection | Blink/head-turn challenge-response | **Not implemented** — explicitly descoped per your instruction. Face verification only checks that the live photo matches the enrolled voter's face. | Time. Documented as a known gap — say this plainly if asked. |
| Face recognition | dlib/InsightFace/ArcFace deep embeddings | OpenCV Haar-cascade face detection + normalized HOG feature descriptors as the "embedding," compared by Euclidean distance | `face_recognition` (dlib) failed to build from source in the dev environment — a very common real-world problem with that library (needs CMake + a C++ toolchain + 10-20 min to compile). HOG descriptors are a legitimate, classical, pre-deep-learning face recognition technique — not pixel-diffing — but less accurate than a deep embedding model. Say this honestly. |
| Database | PostgreSQL | SQLite (file: `backend/evoting.db`) | You asked for local-only, no deploy setup. Swapping to Postgres is a one-line change in `config.py` (`DATABASE_URL`) plus `pip install psycopg2-binary` — SQLAlchemy abstracts the rest. |
| Migrations | Alembic | `Base.metadata.create_all()` on startup | Fine for a local/demo system; not how you'd run this in production. |

Everything else — TOTP (RFC 6238, via `pyotp`), AES-256-GCM ballot encryption,
argon2 password hashing, RBAC enforced server-side, election lifecycle state
machine, duplicate-vote prevention (DB unique constraint + transaction),
duplicate-face-enrollment detection, audit logging, PDF/Excel reports — is
implemented for real and was tested end-to-end (see "What was tested" below).

## Recently added (post-initial-build)

- **TOTP recovery**: `/api/voters/{voter_id}/reset-totp` (admin/officer) clears
  a voter's TOTP enrollment. The voter then re-enrolls at `/totp-recovery`
  (frontend) using their voter_id + existing account password — no need to
  redo face enrollment or their password.
- **Officer-election assignment enforcement**: an `ELECTION_OFFICER` can only
  view/manage elections where `officer_id` matches their own account
  (assigned at election creation by the Super Admin). Unassigned elections
  are Super-Admin-only. Enforced server-side via `deps.check_election_access`.
- **`/` redirect fix**: root path now checks `/api/setup/status` and sends
  you to `/setup`, `/login`, or `/admin/dashboard` as appropriate, instead of
  always dumping you on the staff login page.

## Prerequisites

- Python 3.10+
- Node.js 18+
- A webcam (for face enrollment/voting — the browser will ask for camera permission)

## Backend setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

First run auto-creates `evoting.db` (SQLite) and `.local_enc_key` (the
AES-256 key used to encrypt ballots and TOTP secrets — for local/dev only;
in production this must come from a real secrets manager, not a file).

API docs: http://127.0.0.1:8000/docs (FastAPI auto-generates this — useful
for demoing every endpoint directly in your viva without needing the UI).

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Opens at http://127.0.0.1:5173. The frontend expects the backend at
`http://127.0.0.1:8000` (hardcoded in `src/lib/api.ts` — change if needed).

## Demo walkthrough

1. Visit the frontend → redirected to `/setup` on first run. Create the
   founding Super Admin account (org name, name, email, password). This
   endpoint permanently disables itself after first use.
2. Log in at `/login` with that email/password. First login forces TOTP
   enrollment — scan the QR code with Google Authenticator, Aegis, or any
   RFC 6238 app, enter the 6-digit code.
3. From the Super Admin dashboard:
   - **Voter Registry** → upload a CSV with columns `voter_id,name` (optionally
     `email,mobile,address,constituency,date_of_birth`). A sample is at
     `backend/sample_voters.csv`.
   - **Elections** → create an election, add candidates, move it
     DRAFT → SCHEDULED → OPEN.
4. Open a new browser tab/window (or incognito) → go to `/enroll`. Enter a
   Voter ID from your uploaded registry, set a password, scan the TOTP QR,
   enter the code, then capture your face (webcam, 5 frames).
5. Go to `/vote`. Enter the same Voter ID, pick the open election, verify
   your face, select a candidate, enter your authenticator code, submit.
6. Back in the admin panel: close the election, click "Verify Ledger & Count
   Votes," then "Approve Results," then "Publish Results." Charts and a
   download link for PDF/Excel reports appear once published.
7. **Audit & Ledger** page shows every hash-chain block and the full audit
   trail, with a one-click "verify ledger integrity" check.

## What was tested end-to-end (automated, this session)

System init → admin login → TOTP setup/verify → CSV voter upload → election
create → candidate add → lifecycle transitions → voter enrollment (password →
TOTP → face, 4 frames) → election-day flow (eligibility check → face verify →
face-session-token → TOTP → cast vote, AES-256-GCM encrypted, written to
ledger) → **duplicate vote correctly rejected (409)** → **duplicate face
enrollment correctly rejected (409, reused photo across two voter IDs)** →
close election → ledger integrity verify → count/decrypt ballots → approve →
publish → public results endpoint → PDF report generated → Excel report
generated → audit log → ledger view → admin dashboard stats.

Not automated-tested: the React frontend's actual browser behavior (webcam
capture, multi-step forms) — it builds clean (`npm run build`, zero
TypeScript errors) and calls the same endpoints the automated test exercised,
but click through it yourself before your demo/viva to catch any UI rough
edges.

## Security notes worth knowing (and being able to explain)

- Role is **always** re-derived from the database on every request via the
  JWT subject — never trusted from the frontend.
- Duplicate voting is blocked by a **database UNIQUE constraint**
  (`voter_id, election_id`), not application-level checking — this is what
  actually makes it safe under concurrent requests.
- Ballots are encrypted (AES-256-GCM) and stored separately from the
  participation record — there is no queryable `voter → candidate` mapping
  anywhere in the schema.
- TOTP secrets are encrypted at rest (same AES-256-GCM service) and never
  returned by any API response after initial QR generation.
- Face session tokens are short-lived (120s), single-purpose JWTs scoped to
  one voter+election pair — casting a vote without a valid one is rejected
  server-side even if someone skips the frontend's face-verify step.
