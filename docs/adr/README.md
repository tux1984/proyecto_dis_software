# Architecture Decision Records (ADR)

Registro de las decisiones arquitectónicas del POC (resumen del SAD §8). Cada una incluye contexto,
decisión, alternativas evaluadas, consecuencias y criterio de validación verificable en este repositorio.

---

## ADR-01 — Estilo: Monolito modular
**Contexto.** Equipo de 2 personas, 16 semanas, presupuesto acotado, observabilidad end-to-end como foco.
**Decisión.** Monolito modular en FastAPI: un proceso ASGI con módulos `auth, events, enrollment, notification, certificate, search, admin` bajo arquitectura limpia.
**Alternativas.** Microservicios (orquestación/overhead injustificado), Serverless (incompatible con conexiones persistentes), monolito sin modularizar (intesteable).
**Consecuencias.** + despliegue único, transacciones locales, instrumentación trivial. − escalado solo por réplica completa.
**Validación.** `docker compose up` < 60 s; módulos testeables aislados (`backend/tests/unit`).

## ADR-02 — Framework: FastAPI sobre Python 3.12
**Decisión.** FastAPI 0.115 + Uvicorn + Pydantic v2 + SQLAlchemy 2 async + asyncpg.
**Alternativas.** Flask+gevent (sin async/Pydantic nativo), Django REST (pesado), Starlette puro (sin validación/OpenAPI).
**Consecuencias.** + throughput async, validación tipada, OpenAPI gratis, DI con `Depends`. − cuidado con llamadas bloqueantes (se usan `run_in_executor`, p. ej. PDF).
**Validación.** OpenAPI en `/docs`; tests inyectan dobles vía `Depends`.

## ADR-03 — Integraciones externas: patrón Adapter
**Decisión.** Cada integración (OAuth, pagos, correo, embeddings, calendario) es un `Protocol` con implementación mock + real; selección por configuración (`AdapterFactory`).
**Consecuencias.** + modificabilidad y testeabilidad (mock sin red). − boilerplate de una interfaz por integración.
**Validación.** `contract/test_adapters.py`: mock y real cumplen el mismo contrato (E6).

## ADR-04 — Observabilidad: OpenTelemetry + Prometheus + Grafana + Loki (+Tempo)
**Contexto.** Atributo de calidad central (RNF-01..05, RN-10); instancia con 2 GB RAM.
**Decisión.** Tres pilares OTel; métricas con `prometheus-fastapi-instrumentator`; logs JSON con `python-json-logger` a Loki; trazas a Tempo (integrado en Grafana).
**Alternativas.** ELK (excede RAM), Datadog/New Relic (costo/lock-in), solo stdout (sin métricas/alertas).
**Consecuencias.** + ~300 MB RAM, costo cero licencias, correlación nativa. − config inicial mayor.
**Validación.** Demo: `trace_id` de la respuesta localizado en Loki + Tempo + RED en Grafana ≤ 5 min.
> Nota de implementación: el span HTTP raíz lo crea un **middleware ASGI propio** (no `BaseHTTPMiddleware`) para evitar el conflicto conocido de propagación de contexto OTel; asyncpg se auto-instrumenta como spans hijos.

## ADR-05 — Concurrencia de cupos: SELECT FOR UPDATE
**Decisión.** Bloqueo pesimista `SELECT … FOR NO KEY UPDATE` sobre la fila del evento; cupo = `capacity − COUNT(ocupados)` en la misma transacción.
**Alternativas.** Optimistic locking (mala UX con 50 escrituras), serializable (más aborts), advisory locks (no portable), decremento de campo (desincronización).
**Consecuencias.** + consistencia 100 % verificable, liberación correcta en cancelaciones. − throughput serializado por evento (suficiente para el POC).
**Validación.** `integration/test_concurrency.py`: 50 simultáneas → 1 confirmada, 49 × 409, 0 sobreventa.

## ADR-06 — Autenticación: OAuth 2.0 + JWT propio
**Decisión.** SSO delegado (mock/Google) valida el `id_token`; el sistema emite un JWT propio HS256 (sub, role, exp). Rutas protegidas con `Depends(get_current_user)` + RBAC.
**Consecuencias.** + stateless (escalado horizontal trivial), separación de responsabilidades. − bearer token: TTL corto + HTTPS.
**Validación.** `integration/test_jwt_auth_flow.py` (válido/ inválido/ expirado); `test_rbac.py`.

## ADR-07 — Búsqueda híbrida: pgvector + texto completo
**Decisión.** Índice GIN sobre `tsvector` (texto) + columna `vector(384)` con IVFFlat `vector_cosine_ops` (semántica). Embeddings con `text-embedding-3-small` (384d) u OpenAI/`fake`.
**Alternativas.** Elasticsearch (RAM/infra), solo texto (no semántico), vector DB externa (costo).
**Consecuencias.** + una sola BD, sin sincronización, backup unificado. − IVFFlat es búsqueda aproximada.
**Validación.** `integration/test_semantic_search.py`.

## ADR-08 — Despliegue: Docker Compose en AWS Lightsail
**Decisión.** Dos instancias Lightsail (stage/prod); imágenes en GHCR (la VM solo hace `docker pull`); Nginx + Let's Encrypt.
**Consecuencias.** + costo bajo, control total, despliegue en segundos. − SPOF de instancia única (aceptable para POC).
**Validación.** `docker compose ps` healthy; reinicio de contenedor se recupera por `restart: always`.

## ADR-09 — Asincronía: cola interna en PostgreSQL
**Decisión.** Cola en tabla `queued_jobs` consumida por un worker con `SELECT … FOR UPDATE SKIP LOCKED`; reintentos con backoff y DLQ (`failed_jobs`).
**Alternativas.** Celery+Redis / RabbitMQ / SQS (broker adicional, overhead para el POC).
**Consecuencias.** + sin broker extra, encolar y operar son atómicos en BD (outbox). − cuello de botella > 10k jobs/min (migrable a Redis).
**Validación.** `e2e/test_broadcast.py`; gauge `enrollment_queue_size`.

## ADR-10 — Auditoría inmutable (append-only)
**Decisión.** `audit_log` append-only: el repositorio solo expone `insert`; a nivel de BD un **trigger** bloquea UPDATE/DELETE (SQLSTATE `42501`), defensa en profundidad superior a un simple REVOKE (aplica incluso al dueño).
**Consecuencias.** + cumplimiento real de RN-07. − crecimiento indefinido (particionado por año como deuda técnica).
**Validación.** `integration/test_audit_log_append_only.py`.

## ADR-11 — Estrategia de pruebas: pytest + Locust + cobertura mínima
**Decisión.** Cinco niveles (unitarias, integración, contrato, e2e, carga) en el pipeline CI; cobertura ≥ 70 % en módulos críticos.
**Consecuencias.** + cobertura efectiva con bajo overhead. − refactors mantienen pruebas (práctica saludable).
**Validación.** CI verde con `--cov-fail-under=70`; cada RF Must tiene al menos una prueba (ver `TRACEABILITY.md`).
