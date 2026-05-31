# PGEA — Guía de entrega, ejecución, pruebas y demostración

Este documento te sirve para: (1) entender qué quedó hecho y qué falta, (2) ejecutar y probar el
proyecto **en local ahora mismo**, (3) llevarlo al equipo con Git/AWS y dejarlo funcional en dos
instancias AWS Lightsail (pruebas/stage y producción), y (4) **demostrarle al profesor cada requisito
de los documentos SRS y SAD** (checklist al final), incluyendo las pruebas de volumetría con Locust.

> Convención de ambientes (la del SAD y la que implementa el código):
> **`stage`** = instancia de **pruebas/validación** (rama `stage`) · **`prod`** = instancia de **producción** (rama `main`).
> Son las "dos instancias AWS" que pediste.

---

## 1. Qué se hizo

- **Backend** (`backend/`): Monolito modular Python 3.12 / FastAPI con **Clean Architecture + Hexagonal
  Ports & Adapters**. Capas `interface → application → domain ← infrastructure`. Worker asíncrono.
- **Base de datos**: PostgreSQL 16 + **pgvector** (búsqueda semántica), migraciones Alembic, trigger de
  auditoría inmutable.
- **Frontend** (`frontend/`): SPA **Vue 3 + Vite + Tailwind** (Pinia/MVVM, AuthGuard, ApiClient con `X-Trace-Id`).
- **Observabilidad** (foco del proyecto): **OpenTelemetry + Prometheus + Grafana + Loki + Tempo**.
- **Infra** (`infra/`, `docker-compose*.yml`): Docker Compose, Nginx (reverse proxy/SPA/TLS), overrides stage/prod.
- **Pruebas** (`backend/tests/`): 53 pruebas (unit, integración, contrato, e2e) + 3 scripts Locust. Cobertura 73 %.
- **CI/CD** (`.github/workflows/`): pipelines de CI y de despliegue a Lightsail vía GHCR (escritos, sin ejecutar aún).
- **Docs** (`docs/`): este archivo, `README.md`, `adr/` (11 ADRs), `RUNBOOK.md`, `TRACEABILITY.md`, `HANDOFF_CLAUDE.md`, y los PDFs `SRS.pdf`/`SAD.pdf`.

**Verificado en Docker**: stack completo *healthy*, 53 pruebas en verde (cobertura ≥70 %), ruff y mypy limpios,
y la cadena de observabilidad `trace_id → Loki → Tempo → Grafana` funcionando.

---

## 2. Qué falta

**Para esta entrega (POC local): nada — está funcional.** Lo pendiente es operativo, para producción:

| Pendiente | Detalle |
|---|---|
| Inicializar Git | `git init`, ramas `feature/*` → `stage` → `main`, primer commit, crear repo en GitHub y `push`. |
| Secrets de GitHub | `OPENAI_API_KEY`, `LIGHTSAIL_STAGE_HOST`, `LIGHTSAIL_PROD_HOST`, `LIGHTSAIL_SSH_KEY`. |
| Provisionar AWS | 2 instancias Lightsail (Ubuntu 22.04) con Docker; clonar repo; `.env` con permisos 600. |
| TLS/Dominio (prod) | Apuntar dominio a la IP prod y emitir certificado Let's Encrypt (certbot); editar `infra/nginx/nginx.prod.conf` (`DOMAIN`). |
| Embeddings reales | En prod usar `EMBEDDING_PROVIDER=openai` + `OPENAI_API_KEY` (en local puedes usar `fake`). |

**Deuda técnica reconocida (documentada en SAD §14.2, fuera del POC):** particionado de `audit_log` por año,
caché distribuida (Redis) para >1 réplica, alta disponibilidad del stack de observabilidad, integración real
de adaptadores (Google OAuth, pasarela colombiana, SMTP), pruebas E2E de frontend (Playwright). RF-23 (CFP) queda
como *Won't have*.

---

## 3. Ejecutarlo y probarlo en LOCAL (ahora mismo)

**Requisitos:** Docker + Docker Compose v2 (ya instalados aquí). No necesitas Python ni Node locales.

```bash
cd /home/sfanchi/projects
cp .env.example .env          # ya existe un .env local con EMBEDDING_PROVIDER=fake
make up                       # construye y levanta TODO (~1 min). Espera readiness automáticamente.
make seed                     # datos sintéticos: 20 usuarios, ~22 eventos con embeddings, inscripciones, certificados
```

| Acceso | URL | Credenciales |
|---|---|---|
| SPA (Web) | http://localhost:8080 | login con correo (abajo) |
| API + Swagger | http://localhost:8000/docs | — |
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | — |

**Cuentas demo (login SSO mock = el correo):** `admin@javeriana.edu.co`, `organizador1@javeriana.edu.co`,
`asistente1@javeriana.edu.co`, `ponente1@javeriana.edu.co`. (Cualquier correo nuevo entra como *asistente*.)

**Recorrido manual en la SPA (5 min):**
1. *Login* (botón "Asistente") → **Catálogo**: filtra por modalidad/categoría, activa el check **"Búsqueda semántica"** y busca `inteligencia artificial`.
2. Entra a un evento → **Inscribirme** (gratuito → confirmada) o "Inscribirse y pagar" (paga → redirige al mock).
3. Login como **Organizador** → **Organizador**: crea evento, publícalo, gestiona inscritos (CSV), envía comunicación, marca asistencia, genera certificados.
4. Login como **Administrador** → **Administración**: dashboard institucional, aprobar eventos pendientes, cambiar roles, ver auditoría, botón **Grafana**.
5. *Mis datos* (Ley 1581): consulta/solicita supresión. *Verificar certificado*: pega un código.

**Comandos útiles:** `make logs` (logs JSON de api+worker), `make ps`, `make test`, `make load`, `make down` (parar), `make clean` (borrar datos).

---

## 4. Llevarlo al otro computador (con Git + AWS) y dejarlo funcional

### 4.1 Pasar el proyecto al otro equipo
```bash
# En este equipo: empaquetar sin artefactos pesados
cd /home/sfanchi && tar --exclude='projects/.git' --exclude='**/node_modules' \
  --exclude='**/__pycache__' -czf pgea.tgz projects/
# Copiar pgea.tgz al otro equipo y descomprimir. (El .env NO viaja en git; recréalo allá.)
```
Instala Docker + Docker Compose en el otro equipo y valida: `make up && make seed && make test`.

### 4.2 Inicializar Git y subir a GitHub
```bash
cd projects
git init -b main
git add . && git commit -m "PGEA: POC inicial (backend, frontend, observabilidad, infra, tests)"
git branch stage           # rama de pruebas/validación
gh repo create <org>/pgea --private --source=. --remote=origin   # o crea el repo en la web
git push -u origin main
git push -u origin stage
# Trabajo diario: crea ramas feature/* → PR a stage → PR a main.
```
En GitHub → *Settings → Secrets and variables → Actions* crea: `OPENAI_API_KEY`, `LIGHTSAIL_STAGE_HOST`,
`LIGHTSAIL_PROD_HOST`, `LIGHTSAIL_SSH_KEY`. El CI (`.github/workflows/ci.yml`) corre en cada PR; al hacer
*merge* a `stage`/`main` construye y publica imágenes en **GHCR** y dispara el deploy.

### 4.3 Provisionar las dos instancias AWS Lightsail
Por cada instancia (Ubuntu 22.04, `stage` = 1 GB RAM, `prod` = 2 GB RAM):
```bash
# 1) Instalar Docker en la VM
curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker ubuntu
# 2) Clonar el repo y crear el .env (permisos 600, con la rama correcta)
sudo mkdir -p /opt/pgea && sudo chown ubuntu /opt/pgea && cd /opt/pgea
git clone https://github.com/<org>/pgea.git . && git checkout stage   # o main en prod
cp .env.example .env && chmod 600 .env
#    edita .env: POSTGRES_PASSWORD/JWT_SECRET fuertes, EMBEDDING_PROVIDER=openai, OPENAI_API_KEY,
#    GHCR_OWNER=<org>, TAG=latest|stage, ENV=stage|prod
# 3) Levantar con el override del ambiente
docker compose -f docker-compose.yml -f infra/compose/docker-compose.stage.yml up -d   # (prod usa el override prod)
docker compose exec api alembic upgrade head
docker compose exec api python -m scripts.seed_data    # opcional: datos demo
```
- **prod**: apunta el dominio a la IP pública, edita `infra/nginx/nginx.prod.conf` (reemplaza `DOMAIN`) y emite TLS:
  `docker run ... certbot/certbot certonly --webroot ...` (Let's Encrypt). Abre puertos 80/443 en el firewall de Lightsail.
- A partir de ahí, cada `push` a `stage`/`main` despliega solo (los workflows hacen `docker pull` desde GHCR + migraciones + healthcheck).

**Mapa de ramas → instancias:** `stage` → instancia de pruebas · `main` → instancia de producción. Los abre 80/443
en `prod` (TLS) y 8080 en `stage`.

---

## 5. Pruebas que puedes hacer y revisar tú mismo (local)

### 5.1 Automatizadas (lo que validará el profesor en CI)
```bash
make test          # 53 pruebas + cobertura ≥70% (gate). Salida: PASSED/FAILED + reporte de cobertura.
make lint          # ruff + mypy (gates de calidad del CI)
```
Pruebas clave y qué demuestran (todas en `backend/tests/`):

| Prueba | Demuestra |
|---|---|
| `integration/test_concurrency.py` | 50 inscripciones simultáneas → 1 confirmada, 49×409, **0 sobreventa** (RNF-08/RN-01) |
| `integration/test_payment_webhook_idempotency.py` | webhook idempotente (RF-04/RN-06) |
| `integration/test_audit_log_append_only.py` | DELETE/UPDATE en `audit_log` → error 42501 (RF-29/ADR-10) |
| `integration/test_rbac.py` | 403 + auditoría en acceso no autorizado (RNF-12) |
| `integration/test_semantic_search.py` | búsqueda híbrida texto/semántica (RF-30) |
| `integration/test_privacy.py` | Ley 1581: consulta, supresión, log de PII (RNF-10) |
| `contract/test_adapters.py` | mock y real cumplen el mismo Protocol (RNF-14/15) |
| `e2e/test_full_enrollment_flow.py` | CU-01/02 completos por HTTP |
| `e2e/test_otel_pipeline.py` | `/metrics` expone RED + custom; respuesta trae `X-Trace-Id` |

### 5.2 Observabilidad (el foco — demuéstralo así)
```bash
# 1) Saca el trace_id de una respuesta
curl -sD - -o /dev/null "http://localhost:8080/api/events?limit=1" | grep -i x-trace-id
```
2. Grafana (http://localhost:3000) → **Explore → Loki**: `{service="pgea-api"} |= "<trace_id>"` → ver el log JSON correlacionado.
3. En ese log, clic en el campo `trace_id` → salta a **Tempo**: verás los spans (HTTP + `enrollment.reserve_capacity` + consultas a BD).
4. **Dashboards → PGEA — RED + SLO**: latencia p50/p95/p99, tasa de errores, cola, SLO catálogo/inscripción.

### 5.3 Manuales por API (ejemplos `curl`)
```bash
B=http://localhost:8080/api
TOK=$(curl -s -X POST $B/auth/login -H 'Content-Type: application/json' -d '{"id_token":"asistente1@javeriana.edu.co"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s "$B/search?q=ciberseguridad&semantic=true" | python3 -m json.tool   # búsqueda semántica
curl -s "$B/events?modality=virtual&sort=date_desc" | python3 -m json.tool   # filtros + orden
# Auditoría inmutable (debe fallar con 42501):
docker compose exec postgres psql -U pgea_app_user -d pgea -c "DELETE FROM audit_log;"
```

### 5.4 Certificados PDF de punta a punta (RF-13/19/21, RN-05)

Un certificado de asistencia solo se emite si hay **inscripción confirmada + asistencia registrada** (RN-05).
El **código** se genera al instante; el **PDF** lo renderiza el *worker* (asíncrono) en 1-3 s.

**Opción A — por la SPA (recomendada para la demo):**
1. *Login* como **Asistente** → entra a un evento publicado → **Inscribirme** (queda confirmada).
2. *Login* como **Organizador** (dueño del evento) → **Organizador** → "Gestionar" ese evento → en la tabla de
   inscritos pulsa **"asistió"** (registra la asistencia).
3. *Login* otra vez como el **Asistente** → menú **Certificados**: aparece el certificado. Espera unos segundos
   y el botón **"Descargar PDF"** queda activo → ábrelo (es un PDF A4 con nombre, evento, fecha y código único).
4. **Verificar**: menú **Verificar certificado** → pega el código → muestra "✅ Certificado válido" con el titular.
   (También: el organizador puede generar en lote con **"Generar certificados (lote)"**.)

**Opción B — por API (`curl`):**
```bash
B=http://localhost:8080/api
OT=$(curl -s -X POST $B/auth/login -H 'Content-Type: application/json' -d '{"id_token":"organizador1@javeriana.edu.co"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
UT=$(curl -s -X POST $B/auth/login -H 'Content-Type: application/json' -d '{"id_token":"asistente9@javeriana.edu.co"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
USERID=$(curl -s $B/auth/me -H "Authorization: Bearer $UT" | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
# 1) crea+publica un evento (organizador) y 2) el asistente se inscribe
EID=$(curl -s -X POST $B/events -H "Authorization: Bearer $OT" -H 'Content-Type: application/json' -d '{"title":"Cert Demo","description":"x","modality":"virtual","starts_at":"2026-02-01T10:00:00Z","ends_at":"2026-02-01T12:00:00Z","capacity":50}' | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
curl -s -X POST $B/events/$EID/publish -H "Authorization: Bearer $OT" -H 'Content-Type: application/json' -d '{"request_approval":false}' >/dev/null
curl -s -X POST $B/enrollments/$EID/register -H "Authorization: Bearer $UT" -H 'Content-Type: application/json' -d '{}' >/dev/null
# 3) el organizador registra asistencia
curl -s -X POST $B/events/$EID/attendance -H "Authorization: Bearer $OT" -H 'Content-Type: application/json' -d "{\"user_id\":\"$USERID\"}"
# 4) el asistente solicita el certificado -> obtiene el código
CODE=$(curl -s -X POST $B/certificates/$EID/request -H "Authorization: Bearer $UT" -H 'Content-Type: application/json' -d '{"cert_type":"asistencia"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['verification_code'])")
echo "código: $CODE"
sleep 4   # el worker genera el PDF
# 5) descarga el PDF y verifica el código (público)
curl -s -o cert.pdf "$B/certificates/file/$CODE.pdf" && echo "PDF guardado en cert.pdf ($(wc -c < cert.pdf) bytes)"
curl -s "$B/certificates/verify/$CODE" | python3 -m json.tool
```
Sin asistencia, el paso 4 devuelve **403 `attendance_required`** (RN-05). Si el PDF aún no está, la lista
"Mis certificados" muestra "Generando…" hasta que el worker termina (revisa `make logs` → línea del worker).

---

## 6. ✅ Checklist de requisitos SAD + SRS y cómo demostrar cada uno

> Para los `curl`, primero obtén un token (sección 5.3). En la SPA, el rol se elige en el login.

### 6.1 Requisitos Funcionales (SRS §4)

| RF | Requisito | Cómo probar / ver | Prueba auto |
|----|-----------|-------------------|-------------|
| RF-01 (M) | Catálogo con filtros combinables | SPA Catálogo (filtros) · `GET /api/events?modality=virtual&category_id=&date_from=` | test_semantic_search |
| RF-02 (M) | Ordenar eventos | `?sort=date_asc\|date_desc\|title` | ↑ |
| RF-03 (M) | Inscripción gratuita atómica | SPA "Inscribirme" · `POST /api/enrollments/{id}/register` | test_concurrency |
| RF-04 (M) | Inscripción paga + webhook mock | evento "paga" → `payment_url`; `POST /api/enrollments/webhook` | test_payment_webhook_idempotency |
| RF-05 (M) | Crear evento (borrador) | SPA Organizador · `POST /api/events` (201) | test_full_enrollment_flow |
| RF-06 (M) | Editar/publicar/cancelar | `PATCH /api/events/{id}`, `POST .../publish`, `.../cancel` | test_organizer_admin |
| RF-07 (S) | Tipos de inscripción (gratuita/paga) | campo `registration_type` al crear | test_payment_webhook |
| RF-08 (C) | Formulario personalizado | `register` acepta y persiste `form_data` (JSONB) | — (manual) |
| RF-09 (S) | Agenda/sesiones + solape | `POST /api/events/{id}/sessions` (409 si choca el track) | test_organizer_admin |
| RF-10 (S) | Invitar ponentes | `POST /api/events/{id}/speakers`; `POST /api/speakers/respond?token=` | test_engagement |
| RF-11 (M) | Lista de inscritos + CSV | SPA panel · `GET /api/enrollments/event/{id}` y `.../export.csv` | test_organizer_admin |
| RF-12 (M) | Comunicaciones masivas async | SPA "Comunicación" · `POST /api/notifications/{id}/broadcast` (202) | test_broadcast |
| RF-13 (M) | Generar certificados (lote) | `POST /api/certificates/{id}/batch` | test_engagement |
| RF-14 (S) | Reportes del evento | SPA panel · `GET /api/events/{id}/dashboard` | test_organizer_admin |
| RF-15 (M) | Confirmaciones automáticas | al inscribirse se encola correo (Observer) → ver `make logs` worker | test_broadcast / observabilidad |
| RF-16 (C) | Exportar a calendario .ics | botón ".ics" · `GET /api/events/{id}/calendar.ics` | test_organizer_admin |
| RF-17 (M) | Cancelar inscripción | SPA "Mis inscripciones" · `POST /api/enrollments/{id}/cancel` | test_organizer_admin |
| RF-18 (M) | Material solo con inscripción confirmada | `GET /api/events/{id}/material` (full vs public) | test_engagement |
| RF-19 (M) | Registrar asistencia | SPA "asistió" · `POST /api/events/{id}/attendance` (422 sin inscripción) | test_engagement |
| RF-20 (C) | Evaluación post-evento | `POST /api/events/{id}/evaluation` (403 sin asistencia) | test_engagement |
| RF-21 (M) | Descargar/verificar certificado | `POST /api/certificates/{id}/request` → `GET /api/certificates/verify/{code}` | test_engagement |
| RF-22 (S) | Perfil + material del ponente | respond con `bio`/`material_url` → `GET /api/events/{id}/speakers` | test_engagement |
| RF-23 (W) | CFP / revisión por pares | **No implementado** (Won't have, documentado en SRS y `adr/`) | N/A |
| RF-24 (S) | Aprobación institucional | SPA Admin · `GET /api/admin/events/pending`, `POST .../approve\|reject` | test_organizer_admin |
| RF-25 (S) | Dashboard institucional | SPA Admin · `GET /api/admin/dashboard` | test_rbac |
| RF-26 (M) | Gestión de usuarios + RBAC | SPA Admin · `GET /api/admin/users`, `POST /api/admin/users/{id}/role` | test_rbac |
| RF-27 (C) | Categorías reutilizables | `GET /api/categories`, `POST /api/admin/categories` | test_organizer_admin |
| RF-28 (M) | Auth SSO (mock) + JWT | `POST /api/auth/login`, `/refresh`, `GET /api/auth/me` | test_jwt_auth_flow |
| RF-29 (M) | Auditoría inmutable | SPA Admin "Auditoría" · `GET /api/admin/audit`; DELETE→42501 | test_audit_log_append_only |
| RF-30 (M) | Búsqueda textual + semántica (pgvector) | `GET /api/search?q=...&semantic=true` | test_semantic_search |

### 6.2 Requisitos No Funcionales (SRS §5)

| RNF | Cómo demostrar |
|----|----------------|
| RNF-01 Logs JSON + trace_id | `make logs` → líneas JSON; en Grafana/Loki por `trace_id` |
| RNF-02 Métricas RED + custom | `curl localhost:8000/metrics` · Grafana dashboard RED |
| RNF-03 Trazas W3C + X-Trace-Id | cabecera `X-Trace-Id` en respuestas · traza en Tempo |
| RNF-04 Health checks | `GET /api/health/live` y `/api/health/ready` (detalle por dependencia) |
| RNF-05 SLI/SLO | `docs/RUNBOOK.md` §2 + dashboard Grafana |
| RNF-06 Catálogo p95 ≤500ms | Locust `catalog_p95.py` (sección 7) + dashboard |
| RNF-07 Inscripción p95 ≤2s | Locust `enroll_p95.py` |
| RNF-08 Concurrencia sin sobreventa | `test_concurrency.py` + Locust `enroll_concurrent.py` |
| RNF-09 Recuperación de dependencia | `docker compose stop postgres` → `/health/ready` 503; `start` → ready (RUNBOOK §3) |
| RNF-10 Ley 1581 | `GET/DELETE /api/me/data` + `GET /api/admin/pii-access` (test_privacy) |
| RNF-11 TLS + auth delegada | TLS en `nginx.prod.conf`; JWT sin password local (RF-28) |
| RNF-12 RBAC servidor | `test_rbac.py`; 403 al acceder a panel ajeno |
| RNF-13 Responsive ≥360px | SPA en emulador móvil del navegador |
| RNF-14/15 Adaptadores intercambiables | cambia `EMAIL_PROVIDER` en `.env` + reinicia (RUNBOOK §7); `test_adapters.py` |
| RNF-16 Separación dominio/infra | árbol `app/{domain,infrastructure}`; `test` del dominio sin BD |
| RNF-17 Cobertura ≥70% | `make test` (gate) |
| RNF-18 Carga reproducible | scripts en `tests/load/` (sección 7) |

### 6.3 Reglas de negocio (SRS §6) — todas verificables

RN-01 atomicidad de cupos → `test_concurrency`. RN-02 cancelación → `test_organizer_admin` (cancel) /
RN-05 certificado requiere asistencia → `test_engagement` (403 sin asistencia). RN-06 timeout/idempotencia
de pago → `test_payment_webhook_idempotency` + worker `_expire_reservations`. RN-03 solo `publicado` en
catálogo → catálogo no muestra borradores. RN-07 Ley 1581 → `test_privacy`. RN-08 envío async → `test_broadcast`.
RN-09 enlace solo a confirmados → `GET /events/{id}/material`. RN-10 observabilidad transversal → cualquier
flujo emite log+métrica+traza con `trace_id`.

### 6.4 Casos de uso (SRS §7)

CU-01 Inscribirse → `e2e/test_full_enrollment_flow.py` + SPA. CU-02 Crear/publicar → mismo + Organizador.
CU-03 Comunicación masiva → `e2e/test_broadcast.py`. CU-04 Descargar certificado → `test_engagement` + SPA Certificados.
CU-05 Invitación a ponente → `test_engagement` + SPA. CU-06 Supervisión/diagnóstico → sección 5.2 (trace_id→Loki→Tempo).
CU-07 Aprobación institucional → `test_organizer_admin` + SPA Admin.

### 6.5 Arquitectura, patrones y ADRs (SAD)

| Qué pide el SAD | Dónde demostrarlo |
|---|---|
| Monolito modular + Clean Architecture | árbol `backend/app/{interface,application,domain,infrastructure}` |
| Hexagonal Ports & Adapters | `domain/ports/*.py` (Protocols) ↔ `infrastructure/{adapters,repositories}` |
| Patrones GoF (Factory, Builder, Adapter, Decorator, Facade, Strategy, State, Observer) | tabla en `README.md §4` con la ubicación exacta de cada uno |
| Repository, MVC/MVVM, Producer-Consumer, Cache-Aside, RBAC, Idempotency, Value Object | idem `README.md §4` |
| 11 ADRs (decisiones) | `docs/adr/README.md` (contexto, alternativas, validación de cada una) |
| C4 / Kruchten 4+1 / SLI-SLO | `docs/SAD.pdf` (referencia) + `RUNBOOK.md` |
| Trazabilidad requisito→componente→prueba | `docs/TRACEABILITY.md` |
| Concurrencia SELECT FOR UPDATE (ADR-05) | `infrastructure/repositories/enrollment_repository.py` + `test_concurrency` |
| Auditoría append-only (ADR-10) | trigger en migración `0001_initial.py` + `test_audit_log_append_only` |

---

## 7. Pruebas de volumetría con Locust (según SRS §5.2/5.3 y SAD §6.2)

Tres escenarios definidos por los documentos. Levanta el stack (`make up && make seed`) y ejecuta cada uno.
Locust corre como contenedor efímero en la red de Docker (host `api:8000`).

> **Atajo:** `make load` corre los escenarios 7.1 y 7.2 y deja **reportes HTML + CSV** en
> `backend/tests/load/reports/` (`catalog_p95.html`, `enroll_p95.html`). Ábrelos en el navegador: incluyen
> gráficas de RPS, latencias por percentil, fallos y distribución. Para el escenario 7.3 usa `make load-concurrent EVENT_ID=<uuid>`.

### 7.1 RNF-06 — Rendimiento del catálogo (objetivo p95 ≤ 500 ms, 50 usuarios)
```bash
docker compose run --rm api locust -f tests/load/catalog_p95.py \
  --headless -u 50 -r 10 -t 1m --host http://api:8000 \
  --html tests/load/reports/catalog_p95.html --csv tests/load/reports/catalog_p95
```
Revisa: en `catalog_p95.html` (o en la salida), `95%ile (ms)` de `/events` ≤ 500. En Grafana → dashboard
*PGEA — RED + SLO*, panel "Catálogo p95" en verde durante la corrida.

### 7.2 RNF-07 — Inscripción gratuita bajo carga (objetivo p95 ≤ 2 s, 20 usuarios)
```bash
docker compose run --rm api locust -f tests/load/enroll_p95.py \
  --headless -u 20 -r 5 -t 1m --host http://api:8000 \
  --html tests/load/reports/enroll_p95.html --csv tests/load/reports/enroll_p95
```
Revisa: `95%ile` de `/enrollments/register` ≤ 2000 ms en `enroll_p95.html`. (Tras la 1ª inscripción por
usuario, las repeticiones devuelven 409 `duplicate_registration` — la latencia del endpoint sigue siendo
válida para la medición. Ese 409 ahora se ve claro en los logs: `make logs` muestra
`WARNING regla de negocio: duplicate_registration — El usuario ya está inscrito…`.)

### 7.3 RNF-08 — Concurrencia al último cupo (sin sobreventa, 50 simultáneas)
La prueba **determinista** es `pytest backend/tests/integration/test_concurrency.py` (1 confirmada, 49×409, 0 sobreventa).
Para reproducir con Locust crea un evento con `capacity=1`, publícalo y lánzalo:
```bash
B=http://localhost:8080/api
OT=$(curl -s -X POST $B/auth/login -H 'Content-Type: application/json' -d '{"id_token":"organizador1@javeriana.edu.co"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
EID=$(curl -s -X POST $B/events -H "Authorization: Bearer $OT" -H 'Content-Type: application/json' \
  -d '{"title":"Ultimo cupo","description":"x","modality":"virtual","starts_at":"2026-12-01T10:00:00Z","ends_at":"2026-12-01T12:00:00Z","capacity":1}' | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
curl -s -X POST $B/events/$EID/publish -H "Authorization: Bearer $OT" -H 'Content-Type: application/json' -d '{"request_approval":false}' >/dev/null
docker compose run --rm -e EVENT_ID=$EID api locust -f tests/load/enroll_concurrent.py \
  --headless -u 50 -r 50 -t 15s --host http://api:8000
# Verifica en BD que solo hay 1 confirmada:
docker compose exec postgres psql -U pgea_app_user -d pgea -c \
  "SELECT status, count(*) FROM enrollments WHERE event_id='$EID' GROUP BY status;"
```

### 7.4 Correlación con SLO
Mientras corre Locust, abre Grafana → *PGEA — RED + SLO*: observa **Rate** (req/s), **Errors** (5xx) y
**Duration** (p50/p95/p99) en tiempo real. Esto demuestra los SLI/SLO del SAD (RUNBOOK §2) bajo carga real —
exactamente el "puente entre arquitectura y validación empírica" que pide el documento.

### 7.5 Pruebas EXIGENTES de capacidad (más allá del requisito) — `make load-stress`
Tres escenarios que **superan** lo definido en los documentos para demostrar margen de capacidad y
degradación elegante (sin errores) bajo presión. Generan HTML+CSV en `backend/tests/load/reports/`.

```bash
make load-stress      # corre los 3 seguidos; o individualmente con los comandos de abajo
```

| Script | Qué hace | Frente al requisito |
|---|---|---|
| `stress_catalog.py` | **Carga escalonada** 50→100→150→200 VUs (30 s c/u) sobre catálogo + búsqueda | 4× los 50 VUs de RNF-06 |
| `stress_mixed.py` | **Carga mixta realista** a 100 VUs: login + navegar + buscar + ver detalle + inscribir | 5× los 20 VUs de RNF-07, y además escrituras |
| `spike_catalog.py` | **Pico súbito**: base 10 → 200 VUs → recuperación | ráfaga, valida resiliencia (RNF-09) |

```bash
docker compose run --rm api locust -f tests/load/stress_catalog.py --headless \
  --host http://api:8000 --html tests/load/reports/stress_catalog.html --csv tests/load/reports/stress_catalog
docker compose run --rm api locust -f tests/load/stress_mixed.py --headless -u 100 -r 25 -t 2m \
  --host http://api:8000 --html tests/load/reports/stress_mixed.html --csv tests/load/reports/stress_mixed
docker compose run --rm api locust -f tests/load/spike_catalog.py --headless \
  --host http://api:8000 --html tests/load/reports/spike_catalog.html --csv tests/load/reports/spike_catalog
```

**Cómo interpretarlo para el profesor:** dentro del requisito (50 VUs catálogo / 20 VUs inscripción) el sistema
cumple el SLO (p95 ≤ 500 ms / ≤ 2 s). Al **cuadruplicar/quintuplicar** la carga, la latencia sube pero el
sistema **no produce errores** (0 % fallos): el cuello de botella es el pool de conexiones (10+20) y el bloqueo
por evento (ADR-05), que serializan sin perder peticiones — exactamente el comportamiento esperado y documentado.
Abre los `.html` para ver gráficas de RPS, percentiles y distribución a lo largo del tiempo.

> **Nota sobre certificados (descarga del PDF):** el PDF lo renderiza el *worker* y el *API* lo sirve; ambos
> comparten el volumen `certstorage`. Si recreaste contenedores antes de este arreglo, los certificados viejos
> no tendrán archivo — genera uno nuevo (sección 5.4) y la descarga funcionará.
