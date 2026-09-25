"""
Common login for SUPER_ADMIN / ELECTION_OFFICER (single login page, role is
derived from the DB - never trusted from the client).
Flow: password -> (TOTP setup if first time | TOTP verify) -> access token.
Voters authenticate through /api/voting (voter_id + face + TOTP), not here.
"""
import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from ..database import get_db
from .. import models, schemas, security, totp as totp_service, audit
from ..config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
PRE_AUTH_TTL_MIN = 5


def _issue_pre_auth(user_id: str, purpose: str) -> str:
    payload = {"sub": user_id, "purpose": purpose,
               "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=PRE_AUTH_TTL_MIN)}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def _decode_pre_auth(token: str, expected_purpose: str, db: Session) -> models.User:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(401, "Invalid or expired pre-auth token")
    if payload.get("purpose") != expected_purpose:
        raise HTTPException(401, "Invalid token purpose")
    user = db.query(models.User).filter(models.User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(401, "User not found")
    return user


@router.post("/login")
def login(req: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == req.email).first()
    if not user or user.role == models.Role.VOTER:
        audit.log(db, "LOGIN_FAILED", target=req.email, success=False, details={"reason": "no_such_account"})
        raise HTTPException(401, "Invalid credentials")

    if user.locked_until and user.locked_until > datetime.datetime.utcnow():
        raise HTTPException(423, f"Account locked until {user.locked_until.isoformat()}")

    if not user.is_active:
        raise HTTPException(403, "Account deactivated")

    if not security.verify_password(req.password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.datetime.utcnow() + datetime.timedelta(minutes=LOCKOUT_MINUTES)
            audit.log(db, "ACCOUNT_LOCKED", actor_id=user.id, actor_role=user.role.value)
        db.commit()
        audit.log(db, "LOGIN_FAILED", actor_id=user.id, actor_role=user.role.value, success=False,
                   details={"reason": "bad_password"})
        raise HTTPException(401, "Invalid credentials")

    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

    if not user.totp_enrolled:
        token = _issue_pre_auth(user.id, "totp_setup_required")
        return {"requires_totp_setup": True, "requires_totp_verify": False, "pre_auth_token": token}
    else:
        token = _issue_pre_auth(user.id, "totp_verify_required")
        return {"requires_totp_setup": False, "requires_totp_verify": True, "pre_auth_token": token}


@router.post("/totp/setup/begin")
def totp_setup_begin(pre_auth_token: str, db: Session = Depends(get_db)):
    user = _decode_pre_auth(pre_auth_token, "totp_setup_required", db)
    secret = totp_service.generate_secret()
    uri = totp_service.provisioning_uri(secret, user.email)
    qr = totp_service.qr_code_data_uri(uri)
    # Stash secret temporarily encrypted on the user row; not "enrolled" until confirmed.
    user.totp_secret_encrypted = totp_service.encrypt_secret(secret)
    db.commit()
    return {"qr_code": qr, "manual_entry_uri": uri}


@router.post("/totp/setup/confirm")
def totp_setup_confirm(pre_auth_token: str, req: schemas.TOTPVerifyRequest, db: Session = Depends(get_db)):
    user = _decode_pre_auth(pre_auth_token, "totp_setup_required", db)
    if not user.totp_secret_encrypted:
        raise HTTPException(400, "Call /totp/setup/begin first")
    secret = totp_service.decrypt_secret(user.totp_secret_encrypted)
    if not totp_service.verify_code(secret, req.code):
        audit.log(db, "TOTP_SETUP_FAILED", actor_id=user.id, actor_role=user.role.value, success=False)
        raise HTTPException(401, "Invalid TOTP code")
    user.totp_enrolled = True
    db.commit()
    audit.log(db, "TOTP_ENROLLED", actor_id=user.id, actor_role=user.role.value)
    access = security.create_access_token(user.id, user.role.value)
    return schemas.TokenResponse(access_token=access, role=user.role.value, totp_enrolled=True)


@router.post("/totp/verify")
def totp_verify(pre_auth_token: str, req: schemas.TOTPVerifyRequest, db: Session = Depends(get_db)):
    user = _decode_pre_auth(pre_auth_token, "totp_verify_required", db)
    secret = totp_service.decrypt_secret(user.totp_secret_encrypted)
    if not totp_service.verify_code(secret, req.code):
        audit.log(db, "TOTP_VERIFY_FAILED", actor_id=user.id, actor_role=user.role.value, success=False)
        raise HTTPException(401, "Invalid TOTP code")
    audit.log(db, "LOGIN_SUCCESS", actor_id=user.id, actor_role=user.role.value)
    access = security.create_access_token(user.id, user.role.value)
    return schemas.TokenResponse(access_token=access, role=user.role.value, totp_enrolled=True)
