"""Health checks (RNF-04, RNF-09).

* ``/health/live``: el proceso responde.
* ``/health/ready``: verifica dependencias (PostgreSQL, cola, adaptadores) y
  devuelve detalle por dependencia; 503 si alguna falla (detección <= 10s).
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.config import get_settings
from app.infrastructure.adapters.factory import AdapterFactory
from app.infrastructure.db import SessionLocal
from app.infrastructure.queue.postgres_queue import pending_count

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live() -> dict:
    return {"status": "alive"}


@router.get("/health/ready")
async def ready(response: Response) -> dict:
    checks: dict[str, str] = {}
    healthy = True

    # PostgreSQL + cola (misma sesión)
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
            checks["database"] = "ok"
            await pending_count(session)
            checks["queue"] = "ok"
    except Exception as exc:  # noqa: BLE001
        healthy = False
        checks["database"] = f"error: {type(exc).__name__}"
        checks["queue"] = "unknown"

    # Adaptadores (configuración resoluble)
    try:
        email = AdapterFactory().create_email()
        checks["email_adapter"] = email.provider_name
    except Exception as exc:  # noqa: BLE001
        healthy = False
        checks["email_adapter"] = f"error: {type(exc).__name__}"

    if not healthy:
        response.status_code = 503
    return {"status": "ready" if healthy else "degraded", "checks": checks,
            "env": get_settings().env}
