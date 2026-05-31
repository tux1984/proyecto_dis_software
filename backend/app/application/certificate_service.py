"""CertificateService — emisión y verificación de certificados (RF-13/21, RN-05).

El código único se genera de forma síncrona; el render del PDF se realiza en el
``worker`` (job ``generate_certificate``) para no bloquear la petición.
Un certificado de asistencia solo se emite si existe asistencia confirmada.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.domain.errors import AttendanceRequiredError, ValidationError
from app.domain.ports.queue import IJobQueue
from app.domain.ports.repositories import IAuditLogRepository, IEnrollmentRepository
from app.domain.value_objects import CertificateType, RegistrationStatus
from app.infrastructure.repositories.certificate_repository import CertificateRepository
from app.infrastructure.repositories.support_repository import AttendanceRepository


class CertificateService:
    def __init__(
        self,
        certificates: CertificateRepository,
        attendance: AttendanceRepository,
        enrollments: IEnrollmentRepository,
        queue: IJobQueue,
        audit: IAuditLogRepository,
    ) -> None:
        self._certs = certificates
        self._attendance = attendance
        self._enrollments = enrollments
        self._queue = queue
        self._audit = audit

    async def request_certificate(
        self, user_id: UUID, event_id: UUID, cert_type: str = "asistencia"
    ) -> dict:
        if cert_type == CertificateType.ASISTENCIA.value:
            enrollment = await self._enrollments.get_by_event_user(event_id, user_id)
            confirmed = (
                enrollment is not None
                and enrollment.status == RegistrationStatus.CONFIRMADA
            )
            attended = await self._attendance.has_attendance(event_id, user_id)
            if not (confirmed and attended):
                # RN-05: sin asistencia confirmada no hay certificado (-> 403)
                raise AttendanceRequiredError(
                    "Se requiere inscripción confirmada y asistencia registrada"
                )

        existing = await self._certs.get_for(user_id, event_id, cert_type)
        if existing is not None:
            return {**existing, "status": "ready" if existing["pdf_url"] else "generating"}

        code = uuid4().hex
        cert_id = await self._certs.create(
            user_id=user_id, event_id=event_id, cert_type=cert_type, verification_code=code,
        )
        await self._queue.enqueue(
            "generate_certificate",
            {"cert_id": str(cert_id), "verification_code": code,
             "user_id": str(user_id), "event_id": str(event_id), "cert_type": cert_type},
        )
        await self._audit.append(
            actor_user_id=user_id, action="certificate_requested",
            entity_type="certificate", entity_id=cert_id,
        )
        return {"verification_code": code, "status": "generating"}

    async def generate_batch(
        self, event_id: UUID, actor_id: UUID, cert_type: str = "asistencia"
    ) -> dict:
        """Genera certificados para todos los asistentes elegibles (RF-13)."""
        confirmed = await self._enrollments.list_by_event(
            event_id, RegistrationStatus.CONFIRMADA
        )
        issued = 0
        for enrollment in confirmed:
            attended = await self._attendance.has_attendance(event_id, enrollment.user_id)
            already = await self._certs.exists(enrollment.user_id, event_id, cert_type)
            if attended and not already:
                code = uuid4().hex
                cert_id = await self._certs.create(
                    user_id=enrollment.user_id, event_id=event_id,
                    cert_type=cert_type, verification_code=code,
                    enrollment_id=enrollment.id,
                )
                await self._queue.enqueue(
                    "generate_certificate",
                    {"cert_id": str(cert_id), "verification_code": code,
                     "user_id": str(enrollment.user_id), "event_id": str(event_id),
                     "cert_type": cert_type},
                )
                issued += 1
        await self._audit.append(
            actor_user_id=actor_id, action="certificate_batch",
            entity_type="event", entity_id=event_id,
        )
        return {"issued": issued, "status": "queued"}

    async def verify(self, code: str) -> dict:
        info = await self._certs.get_by_code(code)
        if info is None:
            raise ValidationError("Código de certificado no válido")
        return info

    async def list_mine(self, user_id: UUID) -> list[dict]:
        return await self._certs.list_by_user(user_id)
