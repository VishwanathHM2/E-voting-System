"""
Post-election counting/results.
CLOSED -> blockchain integrity verify -> COUNTING (decrypt & tally) ->
VERIFICATION -> APPROVED (super admin) -> PUBLISHED (public).
"""
import json
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, crypto, ledger, audit
from ..deps import require_roles, check_election_access

router = APIRouter(prefix="/api/results", tags=["results"])


@router.post("/{election_id}/verify-ledger")
def verify_ledger(election_id: str, db: Session = Depends(get_db),
                   user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN, models.Role.ELECTION_OFFICER))):
    election = _get_election(db, election_id)
    check_election_access(election, user, db)
    if election.status != models.ElectionStatus.CLOSED:
        raise HTTPException(400, "Election must be CLOSED before ledger verification")
    result = ledger.verify_chain(db)
    audit.log(db, "LEDGER_INTEGRITY_CHECK", actor_id=user.id, actor_role=user.role.value,
               target=election_id, details=result, success=result["valid"])
    if not result["valid"]:
        raise HTTPException(409, {"message": "LEDGER INTEGRITY FAILURE - result approval blocked", **result})
    return result


@router.post("/{election_id}/count")
def count_votes(election_id: str, db: Session = Depends(get_db),
                 user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN, models.Role.ELECTION_OFFICER))):
    election = _get_election(db, election_id)
    check_election_access(election, user, db)
    if election.status != models.ElectionStatus.CLOSED:
        raise HTTPException(400, "Election must be CLOSED before counting")

    ledger_check = ledger.verify_chain(db)
    if not ledger_check["valid"]:
        raise HTTPException(409, {"message": "Cannot count: ledger integrity check failed", **ledger_check})

    ballots = db.query(models.Ballot).filter(models.Ballot.election_id == election_id).all()
    tally = Counter()
    decrypt_failures = 0
    for b in ballots:
        if not crypto.verify_integrity(b.ciphertext, b.nonce, b.tag, b.integrity_hash):
            decrypt_failures += 1
            continue
        try:
            pt = crypto.decrypt(b.ciphertext, b.nonce, b.tag)
            candidate_id = json.loads(pt)["candidate_id"]
            b.decrypted_candidate_id = candidate_id
            tally[candidate_id] += 1
        except Exception:
            decrypt_failures += 1

    election.status = models.ElectionStatus.COUNTING
    db.commit()

    candidates = db.query(models.Candidate).filter(models.Candidate.election_id == election_id).all()
    cand_map = {c.id: c for c in candidates}
    total_votes = sum(tally.values())
    results = [{
        "candidate_id": cid, "name": cand_map[cid].name if cid in cand_map else "Unknown",
        "votes": count, "percentage": round(count / total_votes * 100, 2) if total_votes else 0,
    } for cid, count in tally.items()]
    results.sort(key=lambda r: r["votes"], reverse=True)

    election.status = models.ElectionStatus.VERIFICATION
    db.commit()

    audit.log(db, "VOTES_COUNTED", actor_id=user.id, actor_role=user.role.value, target=election_id,
               details={"total_ballots": len(ballots), "total_valid": total_votes, "decrypt_failures": decrypt_failures})
    ledger.add_block(db, "COUNTING_COMPLETED",
                      {"election_id": election_id, "total_votes": total_votes, "decrypt_failures": decrypt_failures},
                      election_id=election_id, submitted_by=user.id)

    return {"status": "VERIFICATION", "total_votes": total_votes, "decrypt_failures": decrypt_failures, "results": results}


@router.post("/{election_id}/approve")
def approve_results(election_id: str, db: Session = Depends(get_db),
                     user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN))):
    election = _get_election(db, election_id)
    if election.status != models.ElectionStatus.VERIFICATION:
        raise HTTPException(400, "Election must be in VERIFICATION status")
    ledger_check = ledger.verify_chain(db)
    if not ledger_check["valid"]:
        raise HTTPException(409, "Cannot approve: ledger integrity check failed")
    election.status = models.ElectionStatus.APPROVED
    db.commit()
    audit.log(db, "RESULTS_APPROVED", actor_id=user.id, actor_role=user.role.value, target=election_id)
    ledger.add_block(db, "RESULTS_APPROVED", {"election_id": election_id}, election_id=election_id, submitted_by=user.id)
    return {"status": "APPROVED"}


@router.post("/{election_id}/publish")
def publish_results(election_id: str, db: Session = Depends(get_db),
                     user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN))):
    election = _get_election(db, election_id)
    if election.status != models.ElectionStatus.APPROVED:
        raise HTTPException(400, "Election must be APPROVED before publishing")
    election.status = models.ElectionStatus.PUBLISHED
    db.commit()
    audit.log(db, "RESULTS_PUBLISHED", actor_id=user.id, actor_role=user.role.value, target=election_id)
    ledger.add_block(db, "RESULTS_PUBLISHED", {"election_id": election_id}, election_id=election_id, submitted_by=user.id)
    return {"status": "PUBLISHED"}


@router.get("/{election_id}/public")
def public_results(election_id: str, db: Session = Depends(get_db)):
    election = _get_election(db, election_id)
    if election.status != models.ElectionStatus.PUBLISHED:
        raise HTTPException(403, "Results are not yet published")

    ballots = db.query(models.Ballot).filter(models.Ballot.election_id == election_id).all()
    tally = Counter(b.decrypted_candidate_id for b in ballots if b.decrypted_candidate_id)
    candidates = db.query(models.Candidate).filter(models.Candidate.election_id == election_id).all()
    cand_map = {c.id: c for c in candidates}
    total_votes = sum(tally.values())
    results = [{
        "candidate_id": cid, "name": cand_map[cid].name if cid in cand_map else "Unknown",
        "votes": count, "percentage": round(count / total_votes * 100, 2) if total_votes else 0,
    } for cid, count in tally.items()]
    results.sort(key=lambda r: r["votes"], reverse=True)
    eligible = db.query(models.Voter).filter(models.Voter.is_eligible == True).count()
    votes_cast = db.query(models.Participation).filter(models.Participation.election_id == election_id).count()
    ledger_check = ledger.verify_chain(db)

    return {
        "election_name": election.name, "status": election.status.value,
        "eligible_voters": eligible, "votes_cast": votes_cast,
        "turnout_pct": round(votes_cast / eligible * 100, 2) if eligible else 0,
        "winner": results[0]["name"] if results else None,
        "results": results,
        "integrity_verified": ledger_check["valid"],
    }


def _get_election(db, election_id):
    e = db.query(models.Election).filter(models.Election.id == election_id).first()
    if not e:
        raise HTTPException(404, "Election not found")
    return e
