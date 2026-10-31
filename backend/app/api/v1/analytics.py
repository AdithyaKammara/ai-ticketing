from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import AdminUser, SessionDep, StaffUser
from app.schemas.analytics import (
    AiQualityOut,
    BreakdownBucket,
    BreakdownBy,
    SummaryOut,
    VolumePoint,
)
from app.services import analytics
from app.services.analytics import DateRange

router = APIRouter(prefix="/analytics", tags=["analytics"])


def date_range(
    frm: Annotated[date | None, Query(alias="from")] = None,
    to: date | None = None,
) -> DateRange:
    return DateRange.of(frm, to)


RangeDep = Annotated[DateRange, Depends(date_range)]


@router.get("/summary", response_model=SummaryOut)
async def summary(user: StaffUser, session: SessionDep, rng: RangeDep) -> SummaryOut:
    return await analytics.summary(session, user, rng)


@router.get("/volume", response_model=list[VolumePoint])
async def volume(user: StaffUser, session: SessionDep, rng: RangeDep) -> list[VolumePoint]:
    return await analytics.volume(session, user, rng)


@router.get("/breakdown", response_model=list[BreakdownBucket])
async def breakdown(
    user: StaffUser,
    session: SessionDep,
    rng: RangeDep,
    by: BreakdownBy = "category",
) -> list[BreakdownBucket]:
    return await analytics.breakdown(session, user, rng, by)


@router.get("/ai-quality", response_model=AiQualityOut)
async def ai_quality(_: AdminUser, session: SessionDep, rng: RangeDep) -> AiQualityOut:
    return await analytics.ai_quality(session, rng)
