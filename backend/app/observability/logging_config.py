"""Logging estructurado JSON con correlación de trazas y push a Loki (RNF-01).

Campos obligatorios del log (SAD §10.2):
    timestamp (ISO 8601 UTC), level, service, trace_id, span_id, route, method,
    status, duration_ms, user_id, message.

El ``trace_id``/``span_id`` se inyectan automáticamente desde el contexto OTel
activo, de modo que cualquier log emitido dentro de un request queda
correlacionado sin que el código de negocio tenga que pasarlos (Decorator/CCC).
"""

from __future__ import annotations

import atexit
import contextlib
import logging
import queue
import threading
import time
from datetime import UTC, datetime

import httpx
from opentelemetry import trace
from pythonjsonlogger import jsonlogger

from app.config import get_settings


class TraceContextFilter(logging.Filter):
    """Inyecta ``trace_id`` y ``span_id`` del span OTel activo en cada record."""

    def filter(self, record: logging.LogRecord) -> bool:
        span = trace.get_current_span()
        ctx = span.get_span_context() if span else None
        if ctx and ctx.is_valid:
            record.trace_id = format(ctx.trace_id, "032x")
            record.span_id = format(ctx.span_id, "016x")
        else:
            record.trace_id = getattr(record, "trace_id", None)
            record.span_id = getattr(record, "span_id", None)
        return True


class PgeaJsonFormatter(jsonlogger.JsonFormatter):
    """Formatter JSON que garantiza los campos obligatorios y timestamp UTC."""

    def __init__(self, service: str, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.service = service

    def add_fields(self, log_record, record, message_dict) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = datetime.fromtimestamp(
            record.created, tz=UTC
        ).isoformat()
        log_record["level"] = record.levelname
        log_record["service"] = self.service
        log_record.setdefault("trace_id", getattr(record, "trace_id", None))
        log_record.setdefault("span_id", getattr(record, "span_id", None))
        log_record["logger"] = record.name


class LokiHandler(logging.Handler):
    """Handler que empuja logs JSON a Loki vía HTTP de forma no bloqueante.

    Usa una cola en memoria y un hilo de fondo; si el request del usuario emite
    un log, el envío a Loki no bloquea su respuesta (RNF-01, RN-08 en espíritu).
    Etiquetas de baja cardinalidad (service, level, env); el resto va en la línea.
    """

    def __init__(self, endpoint: str, service: str, env: str) -> None:
        super().__init__()
        self.endpoint = endpoint
        self.service = service
        self.env = env
        self._queue: queue.Queue[tuple[str, str, str]] = queue.Queue(maxsize=10_000)
        self._client = httpx.Client(timeout=2.0)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="loki-push", daemon=True)
        self._thread.start()
        atexit.register(self.close)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
            ts_ns = str(int(time.time() * 1_000_000_000))
            self._queue.put_nowait((ts_ns, record.levelname, line))
        except (queue.Full, Exception):  # nunca romper el flujo por logging
            pass

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                ts_ns, level, line = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue
            payload = {
                "streams": [
                    {
                        "stream": {
                            "service": self.service,
                            "level": level,
                            "env": self.env,
                        },
                        "values": [[ts_ns, line]],
                    }
                ]
            }
            with contextlib.suppress(Exception):
                self._client.post(self.endpoint, json=payload)  # Loki caído no afecta al API

    def close(self) -> None:
        self._stop.set()
        try:
            self._client.close()
        finally:
            super().close()


_configured = False


def configure_logging() -> None:
    """Configura el root logger con formato JSON, filtro de trazas y Loki."""
    global _configured
    if _configured:
        return
    settings = get_settings()

    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    # Limpia handlers por defecto (uvicorn) para evitar logs duplicados sin formato
    root.handlers.clear()

    formatter = PgeaJsonFormatter(service=settings.service_name)
    trace_filter = TraceContextFilter()

    stdout = logging.StreamHandler()
    stdout.setFormatter(formatter)
    stdout.addFilter(trace_filter)
    root.addHandler(stdout)

    if settings.loki_endpoint:
        loki = LokiHandler(
            endpoint=settings.loki_endpoint,
            service=settings.service_name,
            env=settings.env,
        )
        loki.setFormatter(formatter)
        loki.addFilter(trace_filter)
        root.addHandler(loki)

    # Alinear loggers de uvicorn/sqlalchemy con el formato JSON
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
    # El log de acceso propio (OTelMiddleware) ya cubre cada request con más
    # contexto y nivel por severidad; silenciamos el access de uvicorn para no
    # duplicar líneas por petición.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # Silenciar clientes HTTP: el handler de Loki usa httpx; si httpx logueara
    # cada push a INFO, ese log se reenviaría a Loki -> bucle de amplificación.
    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Atajo para obtener un logger ya configurado."""
    return logging.getLogger(name)
