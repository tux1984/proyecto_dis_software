"""Eventos de dominio para el patrón Observer (SAD §9.2, tabla GoF).

Al confirmar una inscripción ocurren varios efectos desacoplados (correo,
métrica de cupo, auditoría). El servicio emisor publica un evento y no conoce a
sus observadores: cada *handler* implementa ``IEnrollmentEventHandler``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DomainEvent:
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class EnrollmentConfirmed(DomainEvent):
    enrollment_id: UUID
    event_id: UUID
    user_id: UUID
    paid: bool

    @classmethod
    def now(cls, enrollment_id: UUID, event_id: UUID, user_id: UUID, paid: bool):
        return cls(
            occurred_at=datetime.now(tz=UTC),
            enrollment_id=enrollment_id,
            event_id=event_id,
            user_id=user_id,
            paid=paid,
        )


@dataclass(frozen=True, slots=True)
class EnrollmentCancelled(DomainEvent):
    enrollment_id: UUID
    event_id: UUID
    user_id: UUID

    @classmethod
    def now(cls, enrollment_id: UUID, event_id: UUID, user_id: UUID):
        return cls(
            occurred_at=datetime.now(tz=UTC),
            enrollment_id=enrollment_id,
            event_id=event_id,
            user_id=user_id,
        )
