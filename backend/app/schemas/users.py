from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.db.enums import Availability, Role
from app.schemas.auth import FullName, Password
from app.schemas.common import DepartmentOut, Schema, SkillOut


class UserOut(Schema):
    id: UUID
    email: str
    full_name: str
    role: Role
    department: DepartmentOut | None
    availability: Availability
    is_active: bool
    skills: list[SkillOut]
    open_tickets: int = 0


class UserCreateIn(BaseModel):
    email: EmailStr
    full_name: FullName
    password: Password
    role: Role = Role.AGENT
    department_id: UUID | None = None
    availability: Availability = Availability.AVAILABLE
    skills: list[str] = Field(default_factory=list, max_length=20)


class UserUpdateIn(BaseModel):
    """Admins may change any field; everyone else may only change their own availability."""

    full_name: FullName | None = None
    role: Role | None = None
    department_id: UUID | None = None
    availability: Availability | None = None
    skills: list[str] | None = Field(default=None, max_length=20)
