from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arq.connections import ArqRedis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import REQUEST_ID_HEADER, RequestContextMiddleware, configure_logging
from app.db.session import create_engine, create_sessionmaker
from app.workers.queue import ArqTriageQueue


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, json=settings.environment == "production")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.settings = settings
        app.state.engine = create_engine(str(settings.database_url))
        app.state.sessionmaker = create_sessionmaker(app.state.engine)
        # ArqRedis is a redis.asyncio.Redis, so one connection pool serves rate limits,
        # readiness checks and the job queue. Connections open lazily on first use.
        app.state.redis = ArqRedis.from_url(
            str(settings.redis_url), socket_connect_timeout=2, socket_timeout=2
        )
        app.state.triage_queue = ArqTriageQueue(app.state.redis)
        try:
            yield
        finally:
            await app.state.redis.aclose()
            await app.state.engine.dispose()

    app = FastAPI(
        title="AI Ticketing API",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)
    app.include_router(api_router)
    return app
