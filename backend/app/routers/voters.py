"""Authorized voter registry: CSV/Excel upload, search, eligibility management."""
import io
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..database import get_db
from .. import models, schemas, audit
from ..deps import require_roles

router = APIRouter(prefix="/api/voters", tags=["voters"])

REQUIRED_COLUMNS = {"voter_id", "name"}
OPTIONAL_COLUMNS = {"date_of_birth", "email", "mobile", "address", "constituency"}


@router.post("/upload")
def upload_registry(file: UploadFile = File(...), db: Session = Depends(get_db),
                     user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN, models.Role.ELECTION_OFFICER))):
    content = file.file.read()
    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content), dtype=str)
        else:
            df = pd.read_excel(io.BytesIO(content), dtype=str)
    except Exception as e:
        raise HTTPException(400, f"Could not parse file: {e}")

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise HTTPException(400, f"Missing required columns: {missing}")

    created, skipped, errors = 0, 0, []
    seen_ids_in_file = set()

    for idx, row in df.iterrows():
        vid = str(row.get("voter_id", "")).strip()
        name = str(row.get("name", "")).strip()
        if not vid or not name or vid.lower() == "nan" or name.lower() == "nan":
            errors.append({"row": int(idx) + 2, "reason": "missing voter_id or name"})
            continue
        if vid in seen_ids_in_file:
            errors.append({"row": int(idx) + 2, "reason": f"duplicate voter_id in file: {vid}"})
            continue
        seen_ids_in_file.add(vid)

        email = str(row.get("email", "")).strip() if pd.notna(row.get("email")) else None
        if email and ("@" not in email or "." not in email.split("@")[-1]):
            errors.append({"row": int(idx) + 2, "reason": f"invalid email: {email}"})
            continue

        existing = db.query(models.Voter).filter(models.Voter.voter_id == vid).first()
        if existing:
            skipped += 1
            continue

        voter = models.Voter(
            voter_id=vid, name=name,
            date_of_birth=_clean(row.get("date_of_birth")),
            email=email,
            mobile=_clean(row.get("mobile")),
            address=_clean(row.get("address")),
            constituency=_clean(row.get("constituency")),
        )
        try:
            db.add(voter)
            db.flush()
            created += 1
        except IntegrityError:
            db.rollback()
            errors.append({"row": int(idx) + 2, "reason": "database constraint violation"})

    db.commit()
    audit.log(db, "VOTER_REGISTRY_UPLOAD", actor_id=user.id, actor_role=user.role.value,
               details={"created": created, "skipped": skipped, "errors": len(errors)})
    return {"created": created, "skipped_existing": skipped, "errors": errors}


def _clean(v):
    if v is None or (isinstance(v, float)):
        return None
    v = str(v).strip()
    return v if v and v.lower() != "nan" else None


@router.get("")
def list_voters(q: str = "", page: int = 1, page_size: int = 25, db: Session = Depends(get_db),
                 user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN, models.Role.ELECTION_OFFICER))):
    query = db.query(models.Voter)
    if q:
        like = f"%{q}%"
        query = query.filter((models.Voter.voter_id.ilike(like)) | (models.Voter.name.ilike(like)))
    total = query.count()
    voters = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "voters": [{
            "id": v.id, "voter_id": v.voter_id, "name": v.name, "constituency": v.constituency,
            "is_eligible": v.is_eligible, "is_enrolled": v.is_enrolled, "face_enrolled": v.face_enrolled,
        } for v in voters],
    }


@router.post("/{voter_id}/eligibility")
def set_eligibility(voter_id: str, eligible: bool, db: Session = Depends(get_db),
                     user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN, models.Role.ELECTION_OFFICER))):
    voter = db.query(models.Voter).filter(models.Voter.voter_id == voter_id).first()
    if not voter:
        raise HTTPException(404, "Voter not found")
    voter.is_eligible = eligible
    db.commit()
    audit.log(db, "VOTER_ELIGIBILITY_CHANGED", actor_id=user.id, actor_role=user.role.value,
               target=voter_id, details={"eligible": eligible})
    return {"voter_id": voter_id, "is_eligible": eligible}


@router.post("/{voter_id}/reset-totp")
def reset_totp(voter_id: str, db: Session = Depends(get_db),
                user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN, models.Role.ELECTION_OFFICER))):
    """
    TOTP recovery: if a voter loses their authenticator, an authorized admin
    or officer can invalidate the old secret and force fresh TOTP setup on
    the voter's next enrollment visit. Requires the voter to physically
    re-verify by going through /enrollment/totp/begin again (which itself
    requires a valid enroll_token, so they still need their voter_id and
    account password - this doesn't hand out unauthenticated access).
    """
    voter = db.query(models.Voter).filter(models.Voter.voter_id == voter_id).first()
    if not voter:
        raise HTTPException(404, "Voter not found")
    if not voter.user_id:
        raise HTTPException(400, "Voter has not started enrollment yet")
    voter_user = db.query(models.User).filter(models.User.id == voter.user_id).first()
    if not voter_user:
        raise HTTPException(404, "Linked voter account not found")

    voter_user.totp_secret_encrypted = None
    voter_user.totp_enrolled = False
    db.commit()

    audit.log(db, "VOTER_TOTP_RESET", actor_id=user.id, actor_role=user.role.value, target=voter_id)
    return {"voter_id": voter_id, "message": "TOTP has been reset. Voter must re-enroll TOTP before voting."}


@router.delete("/{voter_id}")
def delete_voter(voter_id: str, db: Session = Depends(get_db),
                  user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN, models.Role.ELECTION_OFFICER))):
    """Removes a voter from the registry along with their linked account.
    Blocked if the voter has already voted in any election - deleting a
    voter who has cast a ballot would break the audit trail linking
    participation records to a real registry entry, so that state must be
    handled by marking them ineligible instead, not deletion."""
    voter = db.query(models.Voter).filter(models.Voter.voter_id == voter_id).first()
    if not voter:
        raise HTTPException(404, "Voter not found")

    has_voted = db.query(models.Participation).filter(models.Participation.voter_id == voter.id).first()
    if has_voted:
        raise HTTPException(400, "Cannot delete a voter who has already voted in an election. "
                                  "Set them as ineligible instead if needed.")

    if voter.user_id:
        linked_user = db.query(models.User).filter(models.User.id == voter.user_id).first()
        if linked_user:
            db.delete(linked_user)

    db.delete(voter)
    db.commit()
    audit.log(db, "VOTER_DELETED", actor_id=user.id, actor_role=user.role.value, target=voter_id)
    return {"message": "Voter deleted"}
