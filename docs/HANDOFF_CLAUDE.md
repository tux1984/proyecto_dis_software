# HANDOFF para Claude — contexto del proyecto PGEA

> Lee esto primero. Resume qué es el proyecto, qué está hecho, las decisiones no obvias y los pasos que
> faltan, para que puedas continuar sin re-explorar todo. Acompáñalo con `README.md`, `docs/ENTREGA_DEMO.md`,
> `docs/adr/README.md`, `docs/TRACEABILITY.md` y los PDFs `docs/SRS.pdf` / `docs/SAD.pdf` (fuente de verdad).

## Qué es
**PGEA — Plataforma de Gestión de Eventos Académicos.** POC construido para cumplir **al pie de la letra**
`docs/SRS.pdf` (30 RF, 18 RNF, 11 RN, 7 CU) y `docs/SAD.pdf` (arquitectura, 11 ADRs, 14 patrones, modelo
físico, SLI/SLO). Universidad Javeriana, curso "Diseño de Software Basado en Patrones". El atributo de
calidad **central es la observabilidad** (RN-10).

## Arquitectura (resumen)
Monolito modular Python 3.12/FastAPI con **Clean Architecture + Hexagonal Ports & Adapters**. Capas:
`interface (routers/DTOs) → application (servicios) → domain (entidades, VOs, puertos Protocol) ← infrastructure (repos, adapters, queue, db)`.
Frontend Vue 3 + Vite + Tailwind (Pinia/MVVM). PostgreSQL 16 + pgvector. Worker async (cola en BD con
`FOR UPDATE SKIP LOCKED`). Observabilidad: OpenTelemetry + Prometheus + Grafana + Loki + Tempo. Nginx como
único punto de entrada (SPA + proxy `/api` + TLS en prod). Docker Compose; CI/CD GitHub Actions + GHCR; AWS Lightsail (stage/prod).

## Estructura del repo
```
backend/app/{interface,application,domain,infrastructure,observability}  · alembic/ · scripts/seed_data.py · tests/{unit,integration,contract,e2e,load}
frontend/src/{api,router,stores,components,views,composables}
infra/{nginx,prometheus,loki,tempo,grafana,compose}     docs/{SRS.pdf,SAD.pdf,adr,RUNBOOK.md,TRACEABILITY.md,ENTREGA_DEMO.md}
docker-compose.yml(+ .override.yml dev, .test.yml)   Makefile   .env.example   .github/workflows/
```
Mapa de patrones → archivos en `README.md §4`. Mapa requisito → componente → prueba en `docs/TRACEABILITY.md`.

## Decisiones NO obvias (no las cambies sin entenderlas)
1. **Observabilidad/trace_id**: el span HTTP raíz lo crea un **middleware ASGI propio** en
   `app/observability/middleware.py`, **no** `FastAPIInstrumentor`. Razón: `BaseHTTPMiddleware` rompe la
   propagación de contexto de OpenTelemetry y el `trace_id` salía `null`. `init_tracing()` solo configura el
   provider + auto-instrumenta asyncpg (spans hijos). Si reintroduces FastAPIInstrumentor tendrás spans duplicados.
2. **Embeddings**: puerto `IEmbeddingAdapter` con `OpenAIEmbeddingAdapter` (`text-embedding-3-small`, `dimensions=384`,
   coincide con `vector(384)`) y `FakeEmbeddingAdapter` determinista. `EMBEDDING_PROVIDER=fake` en tests/CI (sin API key);
   `openai` en demo/prod. NO cambies la dimensión sin migrar el índice.
3. **Auditoría inmutable (ADR-10)**: trigger PL/pgSQL en la migración `0001_initial.py` que lanza SQLSTATE
   `42501` en UPDATE/DELETE de `audit_log`. Es más fuerte que REVOKE (aplica al dueño). El repo solo expone `append`.
4. **Concurrencia (ADR-05)**: `EnrollmentRepository.reserve_capacity_and_create` usa `SELECT … FOR NO KEY UPDATE`
   + conteo de ocupados (confirmadas + reservas activas) en la misma transacción. `test_concurrency.py` lo valida.
5. **Worker** corre como proceso separado con su propio registro Prometheus → expone `/metrics` en `:8001`
   (Prometheus lo raspa como target `pgea-worker`). El API expone `:8000/metrics`.
6. **Unit of Work**: `get_session` (FastAPI dependency) hace commit al final del request / rollback en excepción;
   los repositorios comparten esa sesión. Por eso inscripción + auditoría + job encolado se confirman juntos.
7. **Certificados PDF**: el *worker* los renderiza en `/app/storage/certificates` y el *API* los sirve en
   `GET /certificates/file/{code}.pdf`. Al ser contenedores distintos comparten el **volumen `certstorage`**
   (montado en `api` y `worker`). Sin ese volumen el API responde "Certificado aún no generado". En prod, evaluar S3.
8. **Logs**: niveles por severidad (INFO 2xx, WARNING 4xx con la razón de negocio, ERROR 5xx) en
   `observability/middleware.py` + `interface/exception_handlers.py`. `uvicorn.access` está silenciado (WARNING)
   para no duplicar el log de acceso propio.

## Gotchas del entorno (¡importantes!) — ver memoria `env-docker-wsl-proxy`
- **Build tras proxy corporativo con TLS interception**: el Dockerfile del backend fija
  `PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org pypi.python.org"` (si no, `pip` falla con `CERTIFICATE_VERIFY_FAILED`).
  En un equipo sin ese proxy no estorba.
- **Docker Desktop + WSL**: editar un archivo montado como *single-file bind mount* (p. ej. `infra/prometheus/prometheus.yml`,
  `nginx.conf`) invalida el mount → `docker compose restart` falla; usa **`docker compose down && up`** para re-resolverlo.
- `docker compose run` deja vivos los contenedores dependientes (p. ej. `postgres-test`); los tests usan datos
  con correos únicos o se hace `docker compose -f ... -f docker-compose.test.yml rm -sf postgres-test` antes.
- **mypy/ruff**: para que tomen la config viva usa el servicio `api-test` (monta `pyproject.toml`):
  `docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm --no-deps api-test mypy app`.
  El servicio `api` usa el `pyproject.toml` horneado en la imagen.

## Estado actual (a 2026-05-30)
- **Funcional en Docker y verificado**: `make up` (9 servicios healthy), `make seed`, `make test`
  (**53 passed, cobertura 73.45%**), `ruff` ✓, `mypy` ✓, y la cadena `trace_id → Loki → Tempo → Prometheus/Grafana` probada.
- Todos los RF **salvo RF-23** (CFP, *Won't have*) implementados.
- **NO** está inicializado en git, **NO** subido a GitHub, **NO** desplegado en AWS. Los workflows
  (`.github/workflows/`) y los overrides `infra/compose/docker-compose.{stage,prod}.yml` están escritos pero sin ejecutar.

## Pasos pendientes (en orden) — detalle en `docs/ENTREGA_DEMO.md §4`
1. `git init -b main`, commit inicial, crear rama `stage`, crear repo en GitHub, `push` de ambas ramas.
2. Crear GitHub Secrets: `OPENAI_API_KEY`, `LIGHTSAIL_STAGE_HOST`, `LIGHTSAIL_PROD_HOST`, `LIGHTSAIL_SSH_KEY`.
3. Provisionar 2 instancias Lightsail (Ubuntu 22.04) con Docker; clonar; `.env` (600) con `EMBEDDING_PROVIDER=openai`,
   `OPENAI_API_KEY`, `GHCR_OWNER`, `TAG`, `ENV`.
4. Levantar con el override del ambiente (`infra/compose/docker-compose.stage.yml` / `prod.yml`) + `alembic upgrade head`.
5. En prod: dominio + TLS Let's Encrypt (editar `infra/nginx/nginx.prod.conf`, reemplazar `DOMAIN`).
6. A partir de ahí, `push` a `stage`/`main` despliega solo (CI → GHCR → deploy SSH + healthcheck).

## Cómo ejecutar y validar (local)
```bash
cp .env.example .env            # EMBEDDING_PROVIDER=fake basta para local/tests
make up && make seed            # stack + datos
make test                       # pruebas + cobertura
make lint                       # ruff + mypy
make load                       # Locust catálogo (ver docs/ENTREGA_DEMO.md §7 para los 3 escenarios)
```
SPA :8080 · API :8000/docs · Grafana :3000 (admin/admin). Login mock = correo
(`admin@`, `organizador1@`, `asistente1@`, `ponente1@` `javeriana.edu.co`).

## Convenciones
- Código y comentarios en español; commits terminan con el co-author de Claude.
- No commitear `.env` (en `.gitignore`); `.env.example` documenta todas las variables.
- Cada RF *Must* tiene al menos una prueba (`docs/TRACEABILITY.md`); el gate de CI exige cobertura ≥70%.
- Antes de tocar configs de observabilidad o el middleware ASGI, repasa el punto 1 de "Decisiones no obvias".
