from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, PlainSerializer, StringConstraints


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must include a timezone offset")
    return value


# Every timestamp leaves the API as ISO 8601 in UTC with a trailing Z.
UtcDatetime = Annotated[
    datetime,
    AfterValidator(_require_aware),
    PlainSerializer(
        lambda v: v.astimezone(UTC).isoformat().replace("+00:00", "Z"), return_type=str
    ),
]

Trimmed = Annotated[str, StringConstraints(strip_whitespace=True)]


class Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None


class DepartmentOut(Schema):
    id: UUID
    name: str
    slug: str


class SkillOut(Schema):
    id: UUID
    name: str
    slug: str
