"""
One-time voter enrollment: voter must already exist in the registry.
Voter ID -> registry check -> set password (creates linked User) -> TOTP setup
-> TOTP verify -> face capture (multi-frame) -> duplicate-face check -> done.
"""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from pydantic import BaseModel
import datetime

from ..database import get_db
from .. import models, schemas, security, totp as totp_service, face_service, audit
from ..config import settings

router = APIRouter(prefix="/api/enrollment", tags=["enrollment"])


def _issue_enroll_token(voter_id: str, stage: str) -> str:
    payload = {"voter_id": voter_id, "stage": stage,
               "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=15)}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _decode_enroll_token(token: str, expected_stage: str) -> str:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(401, "Invalid or expired enrollment session")
    if payload.get("stage") != expected_stage:
        raise HTTPException(401, "Wrong enrollment stage")
    return payload["voter_id"]


class StartReq(BaseModel):
    voter_id: str


class SetPasswordReq(BaseModel):
    enroll_token: str
    password: str
    confirm_password: str


@router.post("/start")
def start(req: schemas.EnrollmentStart, db: Session = Depends(get_db)):
    voter = db.query(models.Voter).filter(models.Voter.voter_id == req.voter_id).first()
    if not voter:
        raise HTTPException(404, "Voter ID not found in authorized registry")
    if not voter.is_eligible:
        raise HTTPException(403, "Voter is not eligible")
    if voter.is_enrolled:
        raise HTTPException(400, "Voter is already enrolled")
    token = _issue_enroll_token(voter.voter_id, "set_password")
    return {"enroll_token": token, "voter_name": voter.name}


class TotpRecoveryStart(BaseModel):
    voter_id: str
    password: str


@router.post("/totp-recovery/start")
def totp_recovery_start(req: TotpRecoveryStart, db: Session = Depends(get_db)):
    """
    Re-entry point for a voter whose TOTP was reset by an admin/officer
    (see /api/voters/{voter_id}/reset-totp). Requires the voter's existing
    account password to prove it's really them - does not touch their
    password or face enrollment, only re-issues a fresh TOTP secret.
    """
    voter = db.query(models.Voter).filter(models.Voter.voter_id == req.voter_id).first()
    if not voter or not voter.user_id:
        raise HTTPException(404, "Voter not found or not enrolled yet")
    voter_user = db.query(models.User).filter(models.User.id == voter.user_id).first()
    if not voter_user or not security.verify_password(req.password, voter_user.password_hash):
        audit.log(db, "TOTP_RECOVERY_FAILED", target=req.voter_id, success=False)
        raise HTTPException(401, "Invalid Voter ID or password")
    if voter_user.totp_enrolled:
        raise HTTPException(400, "TOTP is already enrolled. Ask an admin to reset it first if you lost access.")

    audit.log(db, "TOTP_RECOVERY_STARTED", target=req.voter_id)
    token = _issue_enroll_token(req.voter_id, "totp_setup")
    return {"enroll_token": token}


@router.post("/set-password")
def set_password(req: SetPasswordReq, db: Session = Depends(get_db)):
    voter_id = _decode_enroll_token(req.enroll_token, "set_password")
    if req.password != req.confirm_password:
        raise HTTPException(400, "Passwords do not match")
    if len(req.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    voter = db.query(models.Voter).filter(models.Voter.voter_id == voter_id).first()
    if not voter or voter.is_enrolled:
        raise HTTPException(400, "Invalid enrollment state")

    if not voter.user_id:
        u = models.User(email=voter.email or f"{voter.voter_id}@voter.local", name=voter.name,
                         password_hash=security.hash_password(req.password), role=models.Role.VOTER)
        db.add(u)
        db.flush()
        voter.user_id = u.id
    else:
        u = db.query(models.User).filter(models.User.id == voter.user_id).first()
        u.password_hash = security.hash_password(req.password)
    db.commit()

    token = _issue_enroll_token(voter_id, "totp_setup")
    return {"enroll_token": token}


@router.post("/totp/begin")
def totp_begin(enroll_token: str, db: Session = Depends(get_db)):
    voter_id = _decode_enroll_token(enroll_token, "totp_setup")
    voter = db.query(models.Voter).filter(models.Voter.voter_id == voter_id).first()
    user = db.query(models.User).filter(models.User.id == voter.user_id).first()
    secret = totp_service.generate_secret()
    uri = totp_service.provisioning_uri(secret, f"voter:{voter_id}")
    qr = totp_service.qr_code_data_uri(uri)
    user.totp_secret_encrypted = totp_service.encrypt_secret(secret)
    db.commit()
    return {"qr_code": qr, "manual_entry_uri": uri}


@router.post("/totp/confirm")
def totp_confirm(enroll_token: str, req: schemas.TOTPVerifyRequest, db: Session = Depends(get_db)):
    voter_id = _decode_enroll_token(enroll_token, "totp_setup")
    voter = db.query(models.Voter).filter(models.Voter.voter_id == voter_id).first()
    user = db.query(models.User).filter(models.User.id == voter.user_id).first()
    secret = totp_service.decrypt_secret(user.totp_secret_encrypted)
    if not totp_service.verify_code(secret, req.code):
        audit.log(db, "ENROLL_TOTP_FAILED", target=voter_id, success=False)
        raise HTTPException(401, "Invalid TOTP code")
    user.totp_enrolled = True
    db.commit()
    audit.log(db, "ENROLL_TOTP_CONFIRMED", target=voter_id)
    token = _issue_enroll_token(voter_id, "face_enroll")
    return {"enroll_token": token}


@router.post("/face")
def face_enroll(enroll_token: str, req: schemas.FaceEnrollRequest, db: Session = Depends(get_db)):
    voter_id = _decode_enroll_token(enroll_token, "face_enroll")
    if req.voter_id != voter_id:
        raise HTTPException(400, "voter_id mismatch")
    if len(req.images_b64) < 3:
        raise HTTPException(400, "At least 3 frames required for reliable enrollment")

    voter = db.query(models.Voter).filter(models.Voter.voter_id == voter_id).first()
    if voter.face_enrolled:
        raise HTTPException(400, "Face already enrolled for this voter")

    embeddings = []
    for img in req.images_b64:
        result = face_service.extract_embedding(img)
        if not result["ok"]:
            audit.log(db, "FACE_ENROLL_FRAME_REJECTED", target=voter_id,
                       details={"reason": result["reason"]}, success=False)
            continue
        embeddings.append(result["embedding"])

    if len(embeddings) < 3:
        raise HTTPException(400, "Not enough usable frames (need clear, single-face frames)")

    avg_embedding = face_service.average_embeddings(embeddings)

    # Duplicate-face check against all other enrolled voters
    existing = db.query(models.Voter.voter_id, models.Voter.face_embedding).filter(
        models.Voter.face_enrolled == True, models.Voter.voter_id != voter_id).all()
    dup = face_service.find_duplicate(avg_embedding, [(v, e) for v, e in existing if e])
    if dup["duplicate"]:
        audit.log(db, "FACE_ENROLL_DUPLICATE_FLAGGED", target=voter_id,
                   details=dup, success=False)
        raise HTTPException(409, f"Enrollment flagged: face closely matches another enrolled voter "
                                  f"({dup['matched_voter_id']}). Requires administrative review.")

    voter.face_embedding = json.dumps(avg_embedding)
    voter.face_enrolled = True
    voter.is_enrolled = True
    db.commit()
    audit.log(db, "VOTER_ENROLLMENT_COMPLETED", target=voter_id)
    return {"message": "Enrollment completed", "voter_id": voter_id}
