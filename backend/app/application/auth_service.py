"""AuthService — autenticación SSO delegada + JWT propio (RF-28, ADR-06).

Valida el ``id_token`` del proveedor (mock o Google) a través del adaptador,
hace upsert del usuario institucional y emite un JWT propio. No almacena
contraseñas locales (RNF-11).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.entities import User
from app.domain.ports.adapters import IOAuthAdapter
from app.domain.ports.repositories import IAuditLogRepository, IUserRepository
from app.domain.value_objects import Role
from app.infrastructure.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.observability.metrics import AUTH_EVENTS

logger = logging.getLogger("pgea.auth")


class AuthService:
    def __init__(
        self,
        users: IUserRepository,
        oauth: IOAuthAdapter,
        audit: IAuditLogRepository,
    ) -> None:
        self._users = users
        self._oauth = oauth
        self._audit = audit

    async def login(self, id_token: str) -> dict:
        try:
            identity = await self._oauth.verify_id_token(id_token)
        except Exception as exc:
            AUTH_EVENTS.labels(event="login", result="failure").inc()
            logger.warning("Login fallido: %s", exc)
            raise TokenError("id_token inválido") from exc

        user = await self._users.get_by_email(identity.email)
        if user is None:
            # Primer acceso: se crea con rol attendee y consentimiento (RN-07).
            user = User(
                id=uuid4(),
                email=identity.email,
                full_name=identity.full_name,
                role=Role.ATTENDEE,
                auth_provider=identity.provider,
                consent_accepted_at=datetime.now(tz=UTC),
            )
            await self._users.add(user)
            await self._audit.append(
                actor_user_id=user.id,
                action="user_created",
                entity_type="user",
                entity_id=user.id,
                result="success",
            )

        await self._audit.append(
            actor_user_id=user.id,
            action="login",
            entity_type="user",
            entity_id=user.id,
            result="success",
        )
        AUTH_EVENTS.labels(event="login", result="success").inc()
        return self._tokens_for(user)

    async def refresh(self, refresh_token: str) -> dict:
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise TokenError("tipo de token inválido")
        except TokenError:
            AUTH_EVENTS.labels(event="refresh", result="failure").inc()
            raise
        user = await self._users.get(UUID(payload["sub"]))
        if user is None:
            raise TokenError("usuario no encontrado")
        AUTH_EVENTS.labels(event="refresh", result="success").inc()
        return self._tokens_for(user)

    def _tokens_for(self, user: User) -> dict:
        return {
            "access_token": create_access_token(user.id, user.role.value, user.email),
            "refresh_token": create_refresh_token(user.id),
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value,
            },
        }
