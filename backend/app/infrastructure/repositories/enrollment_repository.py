"""Repositorio de inscripciones — control atómico de cupos (ADR-05).

``reserve_capacity_and_create`` es la operación más crítica del sistema
(RN-01, RNF-08). Serializa la verificación y reserva del cupo mediante
``SELECT … FOR NO KEY UPDATE`` sobre la fila del evento dentro de la
transacción del request, garantizando "sin sobreventa" bajo concurrencia.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import Enrollment, Event
from app.domain.errors import DuplicateRegistrationError, NoCapacityError
from app.domain.value_objects import RegistrationStatus
from app.infrastructure.models import EnrollmentModel
from app.infrastructure.repositories.mappers import to_enrollment


def _now() -> datetime:
    return datetime.now(tz=UTC)


class EnrollmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def reserve_capacity_and_create(
        self,
        event: Event,
        user_id: UUID,
        *,
        paid: bool,
        reserved_until: datetime | None,
        form_data: dict | None,
    ) -> Enrollment:
        # 0) Evita deadlocks indefinidos (SAD §6.2.2)
        await self._s.execute(text("SET LOCAL statement_timeout = 5000"))

        # 1) Bloqueo pesimista de la fila del evento (no bloquea lectores: MVCC)
        await self._s.execute(
            text("SELECT 1 FROM events WHERE id = :id FOR NO KEY UPDATE"),
            {"id": str(event.id)},
        )

        # 2) ¿Inscripción existente para (event, user)?  (UNIQUE event_id,user_id)
        existing = await self._model_by_event_user(event.id, user_id)
        if existing is not None:
            active = existing.status == RegistrationStatus.CONFIRMADA.value or (
                existing.status == RegistrationStatus.PENDIENTE_PAGO.value
                and existing.reserved_until is not None
                and existing.reserved_until > _now()
            )
            if active:
                raise DuplicateRegistrationError(
                    "El usuario ya está inscrito en el evento"
                )

        # 3) Conteo de cupos ocupados: confirmadas + reservas activas (RN-01, RN-06)
        occupied = await self._count_occupied(event.id)
        if occupied >= event.capacity:
            raise NoCapacityError("Sin cupo disponible")

        # 4) Construir la entidad de dominio según el tipo de inscripción
        if paid:
            assert reserved_until is not None
            enrollment = Enrollment.new_pending_payment(
                event.id, user_id, reserved_until, form_data
            )
        else:
            enrollment = Enrollment.new_free(event.id, user_id, form_data)

        # 5) Persistir (reutiliza la fila si existía cancelada/expirada)
        if existing is not None:
            existing.status = enrollment.status.value
            existing.registered_at = enrollment.registered_at
            existing.confirmed_at = enrollment.confirmed_at
            existing.cancelled_at = None
            existing.reserved_until = enrollment.reserved_until
            existing.payment_reference = None
            existing.form_data = form_data
            enrollment.id = existing.id
        else:
            self._s.add(
                EnrollmentModel(
                    id=enrollment.id,
                    event_id=enrollment.event_id,
                    user_id=enrollment.user_id,
                    status=enrollment.status.value,
                    form_data=form_data,
                    registered_at=enrollment.registered_at,
                    confirmed_at=enrollment.confirmed_at,
                    reserved_until=enrollment.reserved_until,
                )
            )
        await self._s.flush()
        return enrollment

    async def _count_occupied(self, event_id: UUID) -> int:
        res = await self._s.execute(
            select(func.count())
            .select_from(EnrollmentModel)
            .where(
                EnrollmentModel.event_id == event_id,
                or_(
                    EnrollmentModel.status == RegistrationStatus.CONFIRMADA.value,
                    (EnrollmentModel.status == RegistrationStatus.PENDIENTE_PAGO.value)
                    & (EnrollmentModel.reserved_until > _now()),
                ),
            )
        )
        return int(res.scalar_one())

    async def _model_by_event_user(
        self, event_id: UUID, user_id: UUID
    ) -> EnrollmentModel | None:
        res = await self._s.execute(
            select(EnrollmentModel).where(
                EnrollmentModel.event_id == event_id,
                EnrollmentModel.user_id == user_id,
            )
        )
        return res.scalar_one_or_none()

    async def get(self, enrollment_id: UUID) -> Enrollment | None:
        m = await self._s.get(EnrollmentModel, enrollment_id)
        return to_enrollment(m) if m else None

    async def get_by_event_user(
        self, event_id: UUID, user_id: UUID
    ) -> Enrollment | None:
        m = await self._model_by_event_user(event_id, user_id)
        return to_enrollment(m) if m else None

    async def update(self, enrollment: Enrollment) -> None:
        m = await self._s.get(EnrollmentModel, enrollment.id)
        if m is None:
            return
        m.status = enrollment.status.value
        m.payment_reference = enrollment.payment_reference
        m.confirmed_at = enrollment.confirmed_at
        m.cancelled_at = enrollment.cancelled_at
        m.reserved_until = enrollment.reserved_until
        await self._s.flush()

    async def list_by_event(
        self, event_id: UUID, status: RegistrationStatus | None = None
    ) -> list[Enrollment]:
        stmt = select(EnrollmentModel).where(EnrollmentModel.event_id == event_id)
        if status:
            stmt = stmt.where(EnrollmentModel.status == status.value)
        res = await self._s.execute(stmt.order_by(EnrollmentModel.registered_at))
        return [to_enrollment(m) for m in res.scalars().all()]

    async def list_by_user(self, user_id: UUID) -> list[Enrollment]:
        res = await self._s.execute(
            select(EnrollmentModel)
            .where(EnrollmentModel.user_id == user_id)
            .order_by(EnrollmentModel.registered_at.desc())
        )
        return [to_enrollment(m) for m in res.scalars().all()]

    async def list_by_user_with_events(self, user_id: UUID) -> list[dict]:
        """Inscripciones del usuario con datos del evento (vista 'Mis inscripciones')."""
        from app.infrastructure.models import EventModel  # import local: evita ciclos

        res = await self._s.execute(
            select(EnrollmentModel, EventModel)
            .join(EventModel, EnrollmentModel.event_id == EventModel.id)
            .where(EnrollmentModel.user_id == user_id)
            .order_by(EnrollmentModel.registered_at.desc())
        )
        return [
            {
                "id": str(e.id),
                "event_id": str(e.event_id),
                "event_title": ev.title,
                "event_starts_at": ev.starts_at.isoformat() if ev.starts_at else None,
                "modality": ev.modality,
                "status": e.status,
                "registered_at": e.registered_at.isoformat() if e.registered_at else None,
            }
            for e, ev in res.all()
        ]

    async def list_with_users(
        self, event_id: UUID, search: str | None = None
    ) -> list[dict]:
        """Inscritos con datos de usuario para el organizador y CSV (RF-11)."""
        from app.infrastructure.models import UserModel  # import local: evita ciclos

        stmt = (
            select(EnrollmentModel, UserModel)
            .join(UserModel, EnrollmentModel.user_id == UserModel.id)
            .where(EnrollmentModel.event_id == event_id)
        )
        if search:
            like = f"%{search.lower()}%"
            stmt = stmt.where(
                func.lower(UserModel.full_name).like(like)
                | func.lower(UserModel.email).like(like)
            )
        res = await self._s.execute(stmt.order_by(EnrollmentModel.registered_at))
        return [
            {
                "enrollment_id": str(e.id),
                "user_id": str(u.id),
                "full_name": u.full_name,
                "email": u.email,
                "status": e.status,
                "registered_at": e.registered_at.isoformat() if e.registered_at else "",
                "form_data": e.form_data or {},
            }
            for e, u in res.all()
        ]

    async def list_expired_pending(self, now: datetime) -> list[Enrollment]:
        res = await self._s.execute(
            select(EnrollmentModel).where(
                EnrollmentModel.status == RegistrationStatus.PENDIENTE_PAGO.value,
                EnrollmentModel.reserved_until < now,
            )
        )
        return [to_enrollment(m) for m in res.scalars().all()]
