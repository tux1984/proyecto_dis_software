"""Conversión entre modelos ORM e entidades de dominio.

Mantiene el dominio libre de SQLAlchemy: los repositorios devuelven entidades
puras y persisten desde ellas.
"""

from __future__ import annotations

from app.domain.entities import Enrollment, Event, User
from app.domain.value_objects import (
    EventStatus,
    Modality,
    RegistrationStatus,
    RegistrationType,
    Role,
)
from app.infrastructure.models import EnrollmentModel, EventModel, UserModel


def to_user(m: UserModel) -> User:
    return User(
        id=m.id,
        email=m.email,
        full_name=m.full_name,
        role=Role(m.role),
        auth_provider=m.auth_provider,
        consent_accepted_at=m.consent_accepted_at,
        is_anonymized=m.is_anonymized,
        created_at=m.created_at,
    )


def to_event(m: EventModel) -> Event:
    return Event(
        id=m.id,
        title=m.title,
        description=m.description,
        modality=Modality(m.modality),
        starts_at=m.starts_at,
        ends_at=m.ends_at,
        capacity=m.capacity,
        organizer_id=m.organizer_id,
        status=EventStatus(m.status),
        registration_type=RegistrationType(m.registration_type),
        location=m.location,
        external_url=m.external_url,
        category_id=m.category_id,
        created_at=m.created_at,
        published_at=m.published_at,
    )


def to_enrollment(m: EnrollmentModel) -> Enrollment:
    return Enrollment(
        id=m.id,
        event_id=m.event_id,
        user_id=m.user_id,
        status=RegistrationStatus(m.status),
        payment_reference=m.payment_reference,
        form_data=m.form_data,
        registered_at=m.registered_at,
        confirmed_at=m.confirmed_at,
        cancelled_at=m.cancelled_at,
        reserved_until=m.reserved_until,
    )
