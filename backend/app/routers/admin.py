"""Super Admin: officer management, dashboard stats."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas, security, audit
from ..deps import require_roles

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/officers")
def create_officer(req: schemas.OfficerCreate, db: Session = Depends(get_db),
                    user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN))):
    if db.query(models.User).filter(models.User.email == req.email).first():
        raise HTTPException(400, "Email already in use")
    officer = models.User(email=req.email, name=req.name,
                           password_hash=security.hash_password(req.password),
                           role=models.Role.ELECTION_OFFICER)
    db.add(officer)
    db.commit()
    db.refresh(officer)
    audit.log(db, "OFFICER_CREATED", actor_id=user.id, actor_role=user.role.value, target=officer.id)
    return {"id": officer.id, "email": officer.email, "name": officer.name}


@router.get("/officers")
def list_officers(db: Session = Depends(get_db),
                   user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN))):
    officers = db.query(models.User).filter(models.User.role == models.Role.ELECTION_OFFICER).all()
    return [{"id": o.id, "email": o.email, "name": o.name, "is_active": o.is_active} for o in officers]


@router.post("/officers/{officer_id}/toggle-active")
def toggle_officer(officer_id: str, db: Session = Depends(get_db),
                    user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN))):
    officer = db.query(models.User).filter(models.User.id == officer_id,
                                            models.User.role == models.Role.ELECTION_OFFICER).first()
    if not officer:
        raise HTTPException(404, "Officer not found")
    officer.is_active = not officer.is_active
    db.commit()
    audit.log(db, "OFFICER_TOGGLED", actor_id=user.id, actor_role=user.role.value,
               target=officer.id, details={"is_active": officer.is_active})
    return {"id": officer.id, "is_active": officer.is_active}


@router.delete("/officers/{officer_id}")
def delete_officer(officer_id: str, db: Session = Depends(get_db),
                    user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN))):
    officer = db.query(models.User).filter(models.User.id == officer_id,
                                            models.User.role == models.Role.ELECTION_OFFICER).first()
    if not officer:
        raise HTTPException(404, "Officer not found")
    db.query(models.ElectionOfficer).filter(models.ElectionOfficer.officer_id == officer_id).delete()
    db.delete(officer)
    db.commit()
    audit.log(db, "OFFICER_DELETED", actor_id=user.id, actor_role=user.role.value, target=officer_id,
               details={"name": officer.name, "email": officer.email})
    return {"message": "Officer deleted"}


@router.get("/officers/{officer_id}")
def get_officer(officer_id: str, db: Session = Depends(get_db),
                 user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN))):
    officer = db.query(models.User).filter(models.User.id == officer_id,
                                            models.User.role == models.Role.ELECTION_OFFICER).first()
    if not officer:
        raise HTTPException(404, "Officer not found")

    assigned = db.query(models.ElectionOfficer).filter(models.ElectionOfficer.officer_id == officer_id).all()
    election_ids = [row.election_id for row in assigned]
    elections = db.query(models.Election).filter(models.Election.id.in_(election_ids)).all() if election_ids else []

    activity = db.query(models.AuditLog).filter(models.AuditLog.actor_id == officer_id
                                                  ).order_by(models.AuditLog.timestamp.desc()).limit(50).all()

    return {
        "id": officer.id, "name": officer.name, "email": officer.email, "is_active": officer.is_active,
        "elections": [{"id": e.id, "name": e.name, "status": e.status.value} for e in elections],
        "activity": [{"action": a.action, "target": a.target, "success": a.success,
                       "timestamp": a.timestamp.isoformat()} for a in activity],
    }


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db),
              user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN, models.Role.ELECTION_OFFICER))):
    total_elections = db.query(models.Election).count()
    active = db.query(models.Election).filter(models.Election.status == models.ElectionStatus.OPEN).count()
    completed = db.query(models.Election).filter(models.Election.status == models.ElectionStatus.PUBLISHED).count()
    eligible_voters = db.query(models.Voter).filter(models.Voter.is_eligible == True).count()
    enrolled_voters = db.query(models.Voter).filter(models.Voter.is_enrolled == True).count()
    votes_cast = db.query(models.Participation).count()
    auth_failures = db.query(models.AuditLog).filter(
        models.AuditLog.action.in_(["LOGIN_FAILED", "TOTP_VERIFY_FAILED", "FACE_VERIFY_FAILED"]),
        models.AuditLog.success == False).count()
    recent = db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc()).limit(20).all()
    return {
        "total_elections": total_elections,
        "active_elections": active,
        "completed_elections": completed,
        "eligible_voters": eligible_voters,
        "enrolled_voters": enrolled_voters,
        "votes_cast": votes_cast,
        "turnout_pct": round((votes_cast / eligible_voters * 100), 2) if eligible_voters else 0,
        "auth_failures": auth_failures,
        "recent_activity": [
            {"action": r.action, "actor_role": r.actor_role, "success": r.success,
             "timestamp": r.timestamp.isoformat()} for r in recent
        ],
    }
