"""AdminService — supervisión institucional (RF-24/25/26/29).

Dashboards institucionales, gestión de usuarios/roles (RBAC) y consulta de la
auditoría inmutable. Toda acción sensible queda registrada.
"""

from __future__ import annotations

from uuid import UUID

from app.domain.errors import ValidationError
from app.domain.ports.repositories import IAuditLogRepository, IUserRepository
from app.domain.value_objects import Role
from app.infrastructure.repositories.stats_repository import StatsRepository


class AdminService:
    def __init__(
        self,
        users: IUserRepository,
        audit: IAuditLogRepository,
        stats: StatsRepository,
    ) -> None:
        self._users = users
        self._audit = audit
        self._stats = stats

    async def institutional_dashboard(self) -> dict:
        return await self._stats.institutional_dashboard()

    async def event_dashboard(self, event_id: UUID) -> dict:
        return await self._stats.event_dashboard(event_id)

    async def list_pending_events(self) -> list[dict]:
        return await self._stats.list_events_by_status("pendiente")

    async def list_users(self) -> list[dict]:
        users = await self._users.list_all()
        return [
            {"id": str(u.id), "email": u.email, "full_name": u.full_name, "role": u.role.value}
            for u in users
        ]

    async def set_role(self, admin_id: UUID, target_user_id: UUID, role: str) -> dict:
        if role not in {r.value for r in Role}:
            raise ValidationError(f"Rol inválido: {role}")
        await self._users.set_role(target_user_id, role)
        await self._audit.append(
            actor_user_id=admin_id, action="role_changed",
            entity_type="user", entity_id=target_user_id,
        )
        return {"user_id": str(target_user_id), "role": role}

    async def query_audit(
        self, action: str | None = None, actor_user_id: UUID | None = None, limit: int = 100
    ) -> list[dict]:
        return await self._audit.query(action=action, actor_user_id=actor_user_id, limit=limit)

    async def pii_access_log(self, limit: int = 100) -> list[dict]:
        """Log de accesos a PII consultable por el administrador (RNF-10)."""
        return await self._audit.query(action="pii_access", limit=limit)
