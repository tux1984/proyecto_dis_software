"""``OTelMiddleware`` — observabilidad transversal por request (Decorator/CCC).

Implementado como middleware **ASGI puro** (no ``BaseHTTPMiddleware``) para
evitar la pérdida de contexto de OpenTelemetry que sufre ``BaseHTTPMiddleware``
al ejecutar el downstream en otra tarea anyio. Aquí el span raíz se crea y se
activa en el mismo contexto que el handler, de modo que cualquier log o span
hijo emitido durante el request queda correlacionado por ``trace_id`` (RNF-01/03).

Responsabilidades:
    * crear el span SERVER propagando el contexto W3C (``traceparent``),
    * inyectar ``X-Trace-Id`` en la respuesta,
    * emitir el log de acceso JSON con ``duration_ms`` (RNF-01),
    * marcar el span como error y registrar la excepción no manejada (SAD §10.4).
"""

from __future__ import annotations

import logging
import time

from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.trace import SpanKind, Status, StatusCode

logger = logging.getLogger("pgea.access")

_SKIP = {"/health/live", "/health/ready", "/metrics"}
_tracer = trace.get_tracer("pgea.http")


class OTelMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")
        if path in _SKIP:
            await self.app(scope, receive, send)
            return

        headers = {
            k.decode("latin-1"): v.decode("latin-1") for k, v in scope.get("headers", [])
        }
        ctx = extract(headers)  # propagación W3C entrante (traceparent)
        start = time.perf_counter()
        status_holder = {"code": 500}

        with _tracer.start_as_current_span(
            f"{method} {path}", context=ctx, kind=SpanKind.SERVER
        ) as span:
            trace_id = format(span.get_span_context().trace_id, "032x")
            span.set_attribute("http.method", method)
            span.set_attribute("http.target", path)

            async def send_wrapper(message) -> None:
                if message["type"] == "http.response.start":
                    status_holder["code"] = message["status"]
                    message.setdefault("headers", [])
                    message["headers"].append((b"x-trace-id", trace_id.encode()))
                await send(message)

            try:
                await self.app(scope, receive, send_wrapper)
            except Exception as exc:  # noqa: BLE001 — frontera de error global
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                self._log(scope, method, 500, start)
                raise

            code = status_holder["code"]
            span.set_attribute("http.status_code", code)
            if code >= 500:
                span.set_status(Status(StatusCode.ERROR))
            self._log(scope, method, code, start)

    def _log(self, scope, method: str, status: int, start: float) -> None:
        route = scope.get("route")
        route_path = getattr(route, "path", None) or scope.get("path", "")
        # En ASGI, el state del request vive como dict en scope["state"].
        user_id = (scope.get("state") or {}).get("user_id")
        # Nivel según severidad: 2xx/3xx=INFO, 4xx=WARNING, 5xx=ERROR.
        level = (
            logging.ERROR if status >= 500
            else logging.WARNING if status >= 400
            else logging.INFO
        )
        logger.log(
            level,
            "%s %s -> %s",
            method,
            route_path,
            status,
            extra={
                "route": route_path,
                "method": method,
                "status": status,
                "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                "user_id": user_id,
            },
        )
