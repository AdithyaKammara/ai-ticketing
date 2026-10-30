import os
import time
from datetime import UTC, datetime
from uuid import UUID


def utcnow() -> datetime:
    """Timezone-aware current time. Naive datetimes never enter the system."""
    return datetime.now(UTC)


def uuid7() -> UUID:
    """RFC 9562 UUIDv7: a millisecond timestamp prefix, so ids sort by creation time."""
    millis = time.time_ns() // 1_000_000
    rand = int.from_bytes(os.urandom(10))
    rand_a = rand >> 68  # 12 bits
    rand_b = rand & ((1 << 62) - 1)  # 62 bits
    value = (millis & ((1 << 48) - 1)) << 80 | 0x7 << 76 | rand_a << 64 | 0b10 << 62 | rand_b
    return UUID(int=value)
