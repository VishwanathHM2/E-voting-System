import datetime
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import jwt, JWTError

from .database import get_db
from . import models, security
from .config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    payload = security.decode_access_token(token)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.query(models.User).filter(models.User.id == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user  # role is ALWAYS re-derived from DB, never trusted from frontend


def require_roles(*roles):
    def checker(user: models.User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user
    return checker


# ---- short-lived, single-purpose "face session" token issued after a
# passed face-match step during election-day voting. Proves the live face
# check succeeded for this exact voter_id+election_id, without which the
# ballot endpoint refuses to proceed. ----
FACE_TOKEN_TTL_SECONDS = 120


def issue_face_session_token(voter_id: str, election_id: str) -> str:
    payload = {
        "purpose": "face_verified",
        "voter_id": voter_id,
        "election_id": election_id,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(seconds=FACE_TOKEN_TTL_SECONDS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_face_session_token(token: str, voter_id: str, election_id: str) -> bool:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return False
    return (payload.get("purpose") == "face_verified"
            and payload.get("voter_id") == voter_id
            and payload.get("election_id") == election_id)


def check_election_access(election, user, db: Session) -> None:
    """
    Officer-election assignment enforcement: an ELECTION_OFFICER may only
    manage elections they've been explicitly assigned to (via the
    election_officers many-to-many table - an election can have several
    assigned officers). SUPER_ADMIN can manage any election. Elections with
    no assigned officers are SUPER_ADMIN-only until one is assigned.
    """
    if user.role == models.Role.SUPER_ADMIN:
        return
    if user.role == models.Role.ELECTION_OFFICER:
        assigned = db.query(models.ElectionOfficer).filter(
            models.ElectionOfficer.election_id == election.id,
            models.ElectionOfficer.officer_id == user.id,
        ).first()
        if not assigned:
            from fastapi import HTTPException
            raise HTTPException(403, "You are not an assigned officer for this election")
        return
