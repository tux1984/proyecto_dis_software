"""Repositorio de usuarios (RBAC, identidad)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import User
from app.infrastructure.models import UserModel
from app.infrastructure.repositories.mappers import to_user


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, user: User) -> None:
        self._s.add(
            UserModel(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=user.role.value,
                auth_provider=user.auth_provider,
                consent_accepted_at=user.consent_accepted_at,
                is_anonymized=user.is_anonymized,
            )
        )
        await self._s.flush()

    async def get(self, user_id: UUID) -> User | None:
        m = await self._s.get(UserModel, user_id)
        return to_user(m) if m else None

    async def get_by_email(self, email: str) -> User | None:
        res = await self._s.execute(select(UserModel).where(UserModel.email == email))
        m = res.scalar_one_or_none()
        return to_user(m) if m else None

    async def update(self, user: User) -> None:
        m = await self._s.get(UserModel, user.id)
        if m is None:
            return
        m.full_name = user.full_name
        m.email = user.email
        m.role = user.role.value
        m.consent_accepted_at = user.consent_accepted_at
        m.is_anonymized = user.is_anonymized
        await self._s.flush()

    async def set_role(self, user_id: UUID, role: str) -> None:
        m = await self._s.get(UserModel, user_id)
        if m is not None:
            m.role = role
            await self._s.flush()

    async def list_all(self) -> list[User]:
        res = await self._s.execute(select(UserModel).order_by(UserModel.created_at))
        return [to_user(m) for m in res.scalars().all()]
