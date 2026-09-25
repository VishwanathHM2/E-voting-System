from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas, audit, ledger
from ..deps import require_roles, check_election_access

router = APIRouter(prefix="/api/elections", tags=["elections"])


@router.post("")
def create_election(req: schemas.ElectionCreate, db: Session = Depends(get_db),
                     user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN))):
    if req.end_time <= req.start_time:
        raise HTTPException(400, "end_time must be after start_time")
    election = models.Election(
        name=req.name, description=req.description, election_type=req.election_type,
        election_level=req.election_level,
        start_time=req.start_time, end_time=req.end_time,
        eligible_constituency=req.eligible_constituency,
        created_by=user.id, status=models.ElectionStatus.DRAFT,
    )
    db.add(election)
    db.commit()
    db.refresh(election)

    for officer_id in (req.officer_ids or []):
        officer = db.query(models.User).filter(models.User.id == officer_id,
                                                 models.User.role == models.Role.ELECTION_OFFICER).first()
        if officer:
            db.add(models.ElectionOfficer(election_id=election.id, officer_id=officer_id))
    db.commit()

    audit.log(db, "ELECTION_CREATED", actor_id=user.id, actor_role=user.role.value, target=election.id)
    ledger.add_block(db, "ELECTION_CREATED", {"election_id": election.id, "name": election.name},
                      election_id=election.id, submitted_by=user.id)
    return _serialize(election, db)


@router.get("")
def list_elections(q: Optional[str] = None, db: Session = Depends(get_db), user: models.User = Depends(require_roles(
        models.Role.SUPER_ADMIN, models.Role.ELECTION_OFFICER))):
    query = db.query(models.Election)
    if user.role == models.Role.ELECTION_OFFICER:
        # Officers only see elections they're explicitly assigned to.
        assigned_ids = [row.election_id for row in db.query(models.ElectionOfficer).filter(
            models.ElectionOfficer.officer_id == user.id).all()]
        query = query.filter(models.Election.id.in_(assigned_ids)) if assigned_ids else query.filter(False)
    if q:
        like = f"%{q}%"
        query = query.filter((models.Election.name.ilike(like)) | (models.Election.eligible_constituency.ilike(like)))
    return [_serialize(e, db) for e in query.order_by(models.Election.created_at.desc()).all()]


@router.get("/public")
def list_public_elections(voter_id: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Voters can see OPEN elections without auth. If voter_id is supplied,
    the list is filtered to elections with no region restriction, or whose
    eligible_constituency matches that voter's own constituency - a voter
    should never even see an election they're not eligible for.
    """
    query = db.query(models.Election).filter(models.Election.status == models.ElectionStatus.OPEN)
    voter_constituency = None
    if voter_id:
        voter = db.query(models.Voter).filter(models.Voter.voter_id == voter_id).first()
        if voter:
            voter_constituency = voter.constituency
    elections = query.all()
    result = []
    for e in elections:
        if e.eligible_constituency and voter_id and e.eligible_constituency != voter_constituency:
            continue
        result.append({"id": e.id, "name": e.name, "start_time": e.start_time, "end_time": e.end_time,
                        "eligible_constituency": e.eligible_constituency})
    return result


@router.get("/{election_id}")
def get_election(election_id: str, db: Session = Depends(get_db)):
    e = db.query(models.Election).filter(models.Election.id == election_id).first()
    if not e:
        raise HTTPException(404, "Election not found")
    # Intentionally not role-gated here: candidates page, voting flow, and
    # public-results pages all read this endpoint without an admin session.
    return _serialize(e, db)


@router.delete("/{election_id}")
def delete_election(election_id: str, db: Session = Depends(get_db),
                     user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN))):
    """Only DRAFT elections can actually be deleted - once SCHEDULED or
    later, an election has been committed to (candidates finalized,
    possibly visible to voters/officers), so it must be handled via the
    normal lifecycle instead. Super Admin only; officers never get this."""
    e = db.query(models.Election).filter(models.Election.id == election_id).first()
    if not e:
        raise HTTPException(404, "Election not found")
    if e.status != models.ElectionStatus.DRAFT:
        raise HTTPException(400, "Only DRAFT elections can be deleted. Use the lifecycle actions instead.")

    db.query(models.Candidate).filter(models.Candidate.election_id == election_id).delete()
    db.query(models.ElectionOfficer).filter(models.ElectionOfficer.election_id == election_id).delete()
    election_name = e.name
    db.delete(e)
    db.commit()

    audit.log(db, "ELECTION_DELETED", actor_id=user.id, actor_role=user.role.value, target=election_id,
               details={"name": election_name})
    ledger.add_block(db, "ELECTION_DELETED", {"election_id": election_id, "name": election_name},
                      election_id=election_id, submitted_by=user.id)
    return {"message": "Election deleted"}


@router.post("/{election_id}/officers")
def add_officer(election_id: str, officer_id: str, db: Session = Depends(get_db),
                 user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN))):
    e = db.query(models.Election).filter(models.Election.id == election_id).first()
    if not e:
        raise HTTPException(404, "Election not found")
    officer = db.query(models.User).filter(models.User.id == officer_id,
                                            models.User.role == models.Role.ELECTION_OFFICER).first()
    if not officer:
        raise HTTPException(404, "Officer not found")
    existing = db.query(models.ElectionOfficer).filter(
        models.ElectionOfficer.election_id == election_id, models.ElectionOfficer.officer_id == officer_id).first()
    if not existing:
        db.add(models.ElectionOfficer(election_id=election_id, officer_id=officer_id))
        db.commit()
        audit.log(db, "ELECTION_OFFICER_ASSIGNED", actor_id=user.id, actor_role=user.role.value,
                   target=election_id, details={"officer_id": officer_id})
    return _serialize(e, db)


@router.delete("/{election_id}/officers/{officer_id}")
def remove_officer(election_id: str, officer_id: str, db: Session = Depends(get_db),
                    user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN))):
    row = db.query(models.ElectionOfficer).filter(
        models.ElectionOfficer.election_id == election_id, models.ElectionOfficer.officer_id == officer_id).first()
    if row:
        db.delete(row)
        db.commit()
        audit.log(db, "ELECTION_OFFICER_REMOVED", actor_id=user.id, actor_role=user.role.value,
                   target=election_id, details={"officer_id": officer_id})
    e = db.query(models.Election).filter(models.Election.id == election_id).first()
    return _serialize(e, db)


@router.post("/{election_id}/status")
def update_status(election_id: str, req: schemas.ElectionStatusUpdate, db: Session = Depends(get_db),
                   user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN, models.Role.ELECTION_OFFICER))):
    e = db.query(models.Election).filter(models.Election.id == election_id).first()
    if not e:
        raise HTTPException(404, "Election not found")
    check_election_access(e, user, db)
    try:
        new_status = models.ElectionStatus(req.status)
    except ValueError:
        raise HTTPException(400, "Invalid status value")

    allowed = models.VALID_TRANSITIONS.get(e.status, set())
    if new_status not in allowed:
        raise HTTPException(400, f"Invalid transition {e.status.value} -> {new_status.value}")

    # Reopening a CLOSED election requires SUPER_ADMIN specifically.
    if e.status == models.ElectionStatus.CLOSED and new_status == models.ElectionStatus.OPEN:
        if user.role != models.Role.SUPER_ADMIN:
            raise HTTPException(403, "Only SUPER_ADMIN can reopen a closed election")

    old_status = e.status
    e.status = new_status
    db.commit()
    audit.log(db, "ELECTION_STATUS_CHANGED", actor_id=user.id, actor_role=user.role.value,
               target=election_id, details={"from": old_status.value, "to": new_status.value})
    ledger.add_block(db, "ELECTION_STATE_CHANGE",
                      {"election_id": election_id, "from": old_status.value, "to": new_status.value},
                      election_id=election_id, submitted_by=user.id)
    return _serialize(e, db)


def _serialize(e: models.Election, db: Session):
    officer_rows = db.query(models.ElectionOfficer).filter(models.ElectionOfficer.election_id == e.id).all()
    return {
        "id": e.id, "name": e.name, "description": e.description, "election_type": e.election_type,
        "election_level": e.election_level,
        "start_time": e.start_time, "end_time": e.end_time, "status": e.status.value,
        "eligible_constituency": e.eligible_constituency,
        "officer_ids": [row.officer_id for row in officer_rows],
    }
