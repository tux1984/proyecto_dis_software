"""Repositorio de notificaciones y entregas (RF-12, RF-15, RN-08)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.value_objects import NotificationSegment, RegistrationStatus
from app.infrastructure.models import (
    EnrollmentModel,
    NotificationDeliveryModel,
    NotificationModel,
    UserModel,
)


class NotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(
        self, *, event_id: UUID, subject: str, body: str, segment: str, created_by: UUID
    ) -> UUID:
        nid = uuid4()
        self._s.add(
            NotificationModel(
                id=nid,
                event_id=event_id,
                subject=subject,
                body_template=body,
                segment=segment,
                status="queued",
                created_by=created_by,
            )
        )
        await self._s.flush()
        return nid

    async def recipients_for(
        self, event_id: UUID, segment: str
    ) -> list[tuple[UUID, str]]:
        stmt = (
            select(UserModel.id, UserModel.email)
            .join(EnrollmentModel, EnrollmentModel.user_id == UserModel.id)
            .where(EnrollmentModel.event_id == event_id)
        )
        if segment == NotificationSegment.CONFIRMED.value:
            stmt = stmt.where(EnrollmentModel.status == RegistrationStatus.CONFIRMADA.value)
        elif segment == NotificationSegment.CANCELLED.value:
            stmt = stmt.where(EnrollmentModel.status == RegistrationStatus.CANCELADA.value)
        res = await self._s.execute(stmt)
        return [tuple(row) for row in res.all()]

    async def add_delivery(self, notification_id: UUID, recipient_user_id: UUID) -> UUID:
        did = uuid4()
        self._s.add(
            NotificationDeliveryModel(
                id=did,
                notification_id=notification_id,
                recipient_user_id=recipient_user_id,
                status="pending",
            )
        )
        await self._s.flush()
        return did

    async def mark_delivery(
        self, delivery_id: UUID, status: str, error: str | None = None
    ) -> None:
        m = await self._s.get(NotificationDeliveryModel, delivery_id)
        if m:
            m.status = status
            m.attempts += 1
            m.last_error = error
            if status == "sent":
                m.sent_at = datetime.now(tz=UTC)
            await self._s.flush()

    async def set_status(self, notification_id: UUID, status: str) -> None:
        m = await self._s.get(NotificationModel, notification_id)
        if m:
            m.status = status
            if status == "running":
                m.started_at = datetime.now(tz=UTC)
            elif status in ("completed", "failed"):
                m.completed_at = datetime.now(tz=UTC)
            await self._s.flush()

    async def get_progress(self, notification_id: UUID) -> dict:
        res = await self._s.execute(
            select(NotificationDeliveryModel.status, func.count())
            .where(NotificationDeliveryModel.notification_id == notification_id)
            .group_by(NotificationDeliveryModel.status)
        )
        counts = {status: int(n) for status, n in res.all()}
        m = await self._s.get(NotificationModel, notification_id)
        return {
            "notification_id": str(notification_id),
            "status": m.status if m else "unknown",
            "sent": counts.get("sent", 0),
            "failed": counts.get("failed", 0),
            "pending": counts.get("pending", 0),
        }
