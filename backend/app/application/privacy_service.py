"""PrivacyService — cumplimiento operacional de la Ley 1581 (RNF-10, RN-07).

Consulta de datos personales, supresión por anonimización (conservando
trazabilidad de auditoría) y registro de cada acceso a PII en el log de
auditoría con ``trace_id``.
"""

from __future__ import annotations

from uuid import UUID

from app.domain.errors import ValidationError
from app.domain.ports.repositories import (
    IAuditLogRepository,
    IEnrollmentRepository,
    IUserRepository,
)


class PrivacyService:
    def __init__(
        self,
        users: IUserRepository,
        enrollments: IEnrollmentRepository,
        audit: IAuditLogRepository,
    ) -> None:
        self._users = users
        self._enrollments = enrollments
        self._audit = audit

    async def get_my_data(self, user_id: UUID) -> dict:
        user = await self._users.get(user_id)
        if user is None:
            raise ValidationError("Usuario no encontrado")
        enrollments = await self._enrollments.list_by_user(user_id)
        # Cada acceso a PII queda auditado (RN-07 d).
        await self._audit.append(
            actor_user_id=user_id, action="pii_access",
            entity_type="user", entity_id=user_id,
        )
        return {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "consent_accepted_at": user.consent_accepted_at.isoformat()
            if user.consent_accepted_at else None,
            "enrollments": [
                {"event_id": str(e.event_id), "status": e.status.value} for e in enrollments
            ],
        }

    async def delete_my_data(self, user_id: UUID) -> dict:
        """Supresión: anonimiza la PII manteniendo la trazabilidad (RN-07 c)."""
        user = await self._users.get(user_id)
        if user is None:
            raise ValidationError("Usuario no encontrado")
        user.anonymize()
        await self._users.update(user)
        await self._audit.append(
            actor_user_id=user_id, action="pii_suppression",
            entity_type="user", entity_id=user_id,
        )
        return {"status": "anonymized", "user_id": str(user_id)}
