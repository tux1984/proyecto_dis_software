"""Consultas de agregación para dashboards (RF-14, RF-25).

Lecturas analíticas separadas del modelo transaccional. En producción podrían
ir a una réplica de lectura (deuda técnica documentada en el SAD §14.2).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.value_objects import EventStatus, RegistrationStatus
from app.infrastructure.models import (
    AttendanceRecordModel,
    CategoryModel,
    EnrollmentModel,
    EventModel,
)


class StatsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def institutional_dashboard(self) -> dict:
        total_events = await self._scalar(
            select(func.count()).select_from(EventModel)
        )
        published = await self._scalar(
            select(func.count()).select_from(EventModel).where(
                EventModel.status == EventStatus.PUBLICADO.value
            )
        )
        total_enroll = await self._scalar(
            select(func.count()).select_from(EnrollmentModel)
        )
        confirmed = await self._scalar(
            select(func.count()).select_from(EnrollmentModel).where(
                EnrollmentModel.status == RegistrationStatus.CONFIRMADA.value
            )
        )

        by_faculty = await self._s.execute(
            select(CategoryModel.faculty, func.count(EventModel.id))
            .join(EventModel, EventModel.category_id == CategoryModel.id)
            .group_by(CategoryModel.faculty)
        )
        by_modality = await self._s.execute(
            select(EventModel.modality, func.count()).group_by(EventModel.modality)
        )
        by_status = await self._s.execute(
            select(EventModel.status, func.count()).group_by(EventModel.status)
        )
        return {
            "total_events": total_events,
            "published_events": published,
            "total_enrollments": total_enroll,
            "confirmed_enrollments": confirmed,
            "events_by_faculty": {r[0] or "Sin facultad": r[1] for r in by_faculty.all()},
            "events_by_modality": {r[0]: r[1] for r in by_modality.all()},
            "events_by_status": {r[0]: r[1] for r in by_status.all()},
        }

    async def event_dashboard(self, event_id: UUID) -> dict:
        event = await self._s.get(EventModel, event_id)
        if event is None:
            return {}
        by_status = await self._s.execute(
            select(EnrollmentModel.status, func.count())
            .where(EnrollmentModel.event_id == event_id)
            .group_by(EnrollmentModel.status)
        )
        counts: dict[str, int] = {r[0]: r[1] for r in by_status.all()}
        confirmed = counts.get(RegistrationStatus.CONFIRMADA.value, 0)
        attendance = await self._scalar(
            select(func.count()).select_from(AttendanceRecordModel).where(
                AttendanceRecordModel.event_id == event_id
            )
        )
        return {
            "event_id": str(event_id),
            "title": event.title,
            "capacity": event.capacity,
            "enrollments_by_status": counts,
            "confirmed": confirmed,
            "occupancy_rate": round(confirmed / event.capacity, 3) if event.capacity else 0,
            "attendance": attendance,
        }

    async def list_events_by_status(self, status: str) -> list[dict]:
        res = await self._s.execute(
            select(EventModel).where(EventModel.status == status).order_by(
                EventModel.created_at.desc()
            )
        )
        return [
            {
                "id": str(e.id),
                "title": e.title,
                "organizer_id": str(e.organizer_id),
                "modality": e.modality,
                "starts_at": e.starts_at.isoformat() if e.starts_at else None,
            }
            for e in res.scalars().all()
        ]

    async def _scalar(self, stmt) -> int:
        res = await self._s.execute(stmt)
        return int(res.scalar_one())
