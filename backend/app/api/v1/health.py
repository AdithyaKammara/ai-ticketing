import asyncio
from collections.abc import Coroutine
from typing import Any, Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

router = APIRouter(tags=["health"])

CHECK_TIMEOUT_S = 2.0


class HealthOut(BaseModel):
    status: Literal["ok"]


class ReadyOut(BaseModel):
    status: Literal["ok", "unavailable"]
    checks: dict[str, bool]


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    """Liveness: the process is up. Never touches dependencies."""
    return HealthOut(status="ok")


@router.get(
    "/ready",
    response_model=ReadyOut,
    responses={503: {"model": ReadyOut}},
)
async def ready(request: Request) -> ReadyOut | JSONResponse:
    """Readiness: the database and Redis both answer."""
    checks = {
        "database": await _check(_ping_database(request)),
        "redis": await _check(_ping_redis(request)),
    }
    if all(checks.values()):
        return ReadyOut(status="ok", checks=checks)
    body = ReadyOut(status="unavailable", checks=checks)
    return JSONResponse(status_code=503, content=body.model_dump())


async def _ping_database(request: Request) -> None:
    async with request.app.state.engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def _ping_redis(request: Request) -> None:
    await request.app.state.redis.ping()


async def _check(probe: Coroutine[Any, Any, None]) -> bool:
    try:
        await asyncio.wait_for(probe, timeout=CHECK_TIMEOUT_S)
    except Exception:
        return False
    return True
