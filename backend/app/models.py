import enum
import uuid
import datetime
from sqlalchemy import (Column, String, Boolean, DateTime, ForeignKey, Integer,
                         Enum as SAEnum, LargeBinary, Text, UniqueConstraint, Float)
from sqlalchemy.orm import relationship
from .database import Base


def gen_id():
    return str(uuid.uuid4())


def now():
    return datetime.datetime.utcnow()


class Role(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ELECTION_OFFICER = "ELECTION_OFFICER"
    VOTER = "VOTER"


class ElectionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    COUNTING = "COUNTING"
    VERIFICATION = "VERIFICATION"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"


# Valid forward transitions for election lifecycle
VALID_TRANSITIONS = {
    ElectionStatus.DRAFT: {ElectionStatus.SCHEDULED},
    ElectionStatus.SCHEDULED: {ElectionStatus.OPEN},
    ElectionStatus.OPEN: {ElectionStatus.CLOSED},
    ElectionStatus.CLOSED: {ElectionStatus.COUNTING, ElectionStatus.OPEN},  # OPEN = admin reopen (audited)
    ElectionStatus.COUNTING: {ElectionStatus.VERIFICATION},
    ElectionStatus.VERIFICATION: {ElectionStatus.APPROVED},
    ElectionStatus.APPROVED: {ElectionStatus.PUBLISHED},
    ElectionStatus.PUBLISHED: set(),
}


class SystemMeta(Base):
    __tablename__ = "system_meta"
    key = Column(String, primary_key=True)
    value = Column(String)


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_id)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(SAEnum(Role), nullable=False)
    is_active = Column(Boolean, default=True)
    totp_secret_encrypted = Column(String, nullable=True)
    totp_enrolled = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=now)

    voter_profile = relationship("Voter", back_populates="user", uselist=False)


class Voter(Base):
    __tablename__ = "voters"
    id = Column(String, primary_key=True, default=gen_id)
    voter_id = Column(String, unique=True, index=True, nullable=False)  # external voter ID (registry)
    name = Column(String, nullable=False)
    date_of_birth = Column(String, nullable=True)
    email = Column(String, nullable=True)
    mobile = Column(String, nullable=True)
    address = Column(String, nullable=True)
    constituency = Column(String, nullable=True)
    is_eligible = Column(Boolean, default=True)
    is_enrolled = Column(Boolean, default=False)
    face_enrolled = Column(Boolean, default=False)
    face_embedding = Column(Text, nullable=True)  # JSON list, stored only after enrollment
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=now)

    user = relationship("User", back_populates="voter_profile")


class Election(Base):
    __tablename__ = "elections"
    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    election_type = Column(String, nullable=True)
    election_level = Column(String, nullable=True)  # Lok Sabha / Rajya Sabha / Municipal / Panchayat / Other
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(SAEnum(ElectionStatus), default=ElectionStatus.DRAFT)
    eligible_constituency = Column(String, nullable=True)  # None = all
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=now)


class ElectionOfficer(Base):
    """Many-to-many: an election can have multiple assigned officers, and an
    officer can be assigned to multiple elections."""
    __tablename__ = "election_officers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    election_id = Column(String, ForeignKey("elections.id"), nullable=False)
    officer_id = Column(String, ForeignKey("users.id"), nullable=False)
    __table_args__ = (UniqueConstraint("election_id", "officer_id", name="uq_election_officer"),)


class Candidate(Base):
    __tablename__ = "candidates"
    id = Column(String, primary_key=True, default=gen_id)
    election_id = Column(String, ForeignKey("elections.id"), nullable=False)
    candidate_number = Column(Integer, nullable=True)  # sequential per election, shown to voters + candidate
    name = Column(String, nullable=False)
    candidate_type = Column(String, nullable=False, default="INDIVIDUAL")  # INDIVIDUAL or PARTY
    party = Column(String, nullable=True)
    symbol = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    photo_path = Column(String, nullable=True)        # candidate's own photo
    party_symbol_path = Column(String, nullable=True)  # separate upload, only relevant when candidate_type == PARTY
    is_active = Column(Boolean, default=True)


class Participation(Base):
    """Tracks that a voter voted in an election. Does NOT link to candidate."""
    __tablename__ = "participation"
    id = Column(String, primary_key=True, default=gen_id)
    voter_id = Column(String, ForeignKey("voters.id"), nullable=False)
    election_id = Column(String, ForeignKey("elections.id"), nullable=False)
    voted_at = Column(DateTime, default=now)
    __table_args__ = (UniqueConstraint("voter_id", "election_id", name="uq_voter_election"),)


class Ballot(Base):
    """Encrypted ballot - not linked to voter identity."""
    __tablename__ = "ballots"
    id = Column(String, primary_key=True, default=gen_id)
    election_id = Column(String, ForeignKey("elections.id"), nullable=False)
    ciphertext = Column(Text, nullable=False)   # base64 AES-GCM ciphertext
    nonce = Column(String, nullable=False)      # base64
    tag = Column(String, nullable=False)        # base64
    integrity_hash = Column(String, nullable=False)  # sha256 of ciphertext+nonce+tag
    ledger_tx_id = Column(String, nullable=True)
    decrypted_candidate_id = Column(String, nullable=True)  # filled in only during official COUNTING
    created_at = Column(DateTime, default=now)


class LedgerBlock(Base):
    """Permissioned, tamper-evident hash-chain ledger (append-only)."""
    __tablename__ = "ledger_blocks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tx_id = Column(String, unique=True, default=gen_id)
    election_id = Column(String, nullable=True)
    event_type = Column(String, nullable=False)  # e.g. BALLOT_CAST, ELECTION_STATE_CHANGE
    payload = Column(Text, nullable=False)  # JSON string of non-sensitive metadata
    prev_hash = Column(String, nullable=False)
    block_hash = Column(String, nullable=False)
    submitted_by = Column(String, nullable=True)  # authorized service/user id
    timestamp = Column(DateTime, default=now)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True, default=gen_id)
    actor_id = Column(String, nullable=True)
    actor_role = Column(String, nullable=True)
    action = Column(String, nullable=False)
    target = Column(String, nullable=True)
    details = Column(Text, nullable=True)
    success = Column(Boolean, default=True)
    timestamp = Column(DateTime, default=now)
