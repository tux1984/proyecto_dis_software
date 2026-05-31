"""NotificationService — comunicaciones masivas asíncronas (RF-12, RF-15, RN-08).

Crea el lote, encola un job de correo por destinatario y retorna de inmediato
(202). El hilo principal no se bloquea: el ``worker`` procesa los envíos con
reintentos. El estado por destinatario queda consultable (observabilidad).
"""

from __future__ import annotations

from uuid import UUID

from app.domain.ports.queue import IJobQueue
from app.domain.ports.repositories import IAuditLogRepository
from app.infrastructure.repositories.notification_repository import NotificationRepository


class NotificationService:
    def __init__(
        self,
        notifications: NotificationRepository,
        queue: IJobQueue,
        audit: IAuditLogRepository,
    ) -> None:
        self._notifications = notifications
        self._queue = queue
        self._audit = audit

    async def broadcast(
        self, *, event_id: UUID, actor_id: UUID, subject: str, body: str, segment: str
    ) -> dict:
        notification_id = await self._notifications.create(
            event_id=event_id, subject=subject, body=body,
            segment=segment, created_by=actor_id,
        )
        recipients = await self._notifications.recipients_for(event_id, segment)
        for user_id, email in recipients:
            delivery_id = await self._notifications.add_delivery(notification_id, user_id)
            await self._queue.enqueue(
                "send_email",
                {
                    "kind": "broadcast",
                    "notification_id": str(notification_id),
                    "delivery_id": str(delivery_id),
                    "to": email,
                    "subject": subject,
                    "body": body,
                },
            )
        await self._audit.append(
            actor_user_id=actor_id, action="notification_broadcast",
            entity_type="notification", entity_id=notification_id,
        )
        return {
            "notification_id": str(notification_id),
            "recipients": len(recipients),
            "status": "queued",
        }

    async def status(self, notification_id: UUID) -> dict:
        return await self._notifications.get_progress(notification_id)
