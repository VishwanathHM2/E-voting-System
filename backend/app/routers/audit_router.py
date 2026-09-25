from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, ledger
from ..deps import require_roles

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/logs")
def get_logs(page: int = 1, page_size: int = 50, db: Session = Depends(get_db),
             user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN))):
    q = db.query(models.AuditLog).order_by(models.AuditLog.timestamp.desc())
    total = q.count()
    logs = q.offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "logs": [{
        "id": l.id, "action": l.action, "actor_role": l.actor_role, "target": l.target,
        "success": l.success, "timestamp": l.timestamp.isoformat(), "details": l.details,
    } for l in logs]}


@router.get("/ledger")
def get_ledger(db: Session = Depends(get_db), user: models.User = Depends(
        require_roles(models.Role.SUPER_ADMIN, models.Role.ELECTION_OFFICER))):
    blocks = db.query(models.LedgerBlock).order_by(models.LedgerBlock.id.asc()).all()
    return [{"id": b.id, "tx_id": b.tx_id, "event_type": b.event_type, "election_id": b.election_id,
             "prev_hash": b.prev_hash, "block_hash": b.block_hash, "timestamp": b.timestamp.isoformat()}
            for b in blocks]


@router.get("/ledger/verify")
def verify_ledger_global(db: Session = Depends(get_db), user: models.User = Depends(
        require_roles(models.Role.SUPER_ADMIN, models.Role.ELECTION_OFFICER))):
    return ledger.verify_chain(db)
