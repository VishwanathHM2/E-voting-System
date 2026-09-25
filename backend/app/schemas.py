import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr


class SetupRequest(BaseModel):
    org_name: str
    admin_name: str
    email: EmailStr
    password: str
    confirm_password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    totp_enrolled: bool


class TOTPVerifyRequest(BaseModel):
    code: str


class OfficerCreate(BaseModel):
    name: str
    email: EmailStr
    password: str


class VoterCreate(BaseModel):
    voter_id: str
    name: str
    date_of_birth: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    address: Optional[str] = None
    constituency: Optional[str] = None


class ElectionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    election_type: Optional[str] = None
    election_level: Optional[str] = None  # Lok Sabha / Rajya Sabha / Municipal / Panchayat / Other
    start_time: datetime.datetime
    end_time: datetime.datetime
    eligible_constituency: Optional[str] = None
    officer_ids: Optional[List[str]] = []


class ElectionStatusUpdate(BaseModel):
    status: str


class CandidateCreate(BaseModel):
    election_id: str
    name: str
    candidate_type: Optional[str] = "INDIVIDUAL"  # INDIVIDUAL or PARTY
    party: Optional[str] = None
    symbol: Optional[str] = None
    description: Optional[str] = None


class EnrollmentStart(BaseModel):
    voter_id: str


class FaceEnrollRequest(BaseModel):
    voter_id: str
    images_b64: List[str]  # 5-10 frames


class VoterLoginRequest(BaseModel):
    voter_id: str
    password: str


class FaceVerifyRequest(BaseModel):
    voter_id: str
    image_b64: str


class CastVoteRequest(BaseModel):
    voter_id: str
    election_id: str
    candidate_id: str
    totp_code: str
    face_session_token: str  # short-lived token proving face+liveness step passed
