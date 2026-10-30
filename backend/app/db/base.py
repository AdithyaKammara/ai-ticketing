from datetime import datetime
from enum import StrEnum
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import DateTime, Enum, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.clock import uuid7

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[type, Any]] = {datetime: DateTime(timezone=True)}


class IdMixin:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


def pg_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """A native Postgres enum type whose labels are the StrEnum values."""
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])
