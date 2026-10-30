from dataclasses import dataclass

from redis.asyncio import Redis

from app.core.errors import AppError


@dataclass(frozen=True)
class Limit:
    name: str
    max_hits: int
    window_seconds: int


class RateLimiter:
    """Fixed-window counters in Redis, shared by every API instance."""

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    def _key(self, limit: Limit, subject: str) -> str:
        return f"ratelimit:{limit.name}:{subject.lower()}"

    async def is_blocked(self, limit: Limit, subject: str) -> bool:
        count = await self.redis.get(self._key(limit, subject))
        return count is not None and int(count) >= limit.max_hits

    async def hit(self, limit: Limit, subject: str) -> int:
        key = self._key(limit, subject)
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, limit.window_seconds, nx=True)
            count, _ = await pipe.execute()
        return int(count)

    async def reset(self, limit: Limit, subject: str) -> None:
        await self.redis.delete(self._key(limit, subject))

    async def consume(self, limit: Limit, subject: str, message: str) -> None:
        """Count one hit and raise 429 once the window is full."""
        if await self.hit(limit, subject) > limit.max_hits:
            ttl = await self.redis.ttl(self._key(limit, subject))
            raise AppError(429, "RATE_LIMITED", message, {"retry_after_seconds": max(ttl, 0)})
