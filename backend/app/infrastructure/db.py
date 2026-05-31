"""Motor y sesión async de SQLAlchemy 2.x + asyncpg (ADR-02, ADR-05).

``get_session`` es la unidad de trabajo por request: hace commit si todo va
bien y rollback ante excepción. Los repositorios comparten esa sesión, de modo
que la inscripción, su auditoría y el job encolado se confirman atómicamente.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

# Convención de nombres estable para que Alembic genere constraints reproducibles.
_NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=_NAMING)


_settings = get_settings()

engine = create_async_engine(
    _settings.database_url,
    pool_size=10,            # ADR-05: pool de 10 conexiones
    max_overflow=20,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, autoflush=False, class_=AsyncSession
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependencia FastAPI: sesión transaccional por request (Unit of Work)."""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
