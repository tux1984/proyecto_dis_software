"""Observabilidad transversal (ADR-04, RNF-01..05, RN-10).

Tres pilares sobre OpenTelemetry:
    - Logs estructurados JSON con ``trace_id`` (RNF-01) -> Loki.
    - Métricas RED + custom (RNF-02) -> Prometheus.
    - Trazas distribuidas W3C (RNF-03) -> Tempo.

``RN-10``: ningún módulo *Must have* se considera implementado si no emite sus
señales. Por eso la instrumentación se inicializa antes que la lógica de negocio.
"""
