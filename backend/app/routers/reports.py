"""Local PDF / Excel report generation for a published election's results."""
import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import openpyxl

from ..database import get_db
from .. import models, ledger
from ..deps import require_roles, check_election_access
from .results import public_results, _get_election

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _gather(db, election_id, user):
    election = _get_election(db, election_id)
    check_election_access(election, user, db)
    if election.status != models.ElectionStatus.PUBLISHED:
        raise HTTPException(400, "Reports are only available after results are published")
    data = public_results(election_id, db)
    integrity = ledger.verify_chain(db)
    data["integrity_verified"] = integrity["valid"]
    return data


@router.get("/{election_id}/pdf")
def pdf_report(election_id: str, db: Session = Depends(get_db),
                user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN, models.Role.ELECTION_OFFICER))):
    data = _gather(db, election_id, user)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(f"Election Report: {data['election_name']}", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Status: {data['status']}", styles["Normal"]),
        Paragraph(f"Eligible voters: {data['eligible_voters']}", styles["Normal"]),
        Paragraph(f"Votes cast: {data['votes_cast']}", styles["Normal"]),
        Paragraph(f"Turnout: {data['turnout_pct']}%", styles["Normal"]),
        Paragraph(f"Winner: {data['winner']}", styles["Normal"]),
        Paragraph(f"Blockchain/ledger integrity verified: {data['integrity_verified']}", styles["Normal"]),
        Spacer(1, 16),
    ]
    table_data = [["Candidate", "Votes", "Percentage"]] + [
        [r["name"], r["votes"], f"{r['percentage']}%"] for r in data["results"]]
    t = Table(table_data)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
    ]))
    elements.append(t)
    doc.build(elements)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf",
                              headers={"Content-Disposition": f"attachment; filename=election_{election_id}_report.pdf"})


@router.get("/{election_id}/excel")
def excel_report(election_id: str, db: Session = Depends(get_db),
                  user: models.User = Depends(require_roles(models.Role.SUPER_ADMIN, models.Role.ELECTION_OFFICER))):
    data = _gather(db, election_id, user)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Election", data["election_name"]])
    ws.append(["Status", data["status"]])
    ws.append(["Eligible voters", data["eligible_voters"]])
    ws.append(["Votes cast", data["votes_cast"]])
    ws.append(["Turnout %", data["turnout_pct"]])
    ws.append(["Winner", data["winner"]])
    ws.append(["Ledger integrity verified", data["integrity_verified"]])
    ws.append([])
    ws.append(["Candidate", "Votes", "Percentage"])
    for r in data["results"]:
        ws.append([r["name"], r["votes"], r["percentage"]])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              headers={"Content-Disposition": f"attachment; filename=election_{election_id}_report.xlsx"})
