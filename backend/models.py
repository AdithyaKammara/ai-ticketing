from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    department = Column(String, nullable=False)
    role = Column(String, nullable=False)
    skills = Column(String, nullable=False)  # comma-separated
    ticket_load = Column(Integer, default=0)
    availability = Column(String, default="Available")  # Available/Busy/On Leave
    active = Column(Boolean, default=True)


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    submitter_name = Column(String, nullable=False)
    submitter_email = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, default="New")  # New/In Progress/Auto-Resolved/Resolved
    category = Column(String)
    severity = Column(String)
    department = Column(String)
    assigned_to = Column(Integer, ForeignKey("employees.id"), nullable=True)
    ai_summary = Column(Text)
    auto_response = Column(Text)
    sentiment = Column(String)
    confidence = Column(Float)
    helpful = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TicketEvent(Base):
    __tablename__ = "ticket_events"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    action = Column(String, nullable=False)
    note = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)