from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas, security, audit

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.get("/status")
def setup_status(db: Session = Depends(get_db)):
    meta = db.query(models.SystemMeta).filter(models.SystemMeta.key == "initialized").first()
    return {"initialized": bool(meta and meta.value == "true")}


@router.post("/initialize")
def initialize(req: schemas.SetupRequest, db: Session = Depends(get_db)):
    meta = db.query(models.SystemMeta).filter(models.SystemMeta.key == "initialized").first()
    if meta and meta.value == "true":
        # Permanently blocked once initialized - no public re-init endpoint.
        raise HTTPException(400, "System already initialized. Initial setup is permanently disabled.")

    if req.password != req.confirm_password:
        raise HTTPException(400, "Passwords do not match")
    if len(req.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    existing = db.query(models.User).filter(models.User.email == req.email).first()
    if existing:
        raise HTTPException(400, "Email already in use")

    admin = models.User(
        email=req.email,
        name=req.admin_name,
        password_hash=security.hash_password(req.password),
        role=models.Role.SUPER_ADMIN,
    )
    db.add(admin)

    org_meta = models.SystemMeta(key="org_name", value=req.org_name)
    init_meta = models.SystemMeta(key="initialized", value="true")
    db.add(org_meta)
    db.add(init_meta)
    db.commit()
    db.refresh(admin)

    audit.log(db, "SYSTEM_INITIALIZED", actor_id=admin.id, actor_role="SUPER_ADMIN",
              details={"org_name": req.org_name, "admin_email": req.email})

    return {"message": "System initialized", "admin_id": admin.id}
