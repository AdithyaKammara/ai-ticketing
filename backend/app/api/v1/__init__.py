from fastapi import APIRouter

from app.api.v1 import analytics, auth, health, reference, tickets, users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(tickets.router)
api_router.include_router(users.router)
api_router.include_router(reference.router)
api_router.include_router(analytics.router)
