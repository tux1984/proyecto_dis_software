"""Trazas distribuidas con OpenTelemetry (RNF-03, ADR-04).

Inicializa el ``TracerProvider`` con export OTLP a Tempo, auto-instrumenta
FastAPI y asyncpg, y propaga el contexto W3C (``traceparent``). Expone un
``tracer`` para crear spans manuales en operaciones de negocio
(``enrollment.reserve_capacity``, ``search.semantic_query``, …).
"""

from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import get_settings

logger = logging.getLogger(__name__)
_initialized = False


def init_tracing(app: object = None) -> None:
    """Configura trazas OTel. Idempotente; no-op si ``OTEL_ENABLED=false``."""
    global _initialized
    settings = get_settings()
    if _initialized or not settings.otel_enabled:
        return

    resource = Resource.create(
        {"service.name": settings.service_name, "deployment.environment": settings.env}
    )
    provider = TracerProvider(resource=resource)

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_endpoint, insecure=True
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
    except Exception as exc:  # exportador no disponible no debe tumbar el API
        logger.warning("OTLP exporter no inicializado: %s", exc)

    trace.set_tracer_provider(provider)

    # Auto-instrumentación de la BD: las consultas asyncpg quedan como spans
    # hijos del span SERVER creado por OTelMiddleware (mismo trace_id).
    # El span HTTP lo crea nuestro middleware ASGI (evita el conflicto de
    # BaseHTTPMiddleware con la propagación de contexto de OTel).
    try:
        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

        AsyncPGInstrumentor().instrument()
    except Exception as exc:
        logger.warning("AsyncPG instrumentation falló: %s", exc)

    _initialized = True


def get_tracer(name: str = "pgea") -> trace.Tracer:
    """Devuelve un tracer para crear spans manuales de negocio."""
    return trace.get_tracer(name)
