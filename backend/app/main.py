import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import Base, engine
from .routers import setup, auth, admin, voters, elections, candidates, enrollment, voting, results, reports, audit_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Secure E-Voting System", version="0.1.0",
              description="Not certified for government/public elections.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serves uploaded candidate symbol images (backend/uploads/symbols/*) at
# /uploads/symbols/<filename>. Publicly readable - symbols are shown on the
# public ballot, so there's nothing sensitive in this folder.
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(os.path.join(UPLOADS_DIR, "symbols"), exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

app.include_router(setup.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(voters.router)
app.include_router(elections.router)
app.include_router(candidates.router)
app.include_router(enrollment.router)
app.include_router(voting.router)
app.include_router(results.router)
app.include_router(reports.router)
app.include_router(audit_router.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/ready")
def ready():
    return {"status": "ready"}
