"""
Election-day flow (liveness detection intentionally out of scope for this
build, per project decision - see README):

voter_id -> registry check -> eligibility -> enrollment check -> face match
(exact voter_id template) -> issue face_session_token -> TOTP verify +
election-eligibility + already-voted check -> encrypt ballot -> ledger entry
-> participation record, all inside one DB transaction.
"""
import datetime
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..database import get_db
from .. import models, schemas, face_service, totp as totp_service, crypto, ledger, audit
from ..deps import issue_face_session_token, verify_face_session_token

router = APIRouter(prefix="/api/voting", tags=["voting"])


def _load_voter_or_404(db, voter_id):
    voter = db.query(models.Voter).filter(models.Voter.voter_id == voter_id).first()
    if not voter:
        raise HTTPException(404, "Access denied: voter not found")
    return voter


@router.get("/check/{voter_id}/{election_id}")
def check_voter_status(voter_id: str, election_id: str, db: Session = Depends(get_db)):
    """Step 1: basic checks before biometric/TOTP steps even start."""
    voter = _load_voter_or_404(db, voter_id)
    election = db.query(models.Election).filter(models.Election.id == election_id).first()
    if not election:
        raise HTTPException(404, "Election not found")

    reasons = []
    if not voter.is_eligible:
        reasons.append("voter_not_eligible")
    if not voter.is_enrolled or not voter.face_enrolled:
        reasons.append("voter_not_enrolled")
    if election.status != models.ElectionStatus.OPEN:
        reasons.append("election_not_open")
    if election.eligible_constituency and election.eligible_constituency != voter.constituency:
        reasons.append("not_eligible_for_this_election")
    already_voted = db.query(models.Participation).filter(
        models.Participation.voter_id == voter.id, models.Participation.election_id == election_id).first()
    if already_voted:
        reasons.append("already_voted")

    if reasons:
        audit.log(db, "VOTING_ACCESS_DENIED", target=voter_id, details={"reasons": reasons}, success=False)
        raise HTTPException(403, {"message": "ACCESS DENIED", "reasons": reasons})

    return {"can_proceed": True}


@router.post("/face-verify")
def face_verify(req: schemas.FaceVerifyRequest, db: Session = Depends(get_db)):
    voter = _load_voter_or_404(db, req.voter_id)
    if not voter.face_enrolled or not voter.face_embedding:
        raise HTTPException(400, "Voter has no enrolled face template")

    result = face_service.extract_embedding(req.image_b64)
    if not result["ok"]:
        audit.log(db, "FACE_VERIFY_FAILED", target=req.voter_id, details={"reason": result["reason"]}, success=False)
        raise HTTPException(401, f"Face verification failed: {result['reason']}")

    stored_embedding = json.loads(voter.face_embedding)
    if not face_service.matches(result["embedding"], stored_embedding):
        audit.log(db, "FACE_VERIFY_MISMATCH", target=req.voter_id, success=False)
        raise HTTPException(401, "Face does not match the enrolled template for this Voter ID")

    audit.log(db, "FACE_VERIFY_SUCCESS", target=req.voter_id)
    return {"matched": True}


@router.post("/face-session-token")
def get_face_session_token(voter_id: str, election_id: str):
    """Issued by the frontend only after /face-verify returned matched=true
    for this exact voter_id (see README for the trust model of this MVP)."""
    return {"token": issue_face_session_token(voter_id, election_id)}


@router.post("/cast")
def cast_vote(req: schemas.CastVoteRequest, db: Session = Depends(get_db)):
    voter = _load_voter_or_404(db, req.voter_id)
    election = db.query(models.Election).filter(models.Election.id == req.election_id).first()
    if not election:
        raise HTTPException(404, "Election not found")

    # Re-check everything server-side - never trust prior client-side steps alone.
    if not voter.is_eligible or not voter.is_enrolled or not voter.face_enrolled:
        raise HTTPException(403, "ACCESS DENIED: not an eligible enrolled voter")
    if election.status != models.ElectionStatus.OPEN:
        raise HTTPException(403, "ACCESS DENIED: election is not open")
    if election.eligible_constituency and election.eligible_constituency != voter.constituency:
        raise HTTPException(403, "ACCESS DENIED: not eligible for this election")

    if not verify_face_session_token(req.face_session_token, req.voter_id, req.election_id):
        audit.log(db, "VOTE_REJECTED_NO_FACE_TOKEN", target=req.voter_id, success=False)
        raise HTTPException(401, "Face verification step missing or expired - restart voting flow")

    user = db.query(models.User).filter(models.User.id == voter.user_id).first()
    if not user or not user.totp_enrolled or not user.totp_secret_encrypted:
        raise HTTPException(400, "TOTP not enrolled for this voter")
    secret = totp_service.decrypt_secret(user.totp_secret_encrypted)
    if not totp_service.verify_code(secret, req.totp_code):
        audit.log(db, "VOTE_REJECTED_BAD_TOTP", target=req.voter_id, success=False)
        raise HTTPException(401, "Invalid TOTP code")

    candidate = db.query(models.Candidate).filter(
        models.Candidate.id == req.candidate_id, models.Candidate.election_id == req.election_id,
        models.Candidate.is_active == True).first()
    if not candidate:
        raise HTTPException(400, "Invalid candidate for this election")

    # Encrypt ballot BEFORE any DB writes for this vote.
    enc = crypto.encrypt(json.dumps({"candidate_id": req.candidate_id}))

    try:
        # Participation row is created first inside the same transaction;
        # the UNIQUE(voter_id, election_id) constraint is the real
        # concurrency-safe duplicate-vote guard (DB-enforced, not app logic).
        participation = models.Participation(voter_id=voter.id, election_id=req.election_id)
        db.add(participation)
        db.flush()  # raises IntegrityError immediately on duplicate, before ballot is written

        ballot = models.Ballot(
            election_id=req.election_id, ciphertext=enc["ciphertext"], nonce=enc["nonce"],
            tag=enc["tag"], integrity_hash=enc["integrity_hash"],
        )
        db.add(ballot)
        db.flush()

        block = ledger.add_block(db, "BALLOT_CAST", {
            "election_id": req.election_id, "ballot_id": ballot.id,
            "integrity_hash": enc["integrity_hash"], "timestamp": datetime.datetime.utcnow().isoformat(),
        }, election_id=req.election_id, submitted_by="voting_service")
        ballot.ledger_tx_id = block.tx_id

        db.commit()
    except IntegrityError:
        db.rollback()
        audit.log(db, "VOTE_REJECTED_DUPLICATE", target=req.voter_id, success=False)
        raise HTTPException(409, "ACCESS DENIED: this voter has already voted in this election")
    except Exception as e:
        db.rollback()
        audit.log(db, "VOTE_SUBMISSION_ERROR", target=req.voter_id, details={"error": str(e)}, success=False)
        raise HTTPException(500, "Vote could not be recorded - no vote was counted. Please retry.")

    audit.log(db, "VOTE_CAST", target=req.voter_id, details={"election_id": req.election_id})
    return {"message": "Vote recorded successfully", "ballot_tx_id": block.tx_id}
