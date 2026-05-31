"""Entidades y agregados del dominio (SAD §6.1.3, Figura 8).

Objetos con identidad y comportamiento. Las transiciones de estado se modelan
con el patrón **State**: cada método valida la transición contra una tabla de
transiciones permitidas y lanza ``InvalidStateTransitionError`` si no es válida.
Esto evita ``if/elif`` dispersos y hace verificable la máquina de estados.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.errors import InvalidStateTransitionError, ValidationError
from app.domain.value_objects import (
    EventStatus,
    Modality,
    RegistrationStatus,
    RegistrationType,
    Role,
)


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _ensure(current, target, allowed: dict) -> None:
    if target not in allowed.get(current, set()):
        raise InvalidStateTransitionError(
            f"Transición no permitida: {current} -> {target}"
        )


# ---- Usuario ----------------------------------------------------------------
@dataclass
class User:
    id: UUID
    email: str
    full_name: str
    role: Role
    auth_provider: str = "mock"
    consent_accepted_at: datetime | None = None
    is_anonymized: bool = False
    created_at: datetime = field(default_factory=_now)

    def anonymize(self) -> None:
        """Anonimiza PII conservando trazabilidad (RN-07, Ley 1581)."""
        self.full_name = "ANONIMIZADO"
        self.email = f"anon+{self.id}@pgea.invalid"
        self.is_anonymized = True


# ---- Evento (State) ---------------------------------------------------------
_EVENT_TRANSITIONS: dict[EventStatus, set[EventStatus]] = {
    EventStatus.BORRADOR: {EventStatus.PENDIENTE, EventStatus.PUBLICADO, EventStatus.CANCELADO},
    EventStatus.PENDIENTE: {EventStatus.PUBLICADO, EventStatus.BORRADOR, EventStatus.CANCELADO},
    EventStatus.PUBLICADO: {EventStatus.CANCELADO},
    EventStatus.CANCELADO: set(),
}


@dataclass
class Event:
    id: UUID
    title: str
    description: str
    modality: Modality
    starts_at: datetime
    ends_at: datetime
    capacity: int
    organizer_id: UUID
    status: EventStatus = EventStatus.BORRADOR
    registration_type: RegistrationType = RegistrationType.GRATUITA
    location: str | None = None
    external_url: str | None = None
    category_id: UUID | None = None
    created_at: datetime = field(default_factory=_now)
    published_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.ends_at <= self.starts_at:
            raise ValidationError("La fecha de fin debe ser posterior a la de inicio")
        if self.capacity <= 0:
            raise ValidationError("La capacidad debe ser > 0")

    # -- transiciones de estado --
    def submit_for_approval(self) -> None:
        _ensure(self.status, EventStatus.PENDIENTE, _EVENT_TRANSITIONS)
        self.status = EventStatus.PENDIENTE

    def approve(self) -> None:
        _ensure(self.status, EventStatus.PUBLICADO, _EVENT_TRANSITIONS)
        self.status = EventStatus.PUBLICADO
        self.published_at = _now()

    def reject(self) -> None:
        _ensure(self.status, EventStatus.BORRADOR, _EVENT_TRANSITIONS)
        self.status = EventStatus.BORRADOR

    def publish(self) -> None:
        _ensure(self.status, EventStatus.PUBLICADO, _EVENT_TRANSITIONS)
        self.status = EventStatus.PUBLICADO
        self.published_at = _now()

    def cancel(self) -> None:
        _ensure(self.status, EventStatus.CANCELADO, _EVENT_TRANSITIONS)
        self.status = EventStatus.CANCELADO

    @property
    def is_visible(self) -> bool:
        """Solo eventos publicados son visibles en el catálogo (RN-03)."""
        return self.status == EventStatus.PUBLICADO

    @property
    def is_paid(self) -> bool:
        return self.registration_type == RegistrationType.PAGA


# ---- Inscripción (State) ----------------------------------------------------
_ENROLLMENT_TRANSITIONS: dict[RegistrationStatus, set[RegistrationStatus]] = {
    RegistrationStatus.PENDIENTE_PAGO: {
        RegistrationStatus.CONFIRMADA,
        RegistrationStatus.EXPIRADA,
        RegistrationStatus.CANCELADA,
    },
    RegistrationStatus.CONFIRMADA: {RegistrationStatus.CANCELADA},
    RegistrationStatus.CANCELADA: set(),
    RegistrationStatus.EXPIRADA: set(),
}


@dataclass
class Enrollment:
    id: UUID
    event_id: UUID
    user_id: UUID
    status: RegistrationStatus
    payment_reference: str | None = None
    form_data: dict | None = None
    registered_at: datetime = field(default_factory=_now)
    confirmed_at: datetime | None = None
    cancelled_at: datetime | None = None
    reserved_until: datetime | None = None

    # -- fábricas --
    @classmethod
    def new_free(cls, event_id: UUID, user_id: UUID, form_data: dict | None = None) -> Enrollment:
        """Inscripción gratuita: nace CONFIRMADA (RF-03, RN-01)."""
        return cls(
            id=uuid4(),
            event_id=event_id,
            user_id=user_id,
            status=RegistrationStatus.CONFIRMADA,
            form_data=form_data,
            confirmed_at=_now(),
        )

    @classmethod
    def new_pending_payment(
        cls,
        event_id: UUID,
        user_id: UUID,
        reserved_until: datetime,
        form_data: dict | None = None,
    ) -> Enrollment:
        """Inscripción paga: reserva el cupo en PENDIENTE_PAGO (RF-04, RN-06)."""
        return cls(
            id=uuid4(),
            event_id=event_id,
            user_id=user_id,
            status=RegistrationStatus.PENDIENTE_PAGO,
            reserved_until=reserved_until,
            form_data=form_data,
        )

    # -- transiciones --
    def confirm(self, payment_reference: str | None = None) -> None:
        _ensure(self.status, RegistrationStatus.CONFIRMADA, _ENROLLMENT_TRANSITIONS)
        self.status = RegistrationStatus.CONFIRMADA
        self.confirmed_at = _now()
        if payment_reference:
            self.payment_reference = payment_reference

    def expire(self) -> None:
        _ensure(self.status, RegistrationStatus.EXPIRADA, _ENROLLMENT_TRANSITIONS)
        self.status = RegistrationStatus.EXPIRADA

    def cancel(self) -> None:
        _ensure(self.status, RegistrationStatus.CANCELADA, _ENROLLMENT_TRANSITIONS)
        self.status = RegistrationStatus.CANCELADA
        self.cancelled_at = _now()

    @property
    def is_confirmed(self) -> bool:
        return self.status == RegistrationStatus.CONFIRMADA
