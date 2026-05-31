"""Repositorios de soporte: categorías, ponentes, sesiones, asistencia,
evaluaciones y webhooks (idempotencia).

Agrupados por cohesión para no fragmentar en exceso el árbol; cada clase
mantiene una única responsabilidad (Repository).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models import (
    AttendanceRecordModel,
    CategoryModel,
    EvaluationModel,
    EventSessionModel,
    EventSpeakerModel,
    WebhookEventModel,
)


class CategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def create(self, name: str, faculty: str = "") -> UUID:
        cid = uuid4()
        self._s.add(CategoryModel(id=cid, name=name, faculty=faculty))
        await self._s.flush()
        return cid

    async def list_all(self) -> list[dict]:
        res = await self._s.execute(select(CategoryModel).order_by(CategoryModel.name))
        return [
            {"id": str(c.id), "name": c.name, "faculty": c.faculty}
            for c in res.scalars().all()
        ]


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add_session(
        self,
        *,
        event_id: UUID,
        title: str,
        starts_at: datetime,
        ends_at: datetime,
        track: str | None,
        speaker_id: UUID | None = None,
    ) -> UUID:
        sid = uuid4()
        self._s.add(
            EventSessionModel(
                id=sid,
                event_id=event_id,
                title=title,
                starts_at=starts_at,
                ends_at=ends_at,
                track=track,
                speaker_id=speaker_id,
            )
        )
        await self._s.flush()
        return sid

    async def overlaps_in_track(
        self, event_id: UUID, track: str | None, starts_at: datetime, ends_at: datetime
    ) -> bool:
        """Detecta solape de sesiones del mismo track (RF-09)."""
        if track is None:
            return False
        res = await self._s.execute(
            select(EventSessionModel).where(
                EventSessionModel.event_id == event_id,
                EventSessionModel.track == track,
                EventSessionModel.starts_at < ends_at,
                EventSessionModel.ends_at > starts_at,
            )
        )
        return res.first() is not None

    async def list_by_event(self, event_id: UUID) -> list[dict]:
        res = await self._s.execute(
            select(EventSessionModel)
            .where(EventSessionModel.event_id == event_id)
            .order_by(EventSessionModel.starts_at)
        )
        return [
            {
                "id": str(s.id),
                "title": s.title,
                "starts_at": s.starts_at.isoformat(),
                "ends_at": s.ends_at.isoformat(),
                "track": s.track,
            }
            for s in res.scalars().all()
        ]


class SpeakerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def invite(self, event_id: UUID, email: str, token: str) -> UUID:
        sid = uuid4()
        self._s.add(
            EventSpeakerModel(
                id=sid, event_id=event_id, email=email, status="invitado", invite_token=token
            )
        )
        await self._s.flush()
        return sid

    async def get_by_token(self, token: str) -> EventSpeakerModel | None:
        res = await self._s.execute(
            select(EventSpeakerModel).where(EventSpeakerModel.invite_token == token)
        )
        return res.scalar_one_or_none()

    async def respond(
        self, token: str, accept: bool, *, bio: str | None = None, material_url: str | None = None
    ) -> bool:
        m = await self.get_by_token(token)
        if m is None:
            return False
        m.status = "confirmado" if accept else "declinado"
        if bio is not None:
            m.bio = bio
        if material_url is not None:
            m.material_url = material_url
        m.invite_token = None  # token de un solo uso (RF-10)
        await self._s.flush()
        return True

    async def list_confirmed(self, event_id: UUID) -> list[dict]:
        res = await self._s.execute(
            select(EventSpeakerModel).where(
                EventSpeakerModel.event_id == event_id,
                EventSpeakerModel.status == "confirmado",
            )
        )
        return [
            {"email": s.email, "bio": s.bio, "material_url": s.material_url}
            for s in res.scalars().all()
        ]


class AttendanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def record(
        self, event_id: UUID, user_id: UUID, session_id: UUID | None = None, source: str = "manual"
    ) -> UUID:
        aid = uuid4()
        self._s.add(
            AttendanceRecordModel(
                id=aid, event_id=event_id, user_id=user_id, session_id=session_id, source=source
            )
        )
        await self._s.flush()
        return aid

    async def has_attendance(self, event_id: UUID, user_id: UUID) -> bool:
        res = await self._s.execute(
            select(AttendanceRecordModel.id).where(
                AttendanceRecordModel.event_id == event_id,
                AttendanceRecordModel.user_id == user_id,
            )
        )
        return res.first() is not None


class EvaluationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, event_id: UUID, user_id: UUID, payload: dict) -> UUID:
        eid = uuid4()
        self._s.add(
            EvaluationModel(id=eid, event_id=event_id, user_id=user_id, payload=payload)
        )
        await self._s.flush()
        return eid


class WebhookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def is_processed(self, idempotency_key: str) -> bool:
        res = await self._s.execute(
            select(WebhookEventModel.id).where(
                WebhookEventModel.idempotency_key == idempotency_key
            )
        )
        return res.first() is not None

    async def record(
        self, provider: str, idempotency_key: str, payload: dict, enrollment_id: UUID | None
    ) -> None:
        self._s.add(
            WebhookEventModel(
                provider=provider,
                idempotency_key=idempotency_key,
                payload=payload,
                related_enrollment_id=enrollment_id,
            )
        )
        await self._s.flush()
