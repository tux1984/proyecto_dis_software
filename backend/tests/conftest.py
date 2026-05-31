"""Fixtures de pruebas (ADR-11).

Cliente HTTP en proceso (httpx + ASGITransport) contra el API real y la BD de
pruebas (PostgreSQL en contenedor). Un único event loop por sesión evita que el
pool de asyncpg (singleton de módulo) quede atado a un loop distinto.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.infrastructure.db import SessionLocal
from app.infrastructure.models import EventModel, UserModel
from app.infrastructure.security import create_access_token
from app.main import create_app


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def app():
    return create_app()


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def db():
    async with SessionLocal() as session:
        yield session


# ---- Factories ----
@pytest_asyncio.fixture
async def make_user(db):
    async def _make(role: str = "attendee", email: str | None = None) -> UserModel:
        user = UserModel(
            id=uuid.uuid4(),
            email=email or f"{uuid.uuid4().hex}@test.javeriana.edu.co",
            full_name="Usuario Prueba",
            role=role,
        )
        db.add(user)
        await db.commit()
        return user

    return _make


@pytest_asyncio.fixture
async def make_event(db):
    from datetime import datetime, timedelta, timezone

    async def _make(
        organizer_id: uuid.UUID,
        *,
        capacity: int = 100,
        status: str = "publicado",
        registration_type: str = "gratuita",
    ) -> EventModel:
        now = datetime.now(tz=timezone.utc)
        event = EventModel(
            id=uuid.uuid4(),
            title="Evento de prueba",
            description="Descripción de prueba",
            modality="virtual",
            starts_at=now + timedelta(days=5),
            ends_at=now + timedelta(days=5, hours=2),
            capacity=capacity,
            status=status,
            registration_type=registration_type,
            organizer_id=organizer_id,
            published_at=now if status == "publicado" else None,
        )
        db.add(event)
        await db.commit()
        return event

    return _make


def token_for(user: UserModel) -> str:
    return create_access_token(user.id, user.role, user.email)


def auth_header(user: UserModel) -> dict:
    return {"Authorization": f"Bearer {token_for(user)}"}
