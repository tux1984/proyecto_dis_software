"""Métricas Prometheus — RED + custom (RNF-02, SAD §10.2).

RED (Rate/Errors/Duration) se auto-instrumenta con
``prometheus-fastapi-instrumentator``. Las métricas de negocio se definen aquí
como singletons sobre el registro por defecto, de modo que aparecen en el mismo
endpoint ``/metrics`` que consume Prometheus.
"""

from __future__ import annotations

from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator, metrics

# Buckets RED requeridos por el SAD (§10.2).
_RED_BUCKETS = (0.05, 0.1, 0.5, 1.0, 2.0, 5.0)

# ---- Métricas de negocio / asíncronas ---------------------------------------
ENROLLMENT_QUEUE_SIZE = Gauge(
    "enrollment_queue_size",
    "Jobs pendientes en la cola interna (notificaciones + certificados)",
)
NOTIFICATION_SENT = Counter(
    "notification_sent_total",
    "Correos procesados por el worker",
    ["provider", "result"],
)
WEBHOOK_PROCESSED = Counter(
    "webhook_processed_total",
    "Webhooks de pasarela procesados",
    ["provider", "result"],
)
EMBEDDING_DURATION = Histogram(
    "embedding_generation_duration_seconds",
    "Latencia de generación de embeddings",
    ["provider"],
)
CERTIFICATE_DURATION = Histogram(
    "certificate_generation_duration_seconds",
    "Latencia de generación de certificados PDF",
)
EVENT_CAPACITY_AVAILABLE = Gauge(
    "event_capacity_available",
    "Cupos disponibles por evento",
    ["event_id"],
)
AUTH_EVENTS = Counter(
    "auth_events_total",
    "Eventos de autenticación",
    ["event", "result"],
)


def setup_red_metrics(app: FastAPI) -> None:
    """Instrumenta el ASGI con métricas RED y expone ``/metrics``.

    Produce:
        - ``http_requests_total{method,status,handler}``  (Rate + Errors)
        - ``http_request_duration_seconds_*{handler}``     (Duration, histograma)
    """
    instrumentator = Instrumentator(
        should_group_status_codes=False,       # status exacto (500/503) para SLO
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/health/live", "/health/ready"],
    )
    instrumentator.add(metrics.requests(metric_name="http_requests"))
    instrumentator.add(
        metrics.latency(
            metric_name="http_request_duration_seconds", buckets=_RED_BUCKETS
        )
    )
    instrumentator.instrument(app).expose(
        app, endpoint="/metrics", include_in_schema=False
    )
