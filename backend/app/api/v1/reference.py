from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.db.models import CategoryRoute, Department, Skill
from app.schemas.common import DepartmentOut, SkillOut
from app.schemas.reference import CategoryOut

router = APIRouter(tags=["reference"])


@router.get("/departments", response_model=list[DepartmentOut])
async def departments(_: CurrentUser, session: SessionDep) -> list[DepartmentOut]:
    rows = await session.scalars(select(Department).order_by(Department.name))
    return [DepartmentOut.model_validate(d) for d in rows]


@router.get("/skills", response_model=list[SkillOut])
async def skills(_: CurrentUser, session: SessionDep) -> list[SkillOut]:
    rows = await session.scalars(select(Skill).order_by(Skill.name))
    return [SkillOut.model_validate(s) for s in rows]


@router.get("/categories", response_model=list[CategoryOut])
async def categories(_: CurrentUser, session: SessionDep) -> list[CategoryOut]:
    rows = await session.scalars(select(CategoryRoute).order_by(CategoryRoute.category))
    return [CategoryOut.model_validate(c) for c in rows.unique()]
