"""Observadores de eventos de inscripción (patrón Observer, SAD §9.2).

Al confirmarse una inscripción, ``EnrollmentService`` publica
``EnrollmentConfirmed`` y cada handler reacciona de forma desacoplada:
encolar el correo de confirmación, actualizar la métrica de cupo y auditar.
El servicio emisor no conoce a sus observadores.
"""

from __future__ import annotations

from app.domain.events import DomainEvent, EnrollmentConfirmed
from app.domain.ports.queue import IJobQueue
from app.domain.ports.repositories import IAuditLogRepository, IEventRepository
from app.observability.metrics import EVENT_CAPACITY_AVAILABLE


class NotificationEnqueueHandler:
    """Encola el correo de confirmación (RF-15). Producer de la cola."""

    def __init__(self, queue: IJobQueue) -> None:
        self._queue = queue

    async def handle(self, event: DomainEvent) -> None:
        if not isinstance(event, EnrollmentConfirmed):
            return
        await self._queue.enqueue(
            "send_email",
            {
                "kind": "enrollment_confirmation",
                "enrollment_id": str(event.enrollment_id),
                "event_id": str(event.event_id),
                "user_id": str(event.user_id),
            },
        )


class CapacityMetricHandler:
    """Actualiza el gauge de cupos disponibles del evento (RNF-02)."""

    def __init__(self, event_repo: IEventRepository) -> None:
        self._events = event_repo

    async def handle(self, event: DomainEvent) -> None:
        if not isinstance(event, EnrollmentConfirmed):
            return
        ev = await self._events.get(event.event_id)
        if ev is not None:
            confirmed = await self._events.count_confirmed(event.event_id)
            EVENT_CAPACITY_AVAILABLE.labels(event_id=str(event.event_id)).set(
                max(ev.capacity - confirmed, 0)
            )


class AuditHandler:
    """Registra la confirmación en la auditoría inmutable (RF-29, RN-10)."""

    def __init__(self, audit_repo: IAuditLogRepository) -> None:
        self._audit = audit_repo

    async def handle(self, event: DomainEvent) -> None:
        if not isinstance(event, EnrollmentConfirmed):
            return
        await self._audit.append(
            actor_user_id=event.user_id,
            action="enrollment_confirmed",
            entity_type="enrollment",
            entity_id=event.enrollment_id,
            result="success",
        )
