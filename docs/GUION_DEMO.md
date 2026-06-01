# PGEA — Guion de demostración

Guía paso a paso para presentar la plataforma. Cada sección indica **qué hacer**, **qué resaltar** y a
**qué requisito** del SRS/SAD corresponde, para que puedas demostrar cada punto cuando el profesor lo pida.

**Login (SSO mock = el correo completo):** `admin@javeriana.edu.co`, `organizador1@javeriana.edu.co`, `asistente1@javeriana.edu.co`, `ponente1@javeriana.edu.co`

### Accesos locales

| Servicio | URL |
|----------|-----|
| Frontend (SPA) | http://localhost:8080 |
| API / Swagger | http://localhost:8000/docs |
| API / ReDoc | http://localhost:8000/redoc |
| Grafana | http://localhost:3000 (admin/admin) |
| Prometheus | http://localhost:9090 |

### Accesos AWS — Stage (`13.220.166.163`)

| Servicio | URL |
|----------|-----|
| Frontend (SPA) | http://13.220.166.163:8080 |
| API / Swagger | http://13.220.166.163:8000/docs |
| API / ReDoc | http://13.220.166.163:8000/redoc |
| Health check | http://13.220.166.163:8080/api/health/ready |
| Grafana | http://13.220.166.163:3000 (admin/admin) |
| Prometheus | http://13.220.166.163:9090 |

### Accesos AWS — Prod (`44.192.12.194`)

| Servicio | URL |
|----------|-----|
| Frontend (SPA) | http://44.192.12.194:8080 |
| API / Swagger | http://44.192.12.194:8000/docs |
| API / ReDoc | http://44.192.12.194:8000/redoc |
| Health check | http://44.192.12.194:8080/api/health/ready |
| Grafana | Solo por túnel SSH: `ssh -L 3000:localhost:3000 ubuntu@44.192.12.194 -i ~/.ssh/github_actions_key` → http://localhost:3000 |
| Prometheus | Solo por túnel SSH: `ssh -L 9090:localhost:9090 ubuntu@44.192.12.194 -i ~/.ssh/github_actions_key` → http://localhost:9090 |

---

## 0. Preparación (5 min antes de la demo)

```bash
cd <proyecto>
make up                 # stack completo: api, worker, postgres, nginx, prometheus, grafana, loki, tempo
make seed               # datos sintéticos (solo si la BD está vacía — es idempotente)
make clean-loadtest     # elimina inscritos sintéticos de pruebas de carga (deja cupos libres)
make ps                 # verifica que todo esté healthy antes de empezar
```

**Pestañas a tener abiertas:**
1. SPA → http://localhost:8080
2. Grafana → http://localhost:3000 con el dashboard **PGEA — RED + SLO** ya abierto
3. Terminal corriendo `make logs`
4. DevTools del navegador (pestaña **Network**) para mostrar la cabecera `X-Trace-Id`
5. Swagger UI → http://localhost:8000/docs (para mostrar endpoints directamente si hace falta)

> Mensaje de apertura: *"PGEA es un monolito modular en FastAPI con Clean Architecture + Hexagonal Ports & Adapters, PostgreSQL+pgvector, frontend Vue, y observabilidad completa con OpenTelemetry, Prometheus, Grafana, Loki y Tempo. Está desplegado en AWS Lightsail con CI/CD automático desde GitHub. El eje técnico del proyecto es que cada flujo crítico es completamente trazable: logs, métricas y trazas distribuidas correlacionadas por `trace_id`."*

---

## 1. Flujo del estudiante: inscripción → asistencia → certificado → verificación

**Objetivo:** mostrar el ciclo completo del asistente (CU-01, CU-04). Cubre RF-01/02/03/13/18/19/21/30, RN-05.

**Pasos:**

1. **Login** como `asistente1@javeriana.edu.co` → botón "Ingresar como Asistente".

2. **Catálogo con filtros** (RF-01, RF-02):
   - Aplica filtro de modalidad (virtual), luego categoría (IA), luego orden (fecha ascendente).
   - *Resalta:* los filtros son combinables y el orden es configurable — RF-01 y RF-02.

3. **Búsqueda semántica** (RF-30, ADR-07) — ver sección detallada abajo:
   - Activa el check **"Búsqueda semántica"** y busca `inteligencia artificial`.
   - Observa que devuelve eventos de Deep Learning, Procesamiento de Lenguaje Natural y Bases de Datos Vectoriales — **sin que esas palabras aparezcan en la query**.
   - *Resalta:* búsqueda por concepto, no por palabra clave.

4. **Inscripción** (RF-03, RN-01):
   - Entra a un evento gratuito → pulsa **"Inscribirme"** → estado: `confirmada`.
   - *Resalta:* la inscripción es atómica con control de concurrencia (`SELECT FOR NO KEY UPDATE`).

5. **Registro de asistencia** — cambia a `organizador1@javeriana.edu.co`:
   - Menú **Organizador** → "Mis eventos" → "Gestionar" el evento → en la tabla de inscritos pulsa **"asistió"** junto a Asistente 1.
   - *Resalta:* RF-19 — intentar marcar a alguien sin inscripción confirmada devuelve 422.

6. **Solicitar certificado** — vuelve a `asistente1@javeriana.edu.co`:
   - "Mis inscripciones" → pulsa **"Solicitar certificado"** en el evento donde tienes asistencia.
   - *Resalta:* RN-05 — sin asistencia registrada el sistema responde 403. La asistencia es requisito de negocio, no solo UI.

7. **Descargar certificado** (RF-13, ADR-09):
   - Menú "Certificados" → espera 1-3 s → **"Descargar PDF"**.
   - Abre el PDF: muestra nombre completo, evento, fecha y **código único de verificación**.
   - *Resalta:* el worker lo generó en segundo plano con una cola PostgreSQL (`FOR UPDATE SKIP LOCKED`) — el API solo encola y responde de inmediato, sin bloquear.

8. **Verificación pública** (RF-21):
   - Menú "Verificar certificado" → pega el código único → **"Certificado válido"**.
   - *Resalta:* cualquier persona puede verificar sin autenticarse — URL pública.

> Punto fuerte: *"Todo este flujo — desde la inscripción hasta la verificación del certificado — genera logs, métricas y trazas correlacionadas. Lo demostramos en la sección 5."*

---

## 1B. Búsqueda semántica: cómo funciona y qué consultas usar

**Objetivo:** explicar RF-30 y ADR-07 con ejemplos concretos que siempre funcionan.

### Consultas curadas (siempre devuelven resultados)

La búsqueda semántica tiene un mapa determinista en `backend/app/infrastructure/curated_search.py` que garantiza resultados reproducibles sin depender de OpenAI:

| Query | Devuelve eventos con títulos |
|-------|------------------------------|
| `inteligencia artificial` / `ia` / `machine learning` / `deep learning` / `nlp` | Inteligencia Artificial, Deep Learning, Procesamiento de Lenguaje Natural, Bases de Datos Vectoriales |
| `ciberseguridad` / `seguridad` / `hacking` / `privacidad` | Ciberseguridad, Criptografía, Protección de Datos |
| `salud` / `medicina` / `telemedicina` / `bioetica` | Salud Pública, Telemedicina, Bioética |

### Cómo demostrarlo paso a paso

1. Sin búsqueda semántica, busca `ia` → probablemente cero resultados (búsqueda textual exacta).
2. Activa **"Búsqueda semántica"** y busca `ia` → aparecen 4 eventos de inteligencia artificial.
3. Busca `ciberseguridad` → aparecen eventos de Criptografía y Protección de Datos aunque esas palabras no estén en la query.
4. Busca `medicina` → aparecen eventos de Telemedicina y Bioética.

### Verificación directa por API (Swagger o curl)

```bash
# Sin semántica — busca literalmente "ia"
curl "http://localhost:8000/search?q=ia&semantic=false"

# Con semántica — activa el mapa curado
curl "http://localhost:8000/search?q=ia&semantic=true"

# Otro ejemplo
curl "http://localhost:8000/search?q=medicina&semantic=true"
```

### Qué decir al profesor

> *"Con `EMBEDDING_PROVIDER=fake` usamos un mapa curado determinista — ideal para demo y para CI (no depende de API key). Si cambiamos a `EMBEDDING_PROVIDER=openai` en el `.env` y reiniciamos, el sistema genera embeddings reales con `text-embedding-3-small` y los almacena en la columna `vector(384)` de PostgreSQL con pgvector (ADR-07). El código del servicio no cambia — solo la configuración del adaptador."*

---

## 2. Flujo del organizador/admin: crear y operar un evento

**Objetivo:** ciclo de vida del evento y aprobación institucional (CU-02, CU-07). Cubre RF-05/06/09/11/12/14/24/25/26/29.

**Pasos (organizador):**

1. **Login `organizador1@javeriana.edu.co`** → **Organizador** → **"Crear evento"**:
   - Completa: título, descripción, modalidad, fechas, capacidad, categoría.
   - Pulsa **"Crear (borrador)"**.
   - *Resalta:* RF-05 — el evento nace en estado `borrador`; el dominio valida fechas (fin > inicio) y capacidad > 0 mediante Value Objects. El patrón **State** controla las transiciones.

2. **Ciclo de vida del estado** (patrón State):
   - Opción A: **"Publicar"** directo → `borrador → publicado`.
   - Opción B: **"Enviar a aprobación"** → `borrador → pendiente` (requiere aprobación del admin — CU-07).
   - *Resalta:* no se puede saltar estados ni ir hacia atrás sin pasar por los estados intermedios.

3. **Gestionar el evento** (RF-11, RF-12, RF-14):
   - **Inscritos + "Exportar CSV"** → RF-11.
   - **Métricas**: confirmados, capacidad, % ocupación, asistencias → RF-14.
   - **"Comunicación masiva"**: escribe asunto + mensaje + elige segmento (todos/confirmados) → **"Enviar"** → responde `202 Accepted` al instante → el worker procesa en segundo plano → RF-12, RN-08.
   - **"Generar certificados en lote"** → encola la generación para todos los asistentes → RF-13.

4. **Conflicto de sesiones** (RF-09):
   - Agrega una sesión al evento en un horario.
   - Intenta agregar otra sesión en el mismo track con horario solapado → devuelve **409 Conflict**.
   - *Resalta:* validación de agenda a nivel de dominio.

**Pasos (admin, si usaste "Enviar a aprobación"):**

5. **Login `admin@javeriana.edu.co`** → **Administración** → **"Eventos pendientes"**:
   - Escribe un comentario de revisión (≥20 caracteres) → **"Aprobar"** → pasa a `publicado` (RF-24, CU-07).
   - O **"Rechazar"** con comentario → vuelve a `borrador` para corrección.

6. **Panel de administración** (RF-25, RF-26, RF-29):
   - **Dashboard institucional**: eventos por facultad, inscripciones totales, tasa de confirmación.
   - **Gestión de usuarios y roles**: cambia rol de un usuario (asistente → organizador).
   - **Auditoría reciente**: muestra todas las acciones críticas con actor, entidad, resultado y `trace_id`.

> *"Al publicar el evento, si `EMBEDDING_PROVIDER=openai` está configurado, el sistema genera automáticamente el embedding del título+descripción y lo guarda en la columna `vector(384)` — por eso la búsqueda semántica funciona para eventos nuevos."*

---

## 3. Flujos técnicos para mostrar

### 3.1 Pago (mock) con webhook idempotente — RF-04, RN-06, ADR-03

1. Como asistente, entra a un evento **de pago** → **"Inscribirse y pagar"** → redirige a la pasarela simulada (`/pay`).
2. Pulsa **"Pagar (aprobar)"** → el webhook confirma el pago → inscripción pasa a `confirmada`.
3. *Resalta:*
   - El adaptador mock simula exactamente la interfaz de un proveedor real.
   - Cambiar a un proveedor real es solo cambiar `PAYMENT_PROVIDER=real` en `.env` — el servicio de negocio no se modifica (Factory + Adapter, ADR-03).
   - La idempotencia del webhook evita doble cobro: el mismo `idempotency_key` procesado dos veces solo confirma una vez (RN-06).

```bash
# Simular webhook directo por curl (idempotente: segunda llamada no crea duplicado)
curl -X POST http://localhost:8000/enrollments/webhook \
  -H "Content-Type: application/json" \
  -d '{"idempotency_key": "test-key-123", "status": "approved", "enrollment_id": "<uuid>"}'
```

### 3.2 Concurrencia sin sobreventa — RNF-08, RN-01, ADR-05 (el punto técnico más fuerte)

```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm api-test \
  sh -c "alembic upgrade head && pytest tests/integration/test_concurrency.py -v"
```

**Resultado esperado:** 50 inscripciones simultáneas al último cupo → **1 confirmada, 49 con 409, 0 sobreventa**.

*Resalta:* garantizado por `SELECT … FOR NO KEY UPDATE` en PostgreSQL — sin locks de aplicación, sin Redis, sin estado compartido entre workers. La base de datos es el árbitro.

### 3.3 Seguridad RBAC — RNF-12, E5 del SAD

```bash
# Como asistente, intenta acceder al panel de admin
curl -H "Authorization: Bearer <token_asistente>" http://localhost:8000/admin/dashboard
# -> 403 Forbidden
```

- En la SPA: loguéate como `asistente1@` e intenta navegar a `/admin` → **403**.
- *Resalta:* la validación es server-side — la UI puede ocultarlo pero el API lo rechaza siempre.
- El intento queda auditado como `access_denied` en la tabla de auditoría y en los logs como `WARNING: regla de negocio: forbidden`.
- Demuéstralo: loguéate como `admin@` → Auditoría → ves el intento denegado con el `trace_id`.

### 3.4 Auditoría inmutable — RF-29, RN-07, ADR-10

```bash
# Intenta borrar la auditoría desde psql
docker compose exec postgres psql -U pgea_app_user -d pgea \
  -c "DELETE FROM audit_log;"
# -> ERROR 42501: permission denied — audit_log es append-only
```

*Resalta:* la inmutabilidad está garantizada por un **trigger de base de datos** — no por código de aplicación. Aplica incluso al usuario dueño de la BD. Defensa en profundidad (ADR-10).

### 3.5 Privacidad Ley 1581 — RNF-10, RN-07

1. Como `asistente1@` → **"Mis datos"** → consulta su información personal.
   - *El acceso queda auditado automáticamente en `audit_log` como acceso a PII.*
2. Pulsa **"Solicitar supresión de datos"** → el sistema **anonimiza** (no borra): el nombre se reemplaza por un hash, el email por uno ficticio.
   - *Resalta:* se conserva la trazabilidad de inscripciones y certificados sin PII identificable — cumple Ley 1581 (RN-07).
3. Como `admin@` → `GET /admin/pii-access` → muestra el log de todos los accesos a datos personales.

### 3.6 Modificabilidad: cambiar proveedor sin tocar código — RNF-15, E6

```bash
# Cambiar proveedor de correo de mock a smtp
sed -i 's/EMAIL_PROVIDER=mock/EMAIL_PROVIDER=smtp/' .env
docker compose up -d api worker
# -> el adaptador SMTP queda activo; ningún servicio de negocio cambió

# Volver a mock
sed -i 's/EMAIL_PROVIDER=smtp/EMAIL_PROVIDER=mock/' .env
docker compose up -d api worker
```

*Resalta:* Factory Method + Adapter (ADR-03). El mismo patrón aplica para `OAUTH_PROVIDER`, `PAYMENT_PROVIDER` y `EMBEDDING_PROVIDER` — todos intercambiables por configuración.

### 3.7 Exportar evento a calendario — RF-08

```bash
curl http://localhost:8000/events/<event_id>/calendar.ics
```

Descarga un archivo `.ics` compatible con Google Calendar, Outlook y Apple Calendar.

---

## 4. Pruebas de volumetría (Locust) — RNF-06/07/08/17/18

```bash
# Escenarios normales: catálogo (50 VUs, 1 min) + inscripción (20 VUs, 1 min)
make load

# Escenarios exigentes: spike 200 VUs + stress mixto 100 VUs
make load-stress
```

Los reportes HTML quedan en `backend/tests/load/reports/`:
- `catalog_p95.html` — catálogo bajo carga típica
- `enroll_p95.html` — inscripción bajo carga típica
- `spike_catalog.html` — pico súbito 10 → 200 → 10 VUs
- `stress_mixed.html` — tráfico mixto realista a 100 VUs

**Qué decir:**
- Dentro del requisito el sistema cumple el SLO: catálogo p95 ≤ 500 ms a 50 VUs, inscripción p95 ≤ 2 s a 20 VUs.
- Al cuadruplicar la carga (200 VUs) la latencia sube pero **sin errores** — degradación elegante, no caída.
- El test de pico (`spike_catalog`) demuestra que el sistema absorbe una ráfaga repentina y se recupera (RNF-09).
- **Mientras corren**, muestra Grafana en vivo: Rate, Errors y Duration se mueven en tiempo real.

---

## 5. Observabilidad — el eje del proyecto (RNF-01..05, CU-06)

> Este es el cierre de oro de la demo: muestra que cada acción es diagnosticable de extremo a extremo.

### 5.1 Señales RED en Grafana (Prometheus)

Grafana → **Dashboards → PGEA — RED + SLO**:

- **Rate**: requests/s por ruta — `GET /events`, `POST /enrollments/*/register`, etc.
- **Errors**: tasa de 5xx — debe ser 0% en condiciones normales.
- **Duration**: p50/p95/p99 por endpoint.
- **SLO en verde**: "Catálogo p95 ≤ 500 ms" e "Inscripción p95 ≤ 2 s".
- **Métricas de negocio**: `enrollment_queue_size`, `notification_sent_total`, `webhook_processed_total`, generación de certificados.

Genera tráfico navegando la SPA o con `make load` y muestra los paneles actualizándose en vivo.

### 5.2 Correlación log → traza: diagnóstico en ≤ 5 min (CU-06)

1. En la SPA, inscríbete en un evento. En **DevTools → Network**, abre la respuesta del endpoint `register` y copia la cabecera **`X-Trace-Id`**.
   - Alternativa: provoca una inscripción duplicada — el toast de error muestra el `trace_id`.

2. Grafana → **Explore → fuente: Loki** → consulta:
   ```
   {service="pgea-api"} |= "<trace_id_copiado>"
   ```
   → aparece el log JSON de esa petición con `route`, `status_code`, `duration_ms`, `user_id`.

3. En ese log, expande y haz clic en el campo **`trace_id`** (link derivado hacia Tempo) → muestra la **traza distribuida**:
   - Span HTTP raíz (`POST /enrollments/{id}/register`)
   - Span de negocio `enrollment.reserve_capacity`
   - Spans de consultas a PostgreSQL (asyncpg)

4. Cierra el círculo:
   > *"Con un solo `trace_id` reconstruyo qué endpoint se invocó, cuánto tardó cada paso, qué consultas SQL ejecutó y qué usuario lo hizo — el criterio del SAD: causa raíz identificable en ≤ 5 minutos."*

### 5.3 Niveles de log estructurados (RNF-01)

En `make logs` muestra los niveles en JSON:
- **INFO**: `Inscripción gratuita confirmada — user_id=… event_id=… duration_ms=12`
- **WARNING**: `regla de negocio: duplicate_registration — ya existe inscripción confirmada`
- **WARNING**: `regla de negocio: forbidden — rol asistente no puede acceder a /admin`
- **ERROR**: solo para 5xx — incluye stack trace y `trace_id`

### 5.4 Health checks y recuperación automática (RNF-04, RNF-09)

```bash
# Estado normal
curl -s http://localhost:8080/api/health/ready | python3 -m json.tool
# -> {"status": "ready", "checks": {"database": "ok", "queue": "ok", "email_adapter": "mock"}}

# Simula caída de la BD
docker compose stop postgres
curl -s http://localhost:8080/api/health/ready
# -> {"status": "degraded", "checks": {"database": "error: ..."}} + HTTP 503

# Recuperación automática
docker compose start postgres
# En 10-15s el healthcheck vuelve a "ready"
```

*Resalta:* `restart: always` en docker-compose — los contenedores se recuperan solos ante fallos (ADR-08).

### 5.5 Service Graph en Tempo (opcional)

Tempo → **Service Graph** → muestra el grafo `pgea-api → postgres` con métricas RED generadas a partir de spans. Útil para mostrar dependencias de servicios sin configuración adicional.

---

## 6. CI/CD con GitHub Actions + AWS Lightsail

**Objetivo:** mostrar que el pipeline de integración y despliegue continuo funciona de punta a punta.

### 6.1 Arquitectura del pipeline

```
push a `stage` → CI (lint+tests+build) → imagen :stage en GHCR → deploy SSH a PGEA-stage
push a `main`  → CI (lint+tests+build) → imagen :latest en GHCR → deploy SSH a PGEA-prod
```

**Instancias activas en AWS Lightsail:**
- **PGEA-stage** → http://13.220.166.163:8080 — recibe push de rama `stage`
- **PGEA-prod** → http://44.192.12.194:8080 — recibe push de rama `main`

### 6.2 Demo en vivo: commit vacío end-to-end

Este es el ejemplo más limpio para mostrar el pipeline completo sin cambiar código:

```bash
# 1. Disparar en stage
git checkout stage
git commit --allow-empty -m "chore: demo pipeline CI/CD stage"
git push origin stage
```

Monitorea en GitHub → Actions:
- Job **CI** (lint + tests + build + push imagen `:stage`) — ~3-4 min
- Job **Deploy Stage** (SSH a la VM, pull imagen, up -d, migraciones, health check) — ~30-60 s

```bash
# 2. Verificar que stage está actualizado
curl http://13.220.166.163:8080/api/health/ready
# -> {"status": "ready", "env": "stage"}
```

```bash
# 3. Promover a producción
git checkout main
git merge stage --no-edit
git push origin main
```

Monitorea los jobs **CI** y **Deploy Prod**:

```bash
# 4. Verificar prod
curl http://44.192.12.194:8080/api/health/ready
# -> {"status": "ready", "env": "prod"}
```

*Resalta:*
- El mismo código pasa por lint, type-check (mypy), pytest con ≥70% de cobertura, y smoke test de Locust antes de desplegarse.
- Las imágenes se publican en GHCR y las VMs solo hacen `docker pull` — no compilan en producción.
- Cada deploy aplica migraciones Alembic y verifica `/health/ready` antes de dar el deploy por exitoso.

### 6.3 Flujo de trabajo habitual (para el profesor)

```
feature/* → PR a stage → CI corre → merge → Deploy Stage automático
                                          → validar en http://13.220.166.163:8080
                                          → PR a main → Deploy Prod automático
                                                      → validar en http://44.192.12.194:8080
```

### 6.4 Rollback manual si algo falla

```bash
# En la VM, bajar y volver a la imagen anterior
ssh ubuntu@<host>
cd /opt/pgea
docker-compose -f docker-compose.yml -f infra/compose/docker-compose.prod.yml down
TAG=sha-<commit_anterior> docker-compose -f docker-compose.yml -f infra/compose/docker-compose.prod.yml up -d
```

---

## 7. Comandos de referencia rápida

```bash
# Stack local
make up                  # levanta todo
make down                # detiene (conserva datos)
make clean               # detiene y borra volúmenes
make logs                # sigue logs de api y worker
make ps                  # estado de contenedores
make seed                # datos sintéticos
make clean-loadtest      # limpia datos de pruebas de carga
make shell               # bash en el contenedor api
make psql                # cliente psql

# Calidad
make lint                # ruff + mypy
make test                # pytest con cobertura ≥70%

# Carga
make load                # escenarios normales (catalog_p95 + enroll_p95)
make load-stress         # escenarios exigentes (spike + stress_mixed)

# Migraciones
make migrate             # alembic upgrade head
make makemigration m="descripcion"  # nueva migración

# Búsqueda semántica por curl
curl "http://localhost:8000/search?q=inteligencia+artificial&semantic=true"
curl "http://localhost:8000/search?q=ciberseguridad&semantic=true"
curl "http://localhost:8000/search?q=medicina&semantic=true"

# Health checks AWS
curl http://13.220.166.163:8080/api/health/ready   # stage
curl http://44.192.12.194:8080/api/health/ready    # prod
```

---

## 8. Escenarios de integración entre herramientas — qué hacer y dónde mirarlo

> Esta sección es el corazón de la demo: muestra que las herramientas no son independientes sino que se complementan. Cada acción en el frontend o la API se puede rastrear en logs, métricas y trazas.

---

### 8.1 Inscripción en la SPA → ver la traza completa en Grafana

**Qué hacer:**
1. Abre la SPA y loguéate como `asistente1@javeriana.edu.co`.
2. Inscríbete en un evento gratuito.
3. En DevTools → Network, copia la cabecera `X-Trace-Id` de la respuesta.

**Qué mirar:**
- **Loki** → Explore → `{service="pgea-api"} |= "<trace_id>"` → log JSON con `route`, `status_code`, `duration_ms`, `user_id`, `event_id`.
- **Tempo** → haz clic en el `trace_id` dentro del log → traza con 3 spans: HTTP root, `enrollment.reserve_capacity`, queries asyncpg a PostgreSQL.
- **Prometheus / Grafana dashboard** → panel `enrollment_confirmed_total` sube en 1 · panel `enrollment_queue_size` sube (certificado encolado) y luego baja cuando el worker lo procesa.

> *"Una sola acción del usuario genera logs estructurados, una traza distribuida y métricas de negocio — todo correlacionado por el mismo `trace_id`."*

---

### 8.2 Inscripción duplicada → ver el WARNING en Loki y el 409 en Prometheus

**Qué hacer:**
1. Intenta inscribirte dos veces en el mismo evento (la segunda vez con el botón deshabilitado o directo por Swagger).
2. En Swagger: `POST /enrollments/{event_id}/register` dos veces con el mismo token.

**Qué mirar:**
- **Loki** → `{service="pgea-api"} |= "duplicate_registration"` → log en nivel `WARNING` con la razón de negocio.
- **Prometheus** → métrica `http_requests_total{status="409"}` incrementa.
- **Grafana dashboard** → panel Errors muestra el spike de 409 (no es un error del sistema, es una regla de negocio).
- **Tempo** → la traza muestra que el span `enrollment.reserve_capacity` terminó con excepción de negocio, no de infraestructura.

> *"Los 409 no son bugs — son reglas de negocio. Loki los registra como WARNING, no ERROR, para no contaminar las alertas."*

---

### 8.3 Prueba de volumetría → ver Grafana en vivo

**Qué hacer:**
```bash
make load   # catálogo 50 VUs + inscripción 20 VUs durante 1 min
```

**Qué mirar simultáneamente en Grafana:**
- **Panel Rate** → sube a ~50-100 req/s en `GET /events`.
- **Panel Duration p95** → se mantiene ≤ 500 ms para catálogo y ≤ 2 s para inscripción (SLO en verde).
- **Panel Errors** → debe mantenerse en 0% (ningún 5xx).
- **Panel `enrollment_queue_size`** → sube durante la carga (certificados encolados) y el worker los va procesando.
- **Loki** → `{service="pgea-api"} | json | duration_ms > 300` → filtra solo requests lentos en tiempo real.

> *"El sistema cumple el SLO bajo carga nominal. Ahora vamos a cuadruplicarla."*

```bash
make load-stress   # spike 200 VUs + stress mixto 100 VUs
```
- **Panel Rate** → sube bruscamente a 200+ req/s.
- **Panel Duration** → p95 sube pero sin llegar a timeout.
- **Panel Errors** → sigue en 0% — degradación elegante, no caída.

---

### 8.4 Caída de la BD → ver degradación en health check y Grafana

**Qué hacer:**
```bash
docker compose stop postgres
curl http://localhost:8080/api/health/ready
```

**Qué mirar:**
- **Health check** → responde `{"status": "degraded", "checks": {"database": "error"}}` con HTTP 503.
- **Grafana dashboard** → panel Errors sube (503 en `/health/ready`).
- **Loki** → `{service="pgea-api"} | json | level="error"` → aparecen los errores de conexión a PostgreSQL con stack trace y `trace_id`.
- **Prometheus** → alerta `DatabaseDown` se activa (si está configurada).

```bash
docker compose start postgres
# En 10-15s vuelve a "ready"
```
- **Health check** → vuelve a `{"status": "ready"}`.
- **Grafana** → los errores desaparecen, Rate vuelve a 0.

> *"El sistema detecta la caída, la reporta en el health check y se recupera automáticamente — sin intervención manual (`restart: always`, ADR-08)."*

---

### 8.5 RBAC: acceso denegado → ver auditoría y log

**Qué hacer:**
1. Loguéate como `asistente1@javeriana.edu.co`.
2. Intenta acceder a `/admin` en la SPA o directamente en Swagger: `GET /admin/dashboard` con el token del asistente.

**Qué mirar:**
- **Loki** → `{service="pgea-api"} |= "forbidden"` → log `WARNING` con `user_id`, `role=attendee`, `route=/admin/dashboard`.
- **Prometheus** → `http_requests_total{status="403"}` incrementa.
- **SPA como admin** → Administración → Auditoría → aparece la entrada `access_denied` con el `trace_id` del intento.
- **Tempo** → la traza muestra que el request terminó en el middleware de RBAC antes de llegar al servicio de negocio.

> *"El rechazo no solo devuelve 403 — queda auditado con actor, recurso y traza. Eso es lo que diferencia seguridad real de seguridad cosmética."*

---

### 8.6 Directamente en Swagger → ver efecto en Grafana y Loki

**Qué hacer:**
1. Abre http://localhost:8000/docs (o el de stage/prod).
2. Autentícate con `POST /auth/login` → copia el `access_token`.
3. Ejecuta `GET /events` varias veces seguidas.
4. Ejecuta `GET /search?q=inteligencia+artificial&semantic=true`.
5. Ejecuta `POST /enrollments/{event_id}/register`.

**Qué mirar:**
- **Grafana dashboard** → cada request en Swagger aparece en el panel Rate en tiempo real.
- **Loki** → `{service="pgea-api"}` → cada llamada genera un log JSON con método, ruta, status y duración.
- **Tempo** → cada request tiene su propia traza navegable.
- **Prometheus** → `http_requests_total` y `http_request_duration_seconds` se actualizan por endpoint.

> *"Swagger no es solo documentación — es una herramienta de prueba que alimenta el mismo pipeline de observabilidad que el frontend."*

---

### 8.7 Generación de certificado → ver el worker en acción

**Qué hacer:**
1. Completa el flujo: inscripción → asistencia → solicitar certificado.
2. En otra terminal, corre `make logs` o:
```bash
docker compose logs -f worker
```

**Qué mirar:**
- **Logs del worker** → aparece `INFO: Procesando job certificate_generation — enrollment_id=…` y luego `INFO: Certificado generado en Xms`.
- **Loki** → `{service="pgea-worker"}` → los mismos logs estructurados del worker.
- **Grafana** → panel `certificate_generated_total` sube en 1 · panel `enrollment_queue_size` baja (job procesado).
- **Tempo** → la traza del `POST /certificates/request` muestra el span de encolado; el worker genera su propia traza con el span de generación del PDF.

> *"El API responde inmediatamente al encolar. El worker procesa en segundo plano. Ambos son trazables por separado pero correlacionados por el `enrollment_id`."*

---

### 8.8 Búsqueda semántica → comparar con y sin semántica en Swagger

**Qué hacer en Swagger (`/docs`):**
```
GET /search?q=ia&semantic=false   → 0 resultados (búsqueda textual exacta)
GET /search?q=ia&semantic=true    → 4 resultados (mapa curado: IA, Deep Learning, NLP, pgvector)
GET /search?q=medicina&semantic=true → eventos de Telemedicina y Bioética
```

**Qué mirar:**
- **Loki** → `{service="pgea-api"} |= "/search"` → el log incluye `semantic=true`, `strategy=curated`, `results=4`.
- **Grafana** → el panel Rate muestra los requests a `/search` diferenciados.
- **Tempo** → la traza de búsqueda semántica tiene un span adicional `curated_search.match` que no aparece en la textual.

> *"La diferencia entre búsqueda textual y semántica es visible no solo en los resultados sino en la traza — el span `curated_search.match` solo aparece cuando se activa la semántica."*

---

### 8.9 CI/CD en vivo → push y ver el deploy en GitHub Actions

**Qué hacer:**
```bash
git checkout stage
git commit --allow-empty -m "chore: demo CI/CD en vivo"
git push origin stage
```

**Qué mirar:**
- **GitHub Actions** → aparece el workflow CI corriendo: lint → tests → build → push a GHCR.
- **GitHub Actions** → Deploy Stage empieza cuando CI termina: SSH → pull → up -d → migraciones → health check.
- **Health check stage** → `curl http://13.220.166.163:8080/api/health/ready` → responde `ready` al finalizar el deploy.
- **Grafana stage** → el panel muestra el restart del contenedor (breve caída de métricas y recuperación).

Luego promueve a prod:
```bash
git checkout main && git merge stage --no-edit && git push origin main
```
- **Deploy Prod** → mismo flujo pero sobre `44.192.12.194`.
- **Health check prod** → `curl http://44.192.12.194:8080/api/health/ready`.

> *"El código pasa por lint, type-check, tests con ≥70% de cobertura y smoke test de Locust antes de llegar a producción. Todo automático desde un `git push`."*

---

## Resumen de "qué prueba cada cosa" (para responder al profesor)

| Demostración | Requisitos que evidencia |
|---|---|
| Flujo estudiante — inscripción → certificado (§1) | RF-01/02/03/13/18/19/21/30, RN-05, CU-01/04 |
| Búsqueda semántica curada + pgvector (§1B) | RF-30, ADR-07 |
| Flujo organizador/admin — evento + aprobación (§2) | RF-05/06/09/11/12/14/24/25/26/29, CU-02/07 |
| Pago mock + webhook idempotente (§3.1) | RF-04, RN-06, ADR-03 |
| Concurrencia sin sobreventa (§3.2) | RNF-08, RN-01, ADR-05 |
| Seguridad RBAC server-side (§3.3) | RNF-12, E5 |
| Auditoría inmutable por trigger BD (§3.4) | RF-29, RN-07, ADR-10 |
| Privacidad Ley 1581 — supresión (§3.5) | RNF-10, RN-07 |
| Modificabilidad por configuración (§3.6) | RNF-15/16, ADR-03 |
| Exportar calendario .ics (§3.7) | RF-08 |
| Volumetría Locust — 4 escenarios (§4) | RNF-06/07/08/17/18 |
| Observabilidad RED + trazas correlacionadas (§5) | RNF-01/02/03/04/05/09, RN-10, CU-06 |
| CI/CD commit vacío end-to-end (§6) | ADR-08, ADR-11 |
