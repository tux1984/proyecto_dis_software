"""Mapeo de errores de dominio a HTTP (SAD §10.4).

El dominio no conoce HTTP; aquí cada ``DomainError`` se traduce a un código y a
una respuesta que incluye ``trace_id`` para soporte (RNF-03).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from opentelemetry import trace

from app.domain.errors import DomainError

logger = logging.getLogger("pgea.errors")

_STATUS_BY_CODE = {
    "unauthorized": 401,
    "forbidden": 403,
    "no_capacity": 409,
    "duplicate_registration": 409,
    "invalid_state_transition": 409,
    "cancellation_not_allowed": 409,
    "payment_timeout": 410,
    "attendance_required": 403,
    "registration_required": 422,
    "validation_error": 400,
    "domain_error": 400,
}


def _trace_id() -> str | None:
    span = trace.get_current_span()
    ctx = span.get_span_context() if span else None
    return format(ctx.trace_id, "032x") if ctx and ctx.is_valid else None


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        status = _STATUS_BY_CODE.get(exc.code, 400)
        trace_id = _trace_id()
        # Registra la razón de negocio con nivel acorde: 5xx=ERROR, 4xx=WARNING.
        # Así un 409 deja en el log un mensaje claro como
        # "regla de negocio: duplicate_registration — El usuario ya está inscrito…".
        level = logging.ERROR if status >= 500 else logging.WARNING
        logger.log(
            level,
            "regla de negocio: %s — %s",
            exc.code,
            exc,
            extra={
                "error_code": exc.code,
                "status": status,
                "route": request.url.path,
                "method": request.method,
            },
        )
        return JSONResponse(
            status_code=status,
            content={"error": exc.code, "detail": str(exc), "trace_id": trace_id},
            headers={"X-Trace-Id": trace_id or ""},
        )

    # Errores de validación de FastAPI/Pydantic (422) → WARNING con detalle.
    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        trace_id = _trace_id()
        logger.warning(
            "validación de entrada inválida en %s %s: %s",
            request.method,
            request.url.path,
            exc.errors(),
            extra={"error_code": "request_validation", "status": 422,
                   "route": request.url.path, "method": request.method},
        )
        return JSONResponse(
            status_code=422,
            content={"error": "request_validation", "detail": exc.errors(), "trace_id": trace_id},
            headers={"X-Trace-Id": trace_id or ""},
        )
