import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from .. import models, schemas, audit
from ..deps import require_roles, check_election_access

router = APIRouter(prefix="/api/candidates", tags=["candidates"])

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads", "symbols")
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg"}
MAX_UPLOAD_BYTES = 3 * 1024 * 1024  # 3 MB


def _save_upload(file: UploadFile, prefix: str) -> str:
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported image type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    content = file.file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "Image too large (max 3 MB)")
    filename = f"{prefix}_{uuid.uuid4().hex[:8]}{ext}"
    with open(os.path.join(UPLOAD_DIR, filename), "wb") as f:
        f.write(content)
    return filename


def _remove_old(filename: str | None):
    if filename:
        old_path = os.path.join(UPLOAD_DIR, os.path.basename(filename))
        if os.path.exists(old_path):
            os.remove(old_path)


@router.post("")
def create_candidate(req: schemas.CandidateCreate, db: Session = Depends(get_db),
                      user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN, models.Role.ELECTION_OFFICER))):
    election = db.query(models.Election).filter(models.Election.id == req.election_id).first()
    if not election:
        raise HTTPException(404, "Election not found")
    check_election_access(election, user, db)
    if election.status not in (models.ElectionStatus.DRAFT, models.ElectionStatus.SCHEDULED):
        raise HTTPException(400, "Cannot modify candidates after voting has begun")

    candidate_type = (req.candidate_type or "INDIVIDUAL").upper()
    if candidate_type not in ("INDIVIDUAL", "PARTY"):
        raise HTTPException(400, "candidate_type must be INDIVIDUAL or PARTY")

    # Auto-assign the next sequential candidate number within this election.
    max_number = db.query(func.max(models.Candidate.candidate_number)).filter(
        models.Candidate.election_id == req.election_id).scalar()
    next_number = (max_number or 0) + 1

    c = models.Candidate(election_id=req.election_id, name=req.name, candidate_type=candidate_type,
                          candidate_number=next_number, party=req.party, symbol=req.symbol,
                          description=req.description)
    db.add(c)
    db.commit()
    db.refresh(c)
    audit.log(db, "CANDIDATE_CREATED", actor_id=user.id, actor_role=user.role.value, target=c.id)
    return _serialize(c)


@router.post("/{candidate_id}/photo")
def upload_photo(candidate_id: str, file: UploadFile = File(...), db: Session = Depends(get_db),
                  user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN, models.Role.ELECTION_OFFICER))):
    """Candidate's own photo (relevant for INDIVIDUAL candidates especially)."""
    c = db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()
    if not c:
        raise HTTPException(404, "Candidate not found")
    election = db.query(models.Election).filter(models.Election.id == c.election_id).first()
    check_election_access(election, user, db)
    if election.status not in (models.ElectionStatus.DRAFT, models.ElectionStatus.SCHEDULED):
        raise HTTPException(400, "Cannot modify candidates after voting has begun")

    _remove_old(c.photo_path)
    c.photo_path = _save_upload(file, f"{candidate_id}_photo")
    db.commit()
    audit.log(db, "CANDIDATE_PHOTO_UPLOADED", actor_id=user.id, actor_role=user.role.value, target=candidate_id)
    return _serialize(c)


@router.post("/{candidate_id}/party-symbol")
def upload_party_symbol(candidate_id: str, file: UploadFile = File(...), db: Session = Depends(get_db),
                         user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN, models.Role.ELECTION_OFFICER))):
    """Separate upload for the party's symbol - only meaningful when candidate_type == PARTY."""
    c = db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()
    if not c:
        raise HTTPException(404, "Candidate not found")
    election = db.query(models.Election).filter(models.Election.id == c.election_id).first()
    check_election_access(election, user, db)
    if election.status not in (models.ElectionStatus.DRAFT, models.ElectionStatus.SCHEDULED):
        raise HTTPException(400, "Cannot modify candidates after voting has begun")
    if c.candidate_type != "PARTY":
        raise HTTPException(400, "Party symbol upload is only for candidates of type PARTY")

    _remove_old(c.party_symbol_path)
    c.party_symbol_path = _save_upload(file, f"{candidate_id}_party")
    db.commit()
    audit.log(db, "CANDIDATE_PARTY_SYMBOL_UPLOADED", actor_id=user.id, actor_role=user.role.value, target=candidate_id)
    return _serialize(c)


@router.get("/election/{election_id}")
def list_candidates(election_id: str, db: Session = Depends(get_db)):
    cands = db.query(models.Candidate).filter(models.Candidate.election_id == election_id,
                                                models.Candidate.is_active == True
                                                ).order_by(models.Candidate.candidate_number.asc()).all()
    return [_serialize(c) for c in cands]


@router.delete("/{candidate_id}")
def deactivate_candidate(candidate_id: str, db: Session = Depends(get_db),
                          user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN))):
    c = db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()
    if not c:
        raise HTTPException(404, "Candidate not found")
    election = db.query(models.Election).filter(models.Election.id == c.election_id).first()
    if election.status not in (models.ElectionStatus.DRAFT, models.ElectionStatus.SCHEDULED):
        raise HTTPException(400, "Cannot modify candidates after voting has begun")
    c.is_active = False
    db.commit()
    audit.log(db, "CANDIDATE_DEACTIVATED", actor_id=user.id, actor_role=user.role.value, target=c.id)
    return {"id": c.id, "is_active": False}


def _serialize(c: models.Candidate):
    return {
        "id": c.id, "election_id": c.election_id, "candidate_number": c.candidate_number,
        "name": c.name, "candidate_type": c.candidate_type, "party": c.party,
        "symbol": c.symbol, "description": c.description,
        "symbol_url": f"/uploads/symbols/{c.photo_path}" if c.photo_path else None,
        "party_symbol_url": f"/uploads/symbols/{c.party_symbol_path}" if c.party_symbol_path else None,
    }
