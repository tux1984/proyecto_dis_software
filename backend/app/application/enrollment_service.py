"""EnrollmentService — Facade del flujo de inscripción (SAD §6.1.5, §9.2).

Concentra la regla más crítica del sistema: verificar y reservar cupo de forma
atómica (RN-01), gestionar el pago asíncrono con webhook idempotente (RF-04,
RN-06) y publicar el evento de dominio ``EnrollmentConfirmed`` a sus
observadores. Una sola llamada del router produce varios efectos verificables:
inscripción en BD, job de correo encolado, métrica de cupo y auditoría.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from opentelemetry import trace

from app.config import Settings
from app.domain.errors import (
    CancellationPolicyError,
    DomainError,
    ValidationError,
)
from app.domain.events import EnrollmentConfirmed
from app.domain.ports.adapters import IPaymentAdapter
from app.domain.ports.handlers import IEnrollmentEventHandler
from app.domain.ports.queue import IJobQueue
from app.domain.ports.repositories import (
    IAuditLogRepository,
    IEnrollmentRepository,
    IEventRepository,
)
from app.domain.value_objects import EventStatus, RegistrationStatus
from app.infrastructure.repositories.support_repository import WebhookRepository
from app.observability.metrics import WEBHOOK_PROCESSED

logger = logging.getLogger("pgea.enrollment")
_tracer = trace.get_tracer("pgea.enrollment")


class EnrollmentService:
    def __init__(
        self,
        enrollments: IEnrollmentRepository,
        events: IEventRepository,
        audit: IAuditLogRepository,
        payment: IPaymentAdapter,
        queue: IJobQueue,
        webhooks: WebhookRepository,
        handlers: list[IEnrollmentEventHandler],
        settings: Settings,
    ) -> None:
        self._enrollments = enrollments
        self._events = events
        self._audit = audit
        self._payment = payment
        self._queue = queue
        self._webhooks = webhooks
        self._handlers = handlers
        self._settings = settings

    async def register(
        self, event_id: UUID, user_id: UUID, form_data: dict | None, return_url: str
    ) -> dict:
        event = await self._events.get(event_id)
        if event is None:
            raise ValidationError("Evento no encontrado")
        if event.status != EventStatus.PUBLICADO:
            raise ValidationError("El evento no está disponible para inscripción")

        with _tracer.start_as_current_span("enrollment.reserve_capacity") as span:
            span.set_attribute("event.id", str(event_id))
            span.set_attribute("event.paid", event.is_paid)
            reserved_until = (
                datetime.now(tz=UTC)
                + timedelta(minutes=self._settings.payment_reservation_timeout_minutes)
                if event.is_paid
                else None
            )
            enrollment = await self._enrollments.reserve_capacity_and_create(
                event, user_id, paid=event.is_paid,
                reserved_until=reserved_until, form_data=form_data,
            )

        if not event.is_paid:
            # Gratuita: confirmada de inmediato → publica el evento de dominio.
            await self._publish_confirmed(enrollment.id, event_id, user_id, paid=False)
            logger.info(
                "Inscripción gratuita confirmada (inscripción=%s, evento=%s)",
                enrollment.id, event_id,
            )
            return {"status": "confirmada", "enrollment_id": str(enrollment.id)}

        # Paga: inicia el pago en la pasarela; queda PENDIENTE_PAGO (RN-06).
        intent = await self._payment.create_payment(
            enrollment.id, amount=0.0, return_url=return_url
        )
        enrollment.payment_reference = intent.provider_reference
        await self._enrollments.update(enrollment)
        await self._audit.append(
            actor_user_id=user_id, action="enrollment_pending_payment",
            entity_type="enrollment", entity_id=enrollment.id,
        )
        logger.info(
            "Reserva de pago creada en pendiente_pago (inscripción=%s, ref=%s)",
            enrollment.id, intent.provider_reference,
        )
        return {
            "status": "pendiente_pago",
            "enrollment_id": str(enrollment.id),
            "payment_reference": intent.provider_reference,
            "payment_url": intent.payment_url,
        }

    async def handle_payment_webhook(self, payload: dict, signature: str | None) -> dict:
        result = self._payment.parse_webhook(payload, signature)

        # Idempotencia (RN-06, R-02): no reprocesar el mismo webhook.
        if await self._webhooks.is_processed(result.idempotency_key):
            WEBHOOK_PROCESSED.labels(provider=result.provider, result="duplicate").inc()
            return {"status": "duplicate", "processed": False}

        with _tracer.start_as_current_span("enrollment.confirm_payment") as span:
            span.set_attribute("enrollment.id", str(result.enrollment_id))
            span.set_attribute("webhook.status", result.status)
            enrollment = await self._enrollments.get(result.enrollment_id)
            if enrollment is None:
                WEBHOOK_PROCESSED.labels(provider=result.provider, result="failure").inc()
                raise ValidationError("Inscripción del webhook no encontrada")

            outcome: str
            if result.status == "confirmed":
                enrollment.confirm(payment_reference=result.idempotency_key)
                await self._enrollments.update(enrollment)
                await self._publish_confirmed(
                    enrollment.id, enrollment.event_id, enrollment.user_id, paid=True
                )
                logger.info("Pago confirmado por webhook (inscripción=%s)", enrollment.id)
                outcome = "confirmada"
            else:  # rejected | expired → liberar cupo
                if enrollment.status == RegistrationStatus.PENDIENTE_PAGO:
                    enrollment.expire()
                    await self._enrollments.update(enrollment)
                outcome = "expirada"

            await self._webhooks.record(
                result.provider, result.idempotency_key, payload, enrollment.id
            )

        WEBHOOK_PROCESSED.labels(provider=result.provider, result="success").inc()
        return {"status": outcome, "processed": True}

    async def cancel(self, enrollment_id: UUID, user_id: UUID) -> dict:
        enrollment = await self._enrollments.get(enrollment_id)
        if enrollment is None or enrollment.user_id != user_id:
            raise ValidationError("Inscripción no encontrada")
        event = await self._events.get(enrollment.event_id)
        # Política de cancelación: no se permite tras el inicio del evento (RN-02).
        if event and event.starts_at <= datetime.now(tz=UTC):
            raise CancellationPolicyError("No se puede cancelar un evento ya iniciado")
        enrollment.cancel()
        await self._enrollments.update(enrollment)
        await self._audit.append(
            actor_user_id=user_id, action="enrollment_cancelled",
            entity_type="enrollment", entity_id=enrollment.id,
        )
        return {"status": "cancelada", "enrollment_id": str(enrollment.id)}

    async def list_mine(self, user_id: UUID) -> list[dict]:
        # Enriquecido con título/fecha del evento para "Mis inscripciones".
        return await self._enrollments.list_by_user_with_events(user_id)

    async def _publish_confirmed(
        self, enrollment_id: UUID, event_id: UUID, user_id: UUID, *, paid: bool
    ) -> None:
        event = EnrollmentConfirmed.now(enrollment_id, event_id, user_id, paid=paid)
        for handler in self._handlers:  # Observer: efectos desacoplados
            try:
                await handler.handle(event)
            except DomainError:
                raise
            except Exception as exc:  # un observer no crítico no debe romper el flujo
                logger.warning("Handler %s falló: %s", type(handler).__name__, exc)
