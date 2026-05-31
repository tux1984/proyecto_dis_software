"""Value Objects y enumeraciones del dominio (patrón Value Object, SAD §9.2).

Inmutables y auto-validados: encapsulan reglas y evitan el *stringly-typed*.
Las enumeraciones modelan los estados de las máquinas de estado (State).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from app.domain.errors import NoCapacityError, ValidationError

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---- Enumeraciones (estados y catálogos cerrados) ---------------------------
class Role(StrEnum):
    ORGANIZER = "organizer"
    ATTENDEE = "attendee"
    SPEAKER = "speaker"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class Modality(StrEnum):
    PRESENCIAL = "presencial"
    VIRTUAL = "virtual"
    HIBRIDO = "hibrido"


class EventStatus(StrEnum):
    """Ciclo de vida del evento (SAD Figura 16)."""

    BORRADOR = "borrador"
    PENDIENTE = "pendiente"      # pendiente_aprobación
    PUBLICADO = "publicado"
    CANCELADO = "cancelado"


class RegistrationStatus(StrEnum):
    """Estados de una inscripción (SAD Figura 8)."""

    PENDIENTE_PAGO = "pendiente_pago"
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"
    EXPIRADA = "expirada"


class SpeakerStatus(StrEnum):
    INVITADO = "invitado"
    CONFIRMADO = "confirmado"
    DECLINADO = "declinado"


class RegistrationType(StrEnum):
    GRATUITA = "gratuita"
    PAGA = "paga"


class CertificateType(StrEnum):
    ASISTENCIA = "asistencia"
    PONENCIA = "ponencia"
    ORGANIZACION = "organizacion"


class NotificationSegment(StrEnum):
    ALL = "all"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


# ---- Value Objects ricos ----------------------------------------------------
@dataclass(frozen=True, slots=True)
class EmailAddress:
    """Correo válido (Value Object inmutable y auto-validado)."""

    value: str

    def __post_init__(self) -> None:
        if not _EMAIL_RE.match(self.value):
            raise ValidationError(f"Correo inválido: {self.value!r}")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class CapacityCount:
    """Cupo de un evento: total vs confirmados (RN-01).

    Garantiza la invariante "sin sobreventa": ``confirmed <= total``.
    """

    total: int
    confirmed: int

    def __post_init__(self) -> None:
        if self.total <= 0:
            raise ValidationError("La capacidad debe ser > 0")
        if self.confirmed < 0:
            raise ValidationError("Confirmados no puede ser negativo")
        if self.confirmed > self.total:
            raise ValidationError("Sobreventa detectada: confirmed > total")

    @property
    def available(self) -> int:
        return self.total - self.confirmed

    @property
    def has_capacity(self) -> bool:
        return self.available > 0

    def reserve_one(self) -> CapacityCount:
        """Devuelve un nuevo cupo con un confirmado más; falla si no hay cupo."""
        if not self.has_capacity:
            raise NoCapacityError("Sin cupo disponible")
        return CapacityCount(total=self.total, confirmed=self.confirmed + 1)
