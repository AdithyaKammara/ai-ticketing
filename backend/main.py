from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from ai_engine import analyze_ticket
from models import Ticket, TicketEvent, Employee
from database import get_db, init_db
from routing import get_assignee, apply_priority_bump

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

init_db()

# ── Schemas ──────────────────────────────────────────
class TicketCreate(BaseModel):
    submitter_name: str
    submitter_email: str
    title: str
    description: str

class FeedbackSchema(BaseModel):
    helpful: bool

class StatusUpdate(BaseModel):
    status: str

class NoteCreate(BaseModel):
    note: str

class EmployeeCreate(BaseModel):
    name: str
    email: str
    department: str
    role: str
    skills: str

class EmployeeUpdate(BaseModel):
    availability: Optional[str] = None
    skills: Optional[str] = None
    role: Optional[str] = None

# ── Tickets ──────────────────────────────────────────
@app.post("/tickets")
def create_ticket(data: TicketCreate, db: Session = Depends(get_db)):
    ai = analyze_ticket(data.title, data.description)

    severity = apply_priority_bump(ai.get("category", ""), ai.get("severity", "Medium"))

    ticket = Ticket(
        submitter_name=data.submitter_name,
        submitter_email=data.submitter_email,
        title=data.title,
        description=data.description,
        category=ai.get("category"),
        severity=severity,
        department=ai.get("department"),
        ai_summary=ai.get("summary"),
        auto_response=ai.get("auto_response"),
        sentiment=ai.get("sentiment"),
        confidence=ai.get("confidence"),
    )

    if ai.get("resolution_path") == "auto-resolve":
        ticket.status = "Auto-Resolved"
    else:
        ticket.status = "New"
        skills_needed = ai.get("category", "").split("|")
        assignee = get_assignee(ai.get("department", ""), skills_needed, db)
        if assignee:
            ticket.assigned_to = assignee.id
            assignee.ticket_load += 1

    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    event = TicketEvent(
        ticket_id=ticket.id,
        action="Ticket created and AI analyzed",
        note=f"Category: {ticket.category}, Severity: {ticket.severity}, Resolution: {ai.get('resolution_path')}"
    )
    db.add(event)
    db.commit()

    return build_ticket_response(ticket, db)

@app.get("/tickets")
def get_tickets(status: Optional[str] = None, department: Optional[str] = None,
                severity: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Ticket)
    if status:
        query = query.filter(Ticket.status == status)
    if department:
        query = query.filter(Ticket.department == department)
    if severity:
        query = query.filter(Ticket.severity == severity)
    tickets = query.order_by(Ticket.created_at.desc()).all()
    return [build_ticket_response(t, db) for t in tickets]

@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return build_ticket_response(ticket, db)

@app.patch("/tickets/{ticket_id}/status")
def update_status(ticket_id: int, data: StatusUpdate, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.status = data.status
    event = TicketEvent(ticket_id=ticket_id, action=f"Status changed to {data.status}")
    db.add(event)
    db.commit()
    return {"message": "Status updated"}

@app.post("/tickets/{ticket_id}/feedback")
def submit_feedback(ticket_id: int, data: FeedbackSchema, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket.helpful = data.helpful
    db.commit()
    return {"message": "Feedback recorded"}

@app.post("/tickets/{ticket_id}/events")
def add_note(ticket_id: int, data: NoteCreate, db: Session = Depends(get_db)):
    event = TicketEvent(ticket_id=ticket_id, action="Internal note", note=data.note)
    db.add(event)
    db.commit()
    return {"message": "Note added"}

@app.get("/tickets/{ticket_id}/events")
def get_events(ticket_id: int, db: Session = Depends(get_db)):
    events = db.query(TicketEvent).filter(TicketEvent.ticket_id == ticket_id).all()
    return [{"id": e.id, "action": e.action, "note": e.note,
             "timestamp": e.timestamp.isoformat()} for e in events]

# ── Employees ─────────────────────────────────────────
@app.get("/employees")
def get_employees(department: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Employee).filter(Employee.active == True)
    if department:
        query = query.filter(Employee.department == department)
    return [build_employee_response(e) for e in query.all()]

@app.post("/employees")
def create_employee(data: EmployeeCreate, db: Session = Depends(get_db)):
    emp = Employee(**data.dict())
    db.add(emp)
    db.commit()
    db.refresh(emp)
    return build_employee_response(emp)

@app.put("/employees/{emp_id}")
def update_employee(emp_id: int, data: EmployeeUpdate, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    if data.availability:
        emp.availability = data.availability
    if data.skills:
        emp.skills = data.skills
    if data.role:
        emp.role = data.role
    db.commit()
    return build_employee_response(emp)

@app.delete("/employees/{emp_id}")
def delete_employee(emp_id: int, db: Session = Depends(get_db)):
    emp = db.query(Employee).filter(Employee.id == emp_id).first()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")
    emp.active = False
    db.commit()
    return {"message": "Employee deactivated"}

# ── Analytics ─────────────────────────────────────────
@app.get("/analytics/summary")
def analytics_summary(db: Session = Depends(get_db)):
    total = db.query(Ticket).count()
    resolved = db.query(Ticket).filter(Ticket.status == "Resolved").count()
    auto_resolved = db.query(Ticket).filter(Ticket.status == "Auto-Resolved").count()
    open_tickets = db.query(Ticket).filter(Ticket.status == "New").count()
    rate = round((auto_resolved / total * 100), 1) if total > 0 else 0
    return {
        "total_open": open_tickets,
        "total_resolved": resolved,
        "total_auto_resolved": auto_resolved,
        "total_tickets": total,
        "auto_resolution_rate": rate
    }

@app.get("/analytics/by-department")
def analytics_by_department(db: Session = Depends(get_db)):
    from sqlalchemy import func
    results = db.query(Ticket.department, func.count(Ticket.id))\
        .filter(Ticket.status == "New")\
        .group_by(Ticket.department).all()
    return [{"department": r[0], "open_count": r[1]} for r in results]

@app.get("/analytics/top-categories")
def analytics_top_categories(db: Session = Depends(get_db)):
    from sqlalchemy import func
    results = db.query(Ticket.category, func.count(Ticket.id))\
        .group_by(Ticket.category)\
        .order_by(func.count(Ticket.id).desc()).limit(5).all()
    return [{"category": r[0], "count": r[1]} for r in results]

@app.get("/analytics/auto-resolution-rate")
def auto_resolution_rate(db: Session = Depends(get_db)):
    total = db.query(Ticket).count()
    auto = db.query(Ticket).filter(Ticket.status == "Auto-Resolved").count()
    rate = round((auto / total * 100), 1) if total > 0 else 0
    return {"auto_resolution_rate": rate}

# ── Helpers ───────────────────────────────────────────
def build_ticket_response(ticket: Ticket, db: Session):
    assignee = None
    if ticket.assigned_to:
        emp = db.query(Employee).filter(Employee.id == ticket.assigned_to).first()
        if emp:
            assignee = {"id": emp.id, "name": emp.name, "department": emp.department}
    return {
        "id": ticket.id,
        "submitter_name": ticket.submitter_name,
        "submitter_email": ticket.submitter_email,
        "title": ticket.title,
        "description": ticket.description,
        "status": ticket.status,
        "category": ticket.category,
        "severity": ticket.severity,
        "department": ticket.department,
        "assigned_to": assignee,
        "ai_summary": ticket.ai_summary,
        "auto_response": ticket.auto_response,
        "sentiment": ticket.sentiment,
        "confidence": ticket.confidence,
        "helpful": ticket.helpful,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None
    }

def build_employee_response(emp: Employee):
    return {
        "id": emp.id,
        "name": emp.name,
        "email": emp.email,
        "department": emp.department,
        "role": emp.role,
        "skills": emp.skills,
        "ticket_load": emp.ticket_load,
        "availability": emp.availability,
        "active": emp.active
    }
@app.post("/seed")
def seed_employees(db: Session = Depends(get_db)):
    from seed_data import seed
    seed()
    return {"message": "Seeded successfully"}