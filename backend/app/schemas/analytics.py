from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.schemas.common import Schema

BreakdownBy = Literal["department", "category", "severity"]


class SummaryOut(Schema):
    open_tickets: int
    resolved_this_period: int
    auto_resolved: int
    auto_resolution_rate: float
    reopen_rate: float
    median_first_response_minutes: float | None
    sla_breaches: int


class VolumePoint(BaseModel):
    day: date
    created: int
    resolved: int


class BreakdownBucket(BaseModel):
    key: str
    label: str
    count: int


class ConfidenceBucket(BaseModel):
    bucket: str
    count: int


class AiQualityOut(Schema):
    triaged: int
    auto_resolved: int
    routed: int
    failed: int
    auto_resolution_rate: float
    reopen_rate: float
    helpful_rate: float | None
    confidence_histogram: list[ConfidenceBucket]
