"""Punto de entrada del API (ADR-01, ADR-02).

Inicializa la observabilidad antes que la lógica (RN-10), monta el middleware
transversal y registra los routers. El orden de middleware garantiza que el
span OTel esté activo cuando el ``OTelMiddleware`` lee el ``trace_id``.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.interface.exception_handlers import register_exception_handlers
from app.interface.routers import (
    admin,
    auth,
    certificates,
    engagement,
    enrollments,
    events,
    health,
    meta,
    notifications,
    privacy,
    search,
)
from app.observability.logging_config import configure_logging
from app.observability.metrics import setup_red_metrics
from app.observability.middleware import OTelMiddleware
from app.observability.otel import init_tracing


def create_app() -> FastAPI:
    configure_logging()
    # Inicializa el TracerProvider antes de servir: deja disponible el provider
    # para los tracers (proxy) y auto-instrumenta asyncpg (RN-10, RI-04).
    init_tracing()
    settings = get_settings()

    app = FastAPI(
        title="PGEA — Plataforma de Gestión de Eventos Académicos",
        version="1.0.0",
        description=(
            "POC funcional. Monolito modular + Clean Architecture + Hexagonal "
            "Ports & Adapters. Observabilidad transversal (OpenTelemetry + "
            "Prometheus + Grafana + Loki + Tempo)."
        ),
    )

    register_exception_handlers(app)

    # Routers (Controllers)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(search.router)
    app.include_router(meta.router)
    app.include_router(events.router)
    app.include_router(enrollments.router)
    app.include_router(notifications.router)
    app.include_router(certificates.router)
    app.include_router(engagement.router)
    app.include_router(admin.router)
    app.include_router(privacy.router)

    # CORS solo fuera de producción (en prod, Nginx sirve mismo origen).
    if settings.env != "prod":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Trace-Id"],
        )

    # Métricas RED (instrumentator) y, por último, el OTelMiddleware: al añadirse
    # de último queda como el más externo y crea el span raíz que envuelve a
    # todo el procesamiento (métricas incluidas) — trace_id disponible en todo.
    setup_red_metrics(app)
    app.add_middleware(OTelMiddleware)

    @app.get("/", tags=["meta"])
    async def root() -> dict:
        return {
            "service": settings.service_name,
            "version": "1.0.0",
            "env": settings.env,
            "docs": "/docs",
        }

    return app


app = create_app()
