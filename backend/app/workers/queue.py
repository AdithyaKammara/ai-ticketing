from typing import Protocol
from uuid import UUID

from arq.connections import ArqRedis

TRIAGE_JOB = "triage_ticket"


class TriageQueue(Protocol):
    async def enqueue_triage(self, ticket_id: UUID) -> None: ...


class ArqTriageQueue:
    """Hands triage to the ARQ worker (milestone M2) through Redis."""

    def __init__(self, redis: ArqRedis) -> None:
        self.redis = redis

    async def enqueue_triage(self, ticket_id: UUID) -> None:
        # The job id makes a double submit for the same ticket a no-op while one is queued.
        await self.redis.enqueue_job(TRIAGE_JOB, str(ticket_id), _job_id=f"triage:{ticket_id}")
