# PGEA — Plataforma de Gestión de Eventos Académicos

> POC funcional · Pontificia Universidad Javeriana · Curso *Diseño de Software Basado en Patrones*.
> Monolito modular en **Python/FastAPI** con **Clean Architecture + Hexagonal Ports & Adapters**,
> **PostgreSQL 16 + pgvector**, frontend **Vue 3 + Tailwind**, y un stack de **observabilidad completo**
> (OpenTelemetry + Prometheus + Grafana + Loki + Tempo). Orquestado con **Docker Compose**.

---

## 1. Descripción

La gestión de eventos académicos (conferencias, seminarios, talleres, congresos, simposios) en la universidad
está fragmentada en hojas de cálculo, formularios sueltos y correos, lo que produce duplicación de esfuerzos,
falta de visibilidad institucional y experiencias inconsistentes para los asistentes.

**PGEA centraliza** la planificación, promoción, inscripción, ejecución, certificación y análisis de eventos en
una sola plataforma, para cinco perfiles —**organizador, asistente, ponente, revisor y administrador**—. Integra
los servicios institucionales (SSO, pasarela de pagos, correo, calendario) mediante **adaptadores** desacoplados,
de modo que el núcleo de negocio no depende de ningún proveedor concreto.

El **atributo de calidad central es la observabilidad**: cada flujo crítico es operable, diagnosticable y
verificable de extremo a extremo (regla RN-10: ningún módulo *Must have* se considera implementado si no emite
logs estructurados, métricas RED y trazas correlacionadas por `trace_id`).

Materializa fielmente [`docs/SRS.pdf`](docs/SRS.pdf) (30 RF, 18 RNF, 11 reglas de negocio, 7 casos de uso) y
[`docs/SAD.pdf`](docs/SAD.pdf) (arquitectura, 11 ADRs, 14 patrones, modelo físico, SLI/SLO y estrategia de pruebas).

---

## 2. Inicio rápido

Requisitos: **Docker** y **Docker Compose v2**. (No necesitas Python ni Node locales: todo se construye en contenedores.)

```bash
cp .env.example .env          # 1) configuración local (coloca OPENAI_API_KEY y un JWT_SECRET fuerte)
make up                       # 2) construye y levanta TODO el stack (~1 min)
make seed                     # 3) puebla datos sintéticos (usuarios, eventos con embeddings, inscripciones…)
```

| Servicio | URL | Notas |
|---|---|---|
| **SPA (Web App)** | http://localhost:8080 | Nginx sirve la SPA y proxya `/api` |
| **API (OpenAPI/Swagger)** | http://localhost:8000/docs | contrato interactivo |
| **Grafana** | http://localhost:3000 | admin/admin · dashboard *PGEA — RED + SLO* |
| **Prometheus** | http://localhost:9090 | targets: api + worker |
| **Tempo** | http://localhost:3200 | trazas (consultadas desde Grafana) |

Cuentas sembradas (login SSO = el correo institucional): `admin@`, `organizador1@`, `asistente1@`, `ponente1@` `javeriana.edu.co`.

```bash
make test     # suite pytest con cobertura (gate >=70% en módulos críticos)
make load     # pruebas de carga Locust (reportes HTML en backend/tests/load/reports/)
make logs     # logs JSON estructurados de api + worker
make down     # detiene (conserva datos);   make clean  borra volúmenes
```

---

## 3. Roles y funcionalidades

| Módulo | Funcionalidades | Rol principal |
|---|---|---|
| **Catálogo y descubrimiento** | Listado con filtros combinables (fecha, categoría, modalidad, texto), ordenamiento, **búsqueda textual y semántica** | Asistente |
| **Ciclo de vida del evento** | Crear, editar, publicar, cancelar; agenda con sesiones/tracks (detección de solapes); categorías reutilizables; **aprobación institucional** opcional | Organizador / Admin |
| **Inscripciones y pagos** | Inscripción **gratuita** con control atómico de cupos; inscripción **de pago** vía pasarela con webhook idempotente y reserva con expiración; cancelación con liberación de cupo | Asistente |
| **Comunicaciones** | Envío **masivo asíncrono** de correos con segmentación; confirmaciones automáticas; estado por destinatario | Organizador |
| **Certificados** | Generación individual y **en lote**, con código único verificable; verificación pública; descarga en PDF | Asistente / Organizador |
| **Agenda y ponentes** | Invitación a ponentes con token de un solo uso; perfil público y material | Organizador / Ponente |
| **Asistencia y material** | Registro de asistencia; acceso a material y enlace virtual **solo para inscritos confirmados**; evaluación post-evento; exportación a calendario `.ics` | Asistente / Organizador |
| **Administración** | Dashboards institucionales; gestión de usuarios y roles (RBAC); aprobación de eventos; **auditoría inmutable** | Administrador |
| **Privacidad (Ley 1581)** | Consentimiento con marca de tiempo; consulta y supresión (anonimización) de datos personales; log de acceso a PII | Todos |
| **Observabilidad** | Logs, métricas RED y trazas correlacionadas; health checks; dashboards y SLO | Operador / Admin |

Los 7 casos de uso del SRS están cubiertos; el guion de demostración paso a paso está en [`docs/GUION_DEMO.md`](docs/GUION_DEMO.md).

---

## 4. Arquitectura

Monolito modular (ADR-01) con **arquitectura limpia por capas** e inversión de dependencias entre dominio e infraestructura:

```
   HTTP ─► interfaz (routers / DTOs / DI)
            └─► aplicación (servicios: orquestan casos de uso)
                  └─► dominio (entidades, value objects, puertos `Protocol`, eventos)
                  ◄─ infraestructura (repositorios, adaptadores, cola, BD)  implementa los puertos
```

- El **dominio** no depende de framework, BD ni proveedores; define *puertos* (`Protocol`). La **infraestructura**
  los implementa (Hexagonal Ports & Adapters, ADR-03), de modo que un proveedor (pasarela, correo, SSO, embeddings)
  se cambia **por configuración**, sin tocar la lógica de negocio.
- **API y Worker** comparten imagen. El worker procesa trabajo asíncrono (correos, certificados) consumiendo una
  cola en PostgreSQL con `SELECT … FOR UPDATE SKIP LOCKED` (ADR-09), lo que permite escalar workers en paralelo.
- **Nginx** es el único punto de entrada: sirve la SPA, hace *reverse proxy* de `/api`, restringe `/metrics` y
  (en producción) termina TLS.

**Ciclo de una petición:** Nginx → `OTelMiddleware` (crea el span raíz, asigna `trace_id`, mide RED, registra log) →
router (valida el DTO y aplica RBAC) → servicio de aplicación (orquesta) → repositorios/adaptadores → PostgreSQL.
La sesión de BD es la unidad de trabajo del request (commit al final, rollback ante excepción), por lo que la
inscripción, su auditoría y el job encolado se confirman atómicamente.

El detalle completo (C4 C1–C4, vistas Kruchten 4+1, diagramas de secuencia, modelo físico) está en [`docs/SAD.pdf`](docs/SAD.pdf).

### Stack tecnológico (SAD Tabla 22)

| Capa | Tecnología |
|---|---|
| API | Python 3.12 · FastAPI 0.115 · Uvicorn · Pydantic v2 |
| Datos | PostgreSQL 16 · pgvector · SQLAlchemy 2 async · asyncpg · Alembic |
| Auth | OAuth 2.0 / OIDC · JWT propio HS256 (python-jose) |
| Embeddings | OpenAI `text-embedding-3-small` (384 dims) |
| Frontend | Vue 3 · Vite · Tailwind · Pinia · Vue Router |
| Observabilidad | OpenTelemetry · Prometheus · Grafana · Loki · Tempo · `python-json-logger` |
| Asíncrono / PDF | cola PostgreSQL (worker) · fpdf2 |
| Infra / CI-CD | Docker Compose · Nginx · GitHub Actions + GHCR · AWS Lightsail |
| Pruebas | pytest · coverage.py · Locust |

---

## 5. Estructura del monorepo

```
.
├── backend/
│   └── app/
│       ├── interface/        routers (controllers), schemas (DTOs), deps (DI + RBAC)
│       ├── application/       servicios de caso de uso (Event, Enrollment, Notification, Certificate, Search, Auth, Admin…)
│       ├── domain/           entidades, value objects, enums (State), errores, puertos (Protocols), eventos
│       ├── infrastructure/   modelos ORM, repositorios, adapters (+factory), cola, caché, db, seguridad
│       └── observability/    OTel, logging JSON, métricas, middleware
│   ├── alembic/ · scripts/seed_data.py · tests/{unit,integration,contract,e2e,load}
├── frontend/  src/{api, router, stores, components, views, composables}     (SPA Vue 3)
├── infra/     nginx · prometheus(+alerts) · loki · tempo · grafana(provisioning+dashboards) · compose/{stage,prod}
├── docs/      SRS.pdf · SAD.pdf · adr/ · RUNBOOK.md · TRACEABILITY.md · GUION_DEMO.md · ENTREGA_DEMO.md
├── .github/workflows/  ci.yml · deploy-stage.yml · deploy-prod.yml
└── docker-compose.yml (+ .override dev, .test)  ·  Makefile  ·  .env.example
```

---

## 6. Patrones de diseño aplicados

Cada patrón resuelve un problema concreto que apareció en el diseño; aquí se documenta **cuándo se usa**, **dónde
vive** y **un ejemplo** verificable en el código.

### Estilo y patrones de arquitectura

| Patrón | Problema que resuelve / cuándo | Dónde | Ejemplo concreto |
|---|---|---|---|
| **Monolito modular** (estilo, ADR-01) | Entregar rápido con un equipo pequeño sin el overhead de microservicios, manteniendo fronteras claras | un proceso ASGI con módulos por dominio | `docker compose up` levanta un solo backend; cada módulo se prueba aislado con pytest |
| **Layered / N-Capas** | Separar responsabilidades y forzar dependencias unidireccionales | `app/{interface,application,domain,infrastructure}` | el dominio no importa SQLAlchemy ni FastAPI |
| **Hexagonal Ports & Adapters** (ADR-03) | Aislar el núcleo de proveedores externos e intercambiarlos por configuración | `domain/ports/*.py` ↔ `infrastructure/{adapters,repositories}` | `EnrollmentService` depende de `IPaymentAdapter`, no de la pasarela concreta |
| **Repository** | Abstraer la persistencia; dominio testeable sin BD real | `infrastructure/repositories/*` | `EnrollmentRepository.reserve_capacity_and_create()` encapsula el bloqueo y el conteo |
| **Producer–Consumer** (ADR-09) | Desacoplar trabajo lento (correos, PDF) del request HTTP | `infrastructure/queue/postgres_queue.py` + `app/worker.py` | `NotificationService` encola; el worker consume con `FOR UPDATE SKIP LOCKED` |
| **Cache-Aside** | Cumplir el SLO de latencia del catálogo bajo lecturas frecuentes | `infrastructure/cache.py` | primera lectura de catálogo a BD, siguientes desde caché in-memory (TTL corto) |
| **Middleware / cross-cutting** | Aplicar observabilidad y autorización de forma transversal sin duplicar código | `observability/middleware.py`, `interface/deps.py` | `OTelMiddleware` envuelve todos los requests |

### Patrones GoF

| Patrón (familia) | Problema que resuelve / cuándo | Dónde | Ejemplo concreto |
|---|---|---|---|
| **Factory Method** (creacional) | Crear el adaptador correcto según configuración, sin que el servicio conozca la clase concreta | `infrastructure/adapters/factory.py` | `AdapterFactory.create_email()` devuelve `MockEmailAdapter` o `SmtpEmailAdapter` según `EMAIL_PROVIDER` |
| **Builder** (creacional) | Validar entrada campo a campo y construir comandos/entidades inmutables válidas | `interface/schemas/__init__.py` (Pydantic `model_validator`) | `EventCreate` valida que `ends_at > starts_at` antes de llegar al servicio |
| **Adapter** (estructural) | Unificar APIs heterogéneas de proveedores externos tras una interfaz estable | `infrastructure/adapters/{oauth,payment,email,embedding,calendar}.py` | `IOAuthAdapter` con implementación mock y Google, intercambiables |
| **Decorator** (estructural) | Añadir observabilidad a cada operación sin contaminar la lógica | `observability/middleware.py` | el middleware agrega `trace_id`, `X-Trace-Id`, métricas RED y log por request |
| **Facade** (estructural) | Ofrecer una sola entrada a un flujo con múltiples efectos | `application/enrollment_service.py` | `register()` orquesta cupo + pago + cola + auditoría + evento de dominio |
| **Strategy** (comportamiento) | Intercambiar el algoritmo de búsqueda sin condicionales en el servicio | `infrastructure/search_strategies.py` | `SearchService` recibe `TextSearchStrategy` o `SemanticSearchStrategy` inyectada |
| **State** (comportamiento) | Validar transiciones de estado y evitar `if/elif` dispersos | `domain/entities.py` | `Enrollment.confirm()` solo procede desde `pendiente_pago`; si no, lanza `InvalidStateTransitionError` |
| **Observer** (comportamiento) | Disparar efectos desacoplados ante un evento de negocio | `application/enrollment_handlers.py` | al confirmar, se publican handlers: encolar correo, métrica de cupo, auditoría |

### Patrones de diseño / seguridad

| Patrón | Problema que resuelve / cuándo | Dónde | Ejemplo concreto |
|---|---|---|---|
| **Dependency Injection** | Desacoplar y testear; inyectar dobles en pruebas | `interface/deps.py` (FastAPI `Depends`) | los servicios reciben repos/adaptadores; los tests los sustituyen por mocks |
| **Value Object** | Encapsular validación e invariantes; evitar *stringly-typed* | `domain/value_objects.py` | `CapacityCount` garantiza "sin sobreventa"; `EmailAddress` valida formato |
| **Idempotency Key** | Evitar doble procesamiento de webhooks de pago | `webhook_events.idempotency_key` (UNIQUE) | un webhook repetido devuelve `duplicate` sin volver a confirmar |
| **RBAC** | Autorización por rol validada en servidor | `interface/deps.py::require_role` | acceso con rol insuficiente → 403 y queda auditado |
| **MVC / MVVM** | Separar estado, vista y lógica de presentación en el frontend | `frontend/src` | Pinia (Model) · componentes (View) · composables (ViewModel) |

---

## 7. Búsqueda semántica (RF-30, ADR-07)

Además de la búsqueda textual (índice GIN sobre `tsvector` en español), la plataforma ofrece **búsqueda semántica**
que encuentra eventos **relacionados conceptualmente**, aunque no compartan las palabras exactas.

- Al **publicar** un evento se genera su *embedding* (a partir de título + descripción) y se almacena en la columna
  `embedding vector(384)` de la tabla `events`.
- La **consulta** se convierte en un vector y se buscan los *k* eventos más cercanos por **similitud coseno**
  (operador `<=>` de pgvector) sobre un índice **IVFFlat**.
- El proveedor de embeddings es un **adaptador intercambiable**: por defecto OpenAI `text-embedding-3-small` con
  `dimensions=384` (usa `OPENAI_API_KEY`). Si la búsqueda vectorial no está disponible, la estrategia **degrada a
  búsqueda textual** sin romper la experiencia.

```bash
curl "http://localhost:8080/api/search?q=inteligencia%20artificial&semantic=true"
# Devuelve eventos de ML, deep learning, NLP y bases de datos vectoriales, no solo coincidencias literales.
```

---

## 8. Observabilidad (el foco del proyecto)

Tres pilares sobre OpenTelemetry, correlacionados por `trace_id`:

- **Logs JSON** (`python-json-logger`) → push HTTP a **Loki**. Campos: `timestamp, level, service, trace_id, span_id,
  route, method, status, duration_ms, user_id, message`. Niveles por severidad (INFO 2xx · WARNING 4xx con la razón
  de negocio · ERROR 5xx).
- **Métricas RED** (`prometheus-fastapi-instrumentator`) + custom (`enrollment_queue_size`, `notification_sent_total`,
  `webhook_processed_total`, `embedding_generation_duration_seconds`, `certificate_generation_duration_seconds`,
  `event_capacity_available`) → **Prometheus** (scrape cada 15 s a api y worker).
- **Trazas** OTel (auto-instrumentación de asyncpg + spans manuales `enrollment.reserve_capacity`,
  `enrollment.confirm_payment`, `search.semantic_query`) → **Tempo** vía OTLP, con propagación W3C `traceparent`.

Cada respuesta HTTP incluye `X-Trace-Id`. Health: `GET /health/live` (proceso) y `GET /health/ready` (BD, cola, adaptadores).

**Diagnóstico de extremo a extremo (CU-06):** toma el `X-Trace-Id` de una respuesta → búscalo en **Loki**
(`{service="pgea-api"} |= "<trace_id>"`) → desde el log salta a la **traza en Tempo** (span HTTP + negocio + BD) →
valida el impacto en el dashboard **RED + SLO** de Grafana. SLI/SLO y runbooks en [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

---

## 9. Modelo de datos (PostgreSQL 16 + pgvector)

Cinco áreas: identidad/acceso, gestión de eventos, inscripciones/pagos, comunicaciones/certificación y auditoría/búsqueda.
Tablas principales: `users`, `roles`, `categories`, `events` (con `embedding vector(384)`), `event_sessions`,
`event_speakers`, `enrollments`, `payments`, `certificates`, `attendance_records`, `notifications`,
`notification_deliveries`, `webhook_events`, `queued_jobs`, `failed_jobs` (DLQ), `evaluations`, `audit_log`.

Decisiones físicas relevantes: `UNIQUE(event_id, user_id)` evita doble inscripción; índices por `status/starts_at`
(catálogo), GIN full-text e IVFFlat (búsqueda híbrida); `audit_log` es **append-only** (trigger que bloquea
UPDATE/DELETE). Esquema versionado con Alembic. Detalle completo en [`docs/SAD.pdf`](docs/SAD.pdf) §7.

---

## 10. API (resumen)

Contrato interactivo completo en `http://localhost:8000/docs`. Endpoints principales:

| Área | Endpoints |
|---|---|
| Auth | `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me` |
| Catálogo / búsqueda | `GET /events`, `GET /events/{id}`, `GET /search?q=&semantic=`, `GET /categories` |
| Eventos | `POST /events`, `PATCH /events/{id}`, `POST /events/{id}/publish|cancel|approve|reject`, `POST /events/{id}/sessions`, `GET /events/{id}/dashboard`, `GET /events/{id}/calendar.ics` |
| Inscripciones | `POST /enrollments/{event_id}/register`, `POST /enrollments/webhook`, `POST /enrollments/{id}/cancel`, `GET /enrollments/mine`, `GET /enrollments/event/{id}` (+`/export.csv`) |
| Comunicaciones | `POST /notifications/{event_id}/broadcast`, `GET /notifications/{id}/status` |
| Certificados | `POST /certificates/{event_id}/request|batch`, `GET /certificates/mine`, `GET /certificates/verify/{code}`, `GET /certificates/file/{code}.pdf` |
| Participación | `POST /events/{id}/attendance`, `GET /events/{id}/material`, `POST /events/{id}/evaluation`, `POST /events/{id}/speakers`, `POST /speakers/respond` |
| Admin | `GET /admin/dashboard|users|audit|pii-access`, `POST /admin/users/{id}/role`, `GET /admin/events/pending`, `POST /admin/categories` |
| Privacidad | `GET /me/data`, `DELETE /me/data` |
| Salud / métricas | `GET /health/live`, `GET /health/ready`, `GET /metrics` |

---

## 11. Seguridad y cumplimiento

- **Credenciales**: `.env` (en `.gitignore`); `.env.example` documenta todas las variables sin secretos. En la VM:
  `.env` con permisos 600; en CI: *GitHub Secrets*. Configuración tipada y validada al arranque (pydantic-settings).
- **Autenticación** delegada (OAuth 2.0 / OIDC) + JWT propio HS256 sin contraseñas locales; **RBAC** validado en
  servidor (403 + auditoría del intento).
- **Cifrado en tránsito** TLS 1.2+ terminado en Nginx (producción), con cabeceras de seguridad (HSTS, X-Frame-Options…).
- **Ley 1581** (RNF-10, RN-07): consentimiento con marca de tiempo, consulta y supresión por anonimización de datos
  personales, y log de acceso a PII consultable por el administrador.
- **Auditoría inmutable** (ADR-10): `audit_log` append-only garantizado a nivel de base de datos.

---

## 12. Pruebas (RNF-17/18, ADR-11)

```bash
make test     # unit + integración + contrato + e2e, cobertura >=70% (gate)
make load     # Locust: catálogo (RNF-06) e inscripción (RNF-07) con reporte HTML
```

- **Unitarias**: dominio (máquinas de estado, value objects).
- **Integración** (PostgreSQL real): concurrencia de cupos (50 simultáneas, **0 sobreventa**), RBAC, idempotencia de
  webhook, auditoría inmutable, JWT, búsqueda, Ley 1581, health.
- **Contrato**: el mock y la implementación real cumplen el mismo `Protocol`.
- **E2E**: flujo completo de inscripción, envío masivo, recorrido organizador/admin, pilares de observabilidad.
- **Carga** (Locust): escenarios de rendimiento, escalabilidad y resiliencia; reportes HTML/CSV.

Mapa prueba → requisito en [`docs/TRACEABILITY.md`](docs/TRACEABILITY.md).

---

## 13. CI/CD y despliegue (ADR-08)

Monorepo con ramas: `feature/*` → **`stage`** (instancia de pruebas) → **`main`** (instancia de producción).

- [`.github/workflows/ci.yml`](.github/workflows/ci.yml): `ruff` + `mypy` + `pytest` (cobertura ≥70%) + build del
  frontend + build/push de imágenes a **GHCR**.
- [`deploy-stage.yml`](.github/workflows/deploy-stage.yml) / [`deploy-prod.yml`](.github/workflows/deploy-prod.yml):
  la instancia hace `docker pull` desde GHCR, ejecuta migraciones Alembic y verifica `/health/ready` (rollback si falla).
- Overrides por ambiente en [`infra/compose/`](infra/compose/). En producción, Nginx termina TLS (Let's Encrypt).

Guía de despliegue paso a paso (otro equipo → GitHub → AWS Lightsail) en [`docs/ENTREGA_DEMO.md`](docs/ENTREGA_DEMO.md) §4.

---

## 14. Alcance funcional

Implementados **todos los RF salvo RF-23** (CFP / revisión por pares), que el propio SRS marca como *Won't have* del POC.
Cobertura por bloques: catálogo y búsqueda (RF-01/02/30), ciclo de vida de eventos y aprobación (RF-05/06/07/09/24/27),
inscripciones gratuitas y de pago con control atómico (RF-03/04/17), comunicaciones y certificados asíncronos
(RF-12/13/15/21), asistencia, material, ponentes, iCal y evaluación (RF-10/16/18/19/20/22), administración, RBAC y
auditoría (RF-25/26/28/29), y privacidad Ley 1581. Trazabilidad completa en [`docs/TRACEABILITY.md`](docs/TRACEABILITY.md).

---

## 15. Documentación

| Documento | Contenido |
|---|---|
| [`docs/SRS.pdf`](docs/SRS.pdf) · [`docs/SAD.pdf`](docs/SAD.pdf) | Especificación de requisitos y documento de arquitectura |
| [`docs/adr/`](docs/adr/) | 11 decisiones arquitectónicas (contexto, alternativas, consecuencias, validación) |
| [`docs/GUION_DEMO.md`](docs/GUION_DEMO.md) | Guion de demostración paso a paso por flujo |
| [`docs/ENTREGA_DEMO.md`](docs/ENTREGA_DEMO.md) | Ejecución local, checklist de requisitos, volumetría y despliegue a AWS |
| [`docs/TRACEABILITY.md`](docs/TRACEABILITY.md) | Matriz requisito → componente → prueba |
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md) | Operación, SLI/SLO, diagnóstico y respaldo/recuperación |
