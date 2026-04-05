from sqlalchemy.orm import Session
from models import Employee

DEPARTMENT_MAP = {
    "DB": "Engineering",
    "Bug": "Engineering",
    "Server": "DevOps",
    "Access": "IT",
    "Billing": "Finance",
    "HR": "HR",
    "Feature": "Product",
    "Other": "IT"
}

PRIORITY_BUMPS = {
    "DB": "Critical",
    "Server": "Critical",
    "Access": "High",
    "Legal": "High"
}

def apply_priority_bump(category: str, current_severity: str) -> str:
    if category in PRIORITY_BUMPS:
        return PRIORITY_BUMPS[category]
    return current_severity

def get_assignee(department: str, skills_needed: list, db: Session):
    employees = db.query(Employee).filter(
        Employee.department == department,
        Employee.availability != "On Leave",
        Employee.active == True
    ).all()

    if not employees:
        # Fallback: any available employee in department
        employees = db.query(Employee).filter(
            Employee.department == department,
            Employee.active == True
        ).all()

    if not employees:
        return None

    def score(emp):
        emp_skills = [s.strip().lower() for s in emp.skills.split(",")]
        skill_score = sum(3 for s in skills_needed if s.lower() in emp_skills)
        load_penalty = emp.ticket_load
        return skill_score - load_penalty

    best = max(employees, key=score)
    return best