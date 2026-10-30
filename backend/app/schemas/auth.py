from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, StringConstraints

from app.db.enums import Availability, Role
from app.schemas.common import DepartmentOut, Schema, SkillOut

Password = Annotated[str, Field(min_length=10, max_length=128)]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class RegisterIn(BaseModel):
    email: EmailStr
    password: Password
    full_name: FullName


class LoginIn(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=128)]


class MeOut(Schema):
    id: UUID
    email: str
    full_name: str
    role: Role
    department: DepartmentOut | None
    availability: Availability
    skills: list[SkillOut]


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int
    user: MeOut
