"""Cola de jobs sobre PostgreSQL (ADR-09).

* **Producer** (``PostgresJobQueue.enqueue``): escribe un job en ``queued_jobs``
  dentro de la transacción del request (patrón outbox: encolar y la operación
  de negocio se confirman juntas).
* **Consumer** (funciones ``claim_next_job`` / ``complete`` / ``fail``): el
  worker reclama jobs con ``SELECT … FOR UPDATE SKIP LOCKED`` para que cada job
  lo procese exactamente un worker, habilitando escalado horizontal de workers.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models import FailedJobModel, QueuedJobModel


def _now() -> datetime:
    return datetime.now(tz=UTC)


class PostgresJobQueue:
    """Lado productor del puerto ``IJobQueue``."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def enqueue(self, job_type: str, payload: dict) -> UUID:
        jid = uuid4()
        self._s.add(
            QueuedJobModel(id=jid, job_type=job_type, payload=payload, status="pending")
        )
        await self._s.flush()
        return jid


# ---- Lado consumidor (worker) -----------------------------------------------
async def claim_next_job(session: AsyncSession) -> QueuedJobModel | None:
    """Reclama el siguiente job disponible con FOR UPDATE SKIP LOCKED."""
    stmt = (
        select(QueuedJobModel)
        .where(QueuedJobModel.status == "pending")
        .where(
            (QueuedJobModel.next_retry_at.is_(None))
            | (QueuedJobModel.next_retry_at <= _now())
        )
        .order_by(QueuedJobModel.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = (await session.execute(stmt)).scalar_one_or_none()
    if job is not None:
        job.status = "processing"
        await session.flush()
    return job


async def complete_job(session: AsyncSession, job: QueuedJobModel) -> None:
    job.status = "done"
    job.processed_at = _now()
    await session.flush()


async def fail_job(
    session: AsyncSession, job: QueuedJobModel, error: str, max_retries: int
) -> None:
    """Reintenta con backoff exponencial; agotados los intentos, va al DLQ."""
    job.attempts += 1
    if job.attempts >= max_retries:
        session.add(
            FailedJobModel(
                job_type=job.job_type, payload=job.payload, error_message=error
            )
        )
        job.status = "failed"
        job.processed_at = _now()
    else:
        backoff = min(2 ** job.attempts, 300)  # segundos, tope 5 min
        job.status = "pending"
        job.next_retry_at = _now() + timedelta(seconds=backoff)
    await session.flush()


async def pending_count(session: AsyncSession) -> int:
    res = await session.execute(
        select(func.count()).select_from(QueuedJobModel).where(
            QueuedJobModel.status.in_(("pending", "processing"))
        )
    )
    return int(res.scalar_one())
