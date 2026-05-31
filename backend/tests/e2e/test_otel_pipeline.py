"""E2E RNF-01..03 — pilares de observabilidad expuestos.

Verifica que el endpoint ``/metrics`` expone las señales RED y las métricas
custom, y que cada respuesta incluye la cabecera ``X-Trace-Id`` (correlación).
La validación completa logs+trazas en Loki/Tempo se realiza en la demo en vivo
(documentada en el RUNBOOK), pues requiere el stack de observabilidad activo.
"""

from __future__ import annotations

import pytest


@pytest.mark.e2e
async def test_metrics_endpoint_exposes_red_and_custom(client):
    # Genera algo de tráfico para poblar las métricas RED.
    await client.get("/events")
    resp = await client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    # RED
    assert "http_request_duration_seconds" in body
    assert "http_requests_total" in body
    # Custom (RNF-02)
    assert "enrollment_queue_size" in body
    assert "webhook_processed_total" in body or "notification_sent_total" in body


@pytest.mark.e2e
async def test_response_has_trace_id_header(client):
    resp = await client.get("/events")
    assert "x-trace-id" in {k.lower() for k in resp.headers}
    trace_id = resp.headers["x-trace-id"]
    assert len(trace_id) == 32  # 128 bits en hex
