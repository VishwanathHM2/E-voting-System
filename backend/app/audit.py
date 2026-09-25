import json
from sqlalchemy.orm import Session
from . import models


def log(db: Session, action: str, actor_id: str = None, actor_role: str = None,
        target: str = None, details: dict = None, success: bool = True):
    entry = models.AuditLog(
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        target=target,
        details=json.dumps(details, default=str) if details else None,
        success=success,
    )
    db.add(entry)
    db.commit()
