# Trazabilidad — Requisito → Componente → Prueba

Cadena de cierre técnico (SAD §12): cada requisito se traza hasta el componente que lo implementa y
la prueba que lo valida. Las pruebas viven en `backend/tests/`.

## Requisitos funcionales (RF)

| RF | Descripción | Componente | Prueba |
|---|---|---|---|
| RF-01/02 | Catálogo con filtros y orden | `SearchService`, `EventRepository.search_catalog` | `integration/test_semantic_search.py`, e2e catálogo |
| RF-03 | Inscripción gratuita atómica | `EnrollmentService`, `EnrollmentRepository` (FOR NO KEY UPDATE) | `integration/test_concurrency.py` |
| RF-04 | Inscripción paga + webhook | `EnrollmentService.handle_payment_webhook`, `MockPaymentAdapter` | `integration/test_payment_webhook_idempotency.py` |
| RF-05/06 | CRUD y ciclo de vida del evento | `EventService` (State), `EventRouter` | `e2e/test_full_enrollment_flow.py`, `e2e/test_organizer_admin.py` |
| RF-07 | Tipos de inscripción | `Event.registration_type` | e2e organizador |
| RF-09 | Agenda/sesiones + solape | `EventService.add_session`, `SessionRepository.overlaps_in_track` | `e2e/test_organizer_admin.py` |
| RF-10/22 | Ponentes (invitación, respuesta, material) | `SpeakerService`, `SpeakerRepository` | `integration/test_engagement.py` |
| RF-11 | Listado de inscritos + CSV | `EnrollmentRepository.list_with_users`, `EnrollmentRouter` | `e2e/test_organizer_admin.py` |
| RF-12/15 | Comunicaciones masivas async | `NotificationService`, `worker`, `EmailAdapter` | `e2e/test_broadcast.py` |
| RF-13/21 | Certificados (lote, código, verificación) | `CertificateService`, `worker`, `pdf.py` | `integration/test_engagement.py` |
| RF-16 | Exportar a calendario (.ics) | `IcsCalendarAdapter`, `EventRouter` | `e2e/test_organizer_admin.py` |
| RF-17 | Cancelar inscripción | `EnrollmentService.cancel` | `e2e/test_organizer_admin.py` |
| RF-18 | Acceso a material según inscripción | `MaterialService` | `integration/test_engagement.py` |
| RF-19 | Registro de asistencia | `AttendanceService` | `integration/test_engagement.py` |
| RF-20 | Evaluación post-evento | `EvaluationService` | `integration/test_engagement.py` |
| RF-24 | Aprobación institucional | `EventService.approve/reject` | `e2e/test_organizer_admin.py` |
| RF-25 | Dashboard institucional | `AdminService`, `StatsRepository` | `integration/test_rbac.py` (dashboard) |
| RF-26 | Gestión de usuarios y RBAC | `AdminService.set_role`, `require_role` | `integration/test_rbac.py`, e2e admin |
| RF-28 | Auth SSO + JWT | `AuthService`, `OAuthAdapter` | `integration/test_jwt_auth_flow.py` |
| RF-29 | Auditoría inmutable | `AuditLogRepository` + trigger BD | `integration/test_audit_log_append_only.py` |
| RF-30 | Búsqueda textual + semántica | `SearchService` (Strategy), `EmbeddingRepository` | `integration/test_semantic_search.py` |
| RF-23 | CFP / revisión por pares | — (Won't have, documentado) | N/A |

## Requisitos no funcionales (RNF)

| RNF | Atributo | Componente | Prueba / Evidencia |
|---|---|---|---|
| RNF-01 | Logs JSON + trace_id | `observability/logging_config.py`, `middleware.py` | `e2e/test_otel_pipeline.py`; Loki en demo |
| RNF-02 | Métricas RED + custom | `observability/metrics.py` | `e2e/test_otel_pipeline.py`; Prometheus/Grafana |
| RNF-03 | Trazas W3C + X-Trace-Id | `observability/{otel,middleware}.py` | header verificado; Tempo en demo |
| RNF-04/09 | Health checks y recuperación | `routers/health.py` | `integration/test_health_dependency_failure.py` |
| RNF-08 | Concurrencia sin sobreventa | `EnrollmentRepository` | `integration/test_concurrency.py` |
| RNF-06/07 | Rendimiento (p95) | catálogo / inscripción | `tests/load/{catalog_p95,enroll_p95}.py` |
| RNF-10 | Ley 1581 (PII) | `PrivacyService` | `integration/test_privacy.py` |
| RNF-12 | RBAC server-side | `require_role` | `integration/test_rbac.py` |
| RNF-14/15 | Adaptadores intercambiables | `AdapterFactory`, puertos | `contract/test_adapters.py` |
| RNF-17 | Cobertura ≥ 70 % | suite completa | `make test` (gate CI) |
| RNF-18 | Carga reproducible | scripts Locust | `tests/load/*` |

## Reglas de negocio (RN)

RN-01 (atomicidad de cupos) → `test_concurrency`; RN-05 (certificado requiere asistencia) → `test_engagement`;
RN-06 (timeout/idempotencia de pago) → `test_payment_webhook_idempotency` + `worker._expire_reservations`;
RN-07 (Ley 1581) → `test_privacy`; RN-08 (envío async) → `test_broadcast`; RN-10 (observabilidad transversal) → `test_otel_pipeline` + pipeline en demo.
