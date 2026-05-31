"""Errores de dominio (SAD §10.4, Figura 8).

Se mapean a códigos HTTP específicos vía ``exception_handlers`` de FastAPI; el
dominio no conoce HTTP. Cada error representa la violación de una regla de
negocio (RN-xx), no un fallo técnico.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base de todos los errores de dominio."""

    code: str = "domain_error"


class NoCapacityError(DomainError):
    """No hay cupo disponible al confirmar la inscripción (RN-01, RNF-08)."""

    code = "no_capacity"


class DuplicateRegistrationError(DomainError):
    """El usuario ya tiene una inscripción para el evento (RF-03)."""

    code = "duplicate_registration"


class InvalidStateTransitionError(DomainError):
    """Transición de estado no permitida en la máquina de estados (State)."""

    code = "invalid_state_transition"


class PaymentTimeoutError(DomainError):
    """La reserva de pago expiró sin confirmación (RN-06)."""

    code = "payment_timeout"


class CancellationPolicyError(DomainError):
    """La cancelación viola la política del evento / fuera de plazo (RN-02)."""

    code = "cancellation_not_allowed"


class AttendanceRequiredError(DomainError):
    """No se puede emitir certificado sin asistencia confirmada (RN-05)."""

    code = "attendance_required"


class ValidationError(DomainError):
    """Invariante de value object o entidad violada."""

    code = "validation_error"


class RegistrationRequiredError(DomainError):
    """Acción que exige inscripción confirmada previa (RF-19 -> 422)."""

    code = "registration_required"
