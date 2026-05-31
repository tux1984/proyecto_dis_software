"""Servicios de participación: ponentes, asistencia, evaluación y material.

Agrupa casos de uso de menor tamaño que comparten dependencias de repositorios
de soporte (RF-10/18/19/20/22). Cada clase mantiene una responsabilidad única.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.domain.errors import (
    AttendanceRequiredError,
    RegistrationRequiredError,
    ValidationError,
)
from app.domain.ports.queue import IJobQueue
from app.domain.ports.repositories import (
    IAuditLogRepository,
    IEnrollmentRepository,
    IEventRepository,
)
from app.domain.value_objects import RegistrationStatus
from app.infrastructure.repositories.support_repository import (
    AttendanceRepository,
    EvaluationRepository,
    SpeakerRepository,
)


class SpeakerService:
    """Invitación y gestión de ponentes (RF-10, RF-22)."""

    def __init__(
        self, speakers: SpeakerRepository, queue: IJobQueue, audit: IAuditLogRepository
    ) -> None:
        self._speakers = speakers
        self._queue = queue
        self._audit = audit

    async def invite(self, event_id: UUID, actor_id: UUID, email: str) -> dict:
        token = uuid4().hex
        await self._speakers.invite(event_id, email, token)
        await self._queue.enqueue(
            "send_email",
            {"kind": "speaker_invite", "to": email,
             "subject": "Invitación como ponente",
             "body": f"Has sido invitado como ponente. Token de un solo uso: {token}"},
        )
        await self._audit.append(
            actor_user_id=actor_id, action="speaker_invited",
            entity_type="event", entity_id=event_id,
        )
        return {"status": "invited", "invite_token": token}

    async def respond(
        self, token: str, accept: bool, bio: str | None = None, material_url: str | None = None
    ) -> dict:
        ok = await self._speakers.respond(token, accept, bio=bio, material_url=material_url)
        if not ok:
            # Token inexistente o ya usado (RF-10 -> 410 en el router)
            raise ValidationError("Token de invitación inválido o ya utilizado")
        return {"status": "confirmado" if accept else "declinado"}

    async def list_confirmed(self, event_id: UUID) -> list[dict]:
        return await self._speakers.list_confirmed(event_id)


class AttendanceService:
    """Registro de asistencia (RF-19, RN-05)."""

    def __init__(
        self,
        attendance: AttendanceRepository,
        enrollments: IEnrollmentRepository,
        audit: IAuditLogRepository,
    ) -> None:
        self._attendance = attendance
        self._enrollments = enrollments
        self._audit = audit

    async def record(
        self, event_id: UUID, actor_id: UUID, user_id: UUID, session_id: UUID | None = None
    ) -> dict:
        enrollment = await self._enrollments.get_by_event_user(event_id, user_id)
        if enrollment is None or enrollment.status != RegistrationStatus.CONFIRMADA:
            # RF-19: sin inscripción confirmada se rechaza (422)
            raise RegistrationRequiredError(
                "El usuario no tiene inscripción confirmada en el evento"
            )
        # Idempotente: si ya tiene asistencia, no reinsertar (evita violar el UNIQUE).
        if await self._attendance.has_attendance(event_id, user_id):
            return {"status": "already_recorded"}
        aid = await self._attendance.record(event_id, user_id, session_id)
        await self._audit.append(
            actor_user_id=actor_id, action="attendance_recorded",
            entity_type="attendance", entity_id=aid,
        )
        return {"status": "recorded", "attendance_id": str(aid)}


class EvaluationService:
    """Evaluación post-evento (RF-20)."""

    def __init__(
        self, evaluations: EvaluationRepository, attendance: AttendanceRepository
    ) -> None:
        self._evaluations = evaluations
        self._attendance = attendance

    async def submit(self, event_id: UUID, user_id: UUID, payload: dict) -> dict:
        if not await self._attendance.has_attendance(event_id, user_id):
            raise AttendanceRequiredError("Solo asistentes registrados pueden evaluar")
        eid = await self._evaluations.add(event_id, user_id, payload)
        return {"status": "submitted", "evaluation_id": str(eid)}


class MaterialService:
    """Acceso a material según inscripción confirmada (RF-18, RN-09)."""

    def __init__(
        self,
        enrollments: IEnrollmentRepository,
        events: IEventRepository,
        speakers: SpeakerRepository,
    ) -> None:
        self._enrollments = enrollments
        self._events = events
        self._speakers = speakers

    async def get_material(self, event_id: UUID, user_id: UUID) -> dict:
        event = await self._events.get(event_id)
        if event is None:
            raise ValidationError("Evento no encontrado")
        enrollment = await self._enrollments.get_by_event_user(event_id, user_id)
        confirmed = enrollment is not None and enrollment.status == RegistrationStatus.CONFIRMADA
        if not confirmed:
            # Con cualquier otro estado: solo información pública (RF-18)
            return {"access": "public", "title": event.title, "description": event.description}
        materials = await self._speakers.list_confirmed(event_id)
        return {
            "access": "full",
            "title": event.title,
            "description": event.description,
            "video_link": event.external_url,   # enlace solo para confirmados (RN-09)
            "materials": materials,
        }
