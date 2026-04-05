import random
from database import SessionLocal, init_db
from models import Employee

def seed():
    init_db()
    db = SessionLocal()

    # Clear existing employees
    db.query(Employee).delete()

    employees = [
        Employee(name="Ravi Kumar", email="ravi@arth.com", department="Engineering", role="Backend Developer", skills="Python,Database,Backend,Bug Fixing"),
        Employee(name="Sneha Reddy", email="sneha@arth.com", department="Engineering", role="Senior Developer", skills="Python,Backend,Bug Fixing"),
        Employee(name="Arjun Mehta", email="arjun@arth.com", department="IT", role="IT Support", skills="Networking,Access,Account Management"),
        Employee(name="Priya Sharma", email="priya@arth.com", department="IT", role="IT Admin", skills="Access,Account Management,Networking"),
        Employee(name="Vikram Nair", email="vikram@arth.com", department="Finance", role="Finance Executive", skills="Payroll,Billing,Reimbursement"),
        Employee(name="Ananya Iyer", email="ananya@arth.com", department="Finance", role="Senior Accountant", skills="Billing,Payroll,Reimbursement"),
        Employee(name="Deepak Singh", email="deepak@arth.com", department="HR", role="HR Manager", skills="Onboarding,Leave Policy,Compliance"),
        Employee(name="Kavya Patel", email="kavya@arth.com", department="HR", role="HR Executive", skills="Leave Policy,Onboarding,Compliance"),
        Employee(name="Rohit Das", email="rohit@arth.com", department="DevOps", role="DevOps Engineer", skills="Server,Infrastructure,Deployment"),
        Employee(name="Meena Joshi", email="meena@arth.com", department="Product", role="Product Manager", skills="Feature Requests,UI,Roadmap"),
    ]

    availabilities = ["Available", "Busy", "On Leave"]
    for emp in employees:
        emp.ticket_load = random.randint(0, 5)
        emp.availability = random.choice(availabilities)

    db.add_all(employees)
    db.commit()
    db.close()
    print("Seeded 10 employees successfully!")

if __name__ == "__main__":
    seed()