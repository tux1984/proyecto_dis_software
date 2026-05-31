"""Worker asíncrono (ADR-09, Producer-Consumer).

Consume ``queued_jobs`` con ``FOR UPDATE SKIP LOCKED`` (un job por worker),
procesa ``send_email`` y ``generate_certificate`` con reintentos/backoff y DLQ,
y ejecuta tareas periódicas (expirar reservas de pago vencidas, RN-06).
Comparte imagen con el API; corre como contenedor separado.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from uuid import UUID

from opentelemetry import trace

from app.config import get_settings
from app.domain.ports.adapters import EmailMessage
from app.infrastructure.adapters.factory import AdapterFactory
from app.infrastructure.db import SessionLocal
from app.infrastructure.models import QueuedJobModel
from app.infrastructure.queue.postgres_queue import (
    claim_next_job,
    complete_job,
    fail_job,
    pending_count,
)
from app.infrastructure.repositories.certificate_repository import CertificateRepository
from app.infrastructure.repositories.enrollment_repository import EnrollmentRepository
from app.infrastructure.repositories.event_repository import EventRepository
from app.infrastructure.repositories.notification_repository import NotificationRepository
from app.infrastructure.repositories.user_repository import UserRepository
from app.observability.logging_config import configure_logging
from app.observability.metrics import (
    CERTIFICATE_DURATION,
    ENROLLMENT_QUEUE_SIZE,
    NOTIFICATION_SENT,
)
from app.observability.otel import init_tracing

logger = logging.getLogger("pgea.worker")
_tracer = trace.get_tracer("pgea.worker")


async def _handle_send_email(session, payload: dict) -> None:
    email = AdapterFactory().create_email()
    kind = payload.get("kind", "broadcast")

    if kind == "enrollment_confirmation":
        user = await UserRepository(session).get(UUID(payload["user_id"]))
        event = await EventRepository(session).get(UUID(payload["event_id"]))
        if user is None or event is None:
            return
        message = EmailMessage(
            to=user.email,
            subject=f"Inscripción confirmada: {event.title}",
            body=f"Hola {user.full_name}, tu inscripción a '{event.title}' está confirmada.",
        )
        await email.send(message)
    else:  # broadcast / speaker_invite
        message = EmailMessage(
            to=payload["to"], subject=payload["subject"], body=payload["body"]
        )
        await email.send(message)
        if payload.get("delivery_id"):
            await NotificationRepository(session).mark_delivery(
                UUID(payload["delivery_id"]), "sent"
            )

    NOTIFICATION_SENT.labels(provider=email.provider_name, result="success").inc()


async def _handle_generate_certificate(session, payload: dict) -> None:
    from app.infrastructure.pdf import generate_certificate_pdf

    start = time.perf_counter()
    user = await UserRepository(session).get(UUID(payload["user_id"]))
    event = await EventRepository(session).get(UUID(payload["event_id"]))
    if user is None or event is None:
        return
    loop = asyncio.get_running_loop()
    pdf_url = await loop.run_in_executor(
        None,
        lambda: generate_certificate_pdf(
            verification_code=payload["verification_code"],
            full_name=user.full_name,
            event_title=event.title,
            event_date=event.starts_at.strftime("%d/%m/%Y"),
            cert_type=payload.get("cert_type", "asistencia"),
        ),
    )
    await CertificateRepository(session).set_pdf_url(UUID(payload["cert_id"]), pdf_url)
    CERTIFICATE_DURATION.observe(time.perf_counter() - start)


_HANDLERS = {
    "send_email": _handle_send_email,
    "generate_certificate": _handle_generate_certificate,
}


async def _process_one() -> bool:
    settings = get_settings()

    # Tx1: reclamar y confirmar el cambio a 'processing' (libera el lock).
    async with SessionLocal() as session:
        job = await claim_next_job(session)
        if job is None:
            await session.commit()
            return False
        job_id, job_type, payload = job.id, job.job_type, dict(job.payload)
        await session.commit()

    # Tx2: procesar el job (efectos de negocio) y marcar resultado.
    with _tracer.start_as_current_span("worker.process_job") as span:
        span.set_attribute("job.type", job_type)
        span.set_attribute("job.id", str(job_id))
        try:
            async with SessionLocal() as session:
                await _HANDLERS[job_type](session, payload)
                done = await session.get(QueuedJobModel, job_id)
                if done is not None:
                    await complete_job(session, done)
                await session.commit()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.exception("Job %s falló: %s", job_id, exc)
            if job_type == "send_email":
                NOTIFICATION_SENT.labels(provider="mock", result="failure").inc()
            async with SessionLocal() as session:
                failed = await session.get(QueuedJobModel, job_id)
                if failed is not None:
                    await fail_job(session, failed, str(exc), settings.worker_max_retries)
                    await session.commit()
            return True


async def _expire_reservations() -> None:
    """Libera cupos de reservas de pago vencidas (RN-06)."""
    now = datetime.now(tz=UTC)
    async with SessionLocal() as session:
        repo = EnrollmentRepository(session)
        expired = await repo.list_expired_pending(now)
        for enrollment in expired:
            try:
                enrollment.expire()
                await repo.update(enrollment)
            except Exception:  # noqa: BLE001 — ya en estado terminal
                continue
        if expired:
            logger.info("Reservas expiradas liberadas: %d", len(expired))
        await session.commit()


async def _update_queue_gauge() -> None:
    async with SessionLocal() as session:
        ENROLLMENT_QUEUE_SIZE.set(await pending_count(session))


async def main() -> None:
    configure_logging()
    init_tracing()  # worker también emite trazas (jobs correlacionados)
    settings = get_settings()

    # El worker expone sus métricas (cola, correos, certificados) en :8001 para
    # que Prometheus las raspe: es un proceso aparte con su propio registro.
    try:
        from prometheus_client import start_http_server

        start_http_server(8001)
        logger.info("Métricas del worker expuestas en :8001/metrics")
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo exponer /metrics del worker: %s", exc)

    logger.info("Worker PGEA iniciado (poll=%ss)", settings.worker_poll_interval_seconds)

    last_periodic = 0.0
    while True:
        try:
            processed = await _process_one()
            await _update_queue_gauge()
            now = time.monotonic()
            if now - last_periodic > 30:
                await _expire_reservations()
                last_periodic = now
            if not processed:
                await asyncio.sleep(settings.worker_poll_interval_seconds)
        except Exception as exc:  # noqa: BLE001 — el worker nunca debe morir
            logger.exception("Error en el bucle del worker: %s", exc)
            await asyncio.sleep(settings.worker_poll_interval_seconds)


if __name__ == "__main__":
    asyncio.run(main())
