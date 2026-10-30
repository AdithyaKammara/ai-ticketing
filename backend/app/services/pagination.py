"""Keyset (cursor) pagination over any mix of ascending and descending sort keys."""

import base64
import binascii
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, and_, false, or_
from sqlalchemy.orm import QueryableAttribute

from app.core.errors import AppError

type KeyValue = datetime | int | UUID


@dataclass(frozen=True)
class SortKey[T]:
    """One ORDER BY term: the SQL expression and the same value computed from a loaded row."""

    expr: ColumnElement[Any] | QueryableAttribute[Any]
    descending: bool
    value_of: Callable[[T], KeyValue]

    def order_by(self) -> ColumnElement[Any]:
        return self.expr.desc() if self.descending else self.expr.asc()


def encode_cursor(values: Sequence[KeyValue]) -> str:
    encoded = [
        {"t": "dt", "v": v.isoformat()}
        if isinstance(v, datetime)
        else {"t": "uuid", "v": str(v)}
        if isinstance(v, UUID)
        else {"t": "int", "v": v}
        for v in values
    ]
    return base64.urlsafe_b64encode(json.dumps(encoded).encode()).decode().rstrip("=")


def decode_cursor(cursor: str, expected: int) -> list[KeyValue]:
    try:
        raw = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        values: list[KeyValue] = []
        for item in raw:
            kind, value = item["t"], item["v"]
            if kind == "dt":
                values.append(datetime.fromisoformat(value))
            elif kind == "uuid":
                values.append(UUID(value))
            elif kind == "int":
                values.append(int(value))
            else:
                raise ValueError(kind)
    except (ValueError, TypeError, KeyError, binascii.Error, json.JSONDecodeError) as exc:
        raise AppError(400, "INVALID_CURSOR", "The page cursor is invalid") from exc
    if len(values) != expected:
        raise AppError(400, "INVALID_CURSOR", "The page cursor is invalid")
    return values


def after_cursor[T](keys: Sequence[SortKey[T]], values: Sequence[KeyValue]) -> ColumnElement[bool]:
    """Rows strictly after `values` in the order `keys` defines."""
    clauses: list[ColumnElement[bool]] = []
    for i, key in enumerate(keys):
        equal_prefix = [keys[j].expr == values[j] for j in range(i)]
        beyond = key.expr < values[i] if key.descending else key.expr > values[i]
        clauses.append(and_(*equal_prefix, beyond))
    return or_(false(), *clauses)


def next_cursor[T](keys: Sequence[SortKey[T]], rows: Sequence[T], limit: int) -> str | None:
    if len(rows) <= limit:
        return None
    last = rows[limit - 1]
    return encode_cursor([key.value_of(last) for key in keys])
