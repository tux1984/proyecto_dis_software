# PGEA — Guion de demostración

Guía paso a paso para presentar la plataforma. Cada sección indica **qué hacer**, **qué resaltar** y a
**qué requisito** del SRS/SAD corresponde, para que puedas demostrar cada punto cuando el profesor lo pida.

**Accesos:** SPA → http://localhost:8080 · Grafana → http://localhost:3000 (admin/admin) · API/Swagger → http://localhost:8000/docs
**Login (SSO mock = el correo):** `admin@`, `organizador1@`, `asistente1@`, `ponente1@` `javeriana.edu.co`.

---

## 0. Preparación (5 min antes de la demo)
```bash
cd <proyecto>
make up                 # stack arriba (api, worker, postgres, nginx, prometheus, grafana, loki, tempo)
make seed               # datos sintéticos (si la BD está vacía)
make clean-loadtest     # quita inscritos "Load…" de pruebas de carga (deja la demo limpia)
```
- Verifica `make ps` → todo *healthy*. Abre 3 pestañas: **SPA**, **Grafana** (deja el dashboard *PGEA — RED + SLO* abierto), y una terminal para `make logs`.
- Ten a mano las DevTools del navegador (pestaña **Network**) para mostrar la cabecera `X-Trace-Id`.

> Mensaje de apertura: *"PGEA es un monolito modular en FastAPI con Clean Architecture + Hexagonal Ports & Adapters, PostgreSQL+pgvector, frontend Vue, y observabilidad completa (OpenTelemetry+Prometheus+Grafana+Loki+Tempo). El eje del proyecto es la observabilidad: todo flujo crítico emite logs, métricas y trazas correlacionadas por `trace_id`."*

---

## 1. Flujo del estudiante: inscripción → asistencia → certificado → verificación
**Objetivo:** mostrar el ciclo completo del asistente (CU-01, CU-04). Cubre RF-01/02/03/18/19/21, RN-05.

**Pasos:**
1. **Login** como `asistente1@javeriana.edu.co` (botón "Asistente").
2. **Catálogo**: aplica filtros (modalidad/categoría/orden). *Resalta:* RF-01 (filtros combinables) y RF-02 (orden).
3. Activa el check **"Búsqueda semántica"** y busca `inteligencia artificial`. *Resalta:* RF-30 — devuelve eventos **relacionados conceptualmente sin las palabras exactas** (Deep Learning, Procesamiento de Lenguaje Natural, Bases de Datos Vectoriales).
   - Consultas curadas para la demo (devuelven solo lo relacionado): **`inteligencia artificial`**, **`ciberseguridad`**, **`salud`** (o `medicina`). Otras consultas caen a búsqueda textual relevante. El mapa está en `backend/app/infrastructure/curated_search.py` (fácil de ampliar). Si se configura `EMBEDDING_PROVIDER=openai` con API key, usa pgvector real como respaldo (ADR-07).
4. Entra a un evento → **"Inscribirme"** → queda **confirmada**. *Resalta:* RF-03 e inscripción atómica (RN-01).
5. (Cambia a) **Login `organizador1@`** → menú **Organizador** → en "Mis eventos" pulsa **"Gestionar"** el evento → en la tabla de inscritos pulsa **"asistió"** junto a Asistente 1. *Resalta:* RF-19 (registro de asistencia); intentar marcar a alguien sin inscripción confirmada da 422.
6. (Vuelve a) **Login `asistente1@`** → **"Mis inscripciones"** (muestra nombres de eventos, fecha, estado) → en ese evento pulsa **"Solicitar certificado"**. *Resalta:* RN-05 — solo se emite con asistencia registrada; sin asistencia respondería 403.
7. Menú **"Certificados"** → espera 1-3 s (lo genera el *worker* asíncrono) → **"Descargar PDF"** (PDF con nombre, evento, fecha y **código único**). *Resalta:* RF-13/21 + procesamiento asíncrono (ADR-09).
8. Menú **"Verificar certificado"** → pega el código → **"✅ Certificado válido"**. *Resalta:* verificación pública con código único (RF-21).

> Punto fuerte: *"El PDF lo renderiza el worker en segundo plano (cola en PostgreSQL con `FOR UPDATE SKIP LOCKED`); el API solo encola y responde de inmediato."*

---

## 2. Flujo del organizador/admin: crear y operar un evento
**Objetivo:** ciclo de vida del evento y aprobación institucional (CU-02, CU-07). Cubre RF-05/06/09/11/12/14/24/25/26.

**Pasos (organizador):**
1. **Login `organizador1@`** → **Organizador** → **"Crear evento"**: título, descripción, modalidad, fechas, capacidad, categoría → **"Crear (borrador)"**. *Resalta:* RF-05 (nace en `borrador`); el dominio valida fechas/capacidad (Value Objects + State).
2. En "Mis eventos", sobre el nuevo evento: **"Enviar a aprobación"** (si quieres mostrar CU-07) o **"Publicar"** directo. *Resalta:* máquina de estados (patrón **State**) borrador → pendiente/publicado.
3. **"Gestionar"** el evento → demuestra:
   - **Inscritos + "Exportar CSV"** (RF-11).
   - **Métricas del evento**: confirmados, capacidad, ocupación, asistencias (RF-14).
   - **"Comunicación masiva"**: asunto + mensaje + segmento → **"Enviar (asíncrono)"** → responde 202 al instante (RF-12, RN-08). *Resalta:* no bloquea; el worker procesa los correos.
   - **"Generar certificados (lote)"** (RF-13).
4. Agrega una **sesión** a la agenda (si tienes el endpoint a mano) — dos sesiones que se solapen en el mismo track dan 409 (RF-09).

**Pasos (admin, si usaste "Enviar a aprobación"):**
5. **Login `admin@`** → **Administración** → **"Eventos pendientes"** → escribe un comentario (≥20 caracteres) → **"Aprobar"** → pasa a `publicado` (RF-24, CU-07).
6. En el mismo panel: **dashboard institucional** (eventos por facultad, inscripciones, confirmadas — RF-25), **usuarios y roles** (cambiar rol — RF-26), **auditoría reciente** (RF-29) y botón **Grafana**.

> Al publicar, *"el sistema genera el embedding del evento (título+descripción) y lo guarda en la columna `vector(384)` — por eso la búsqueda semántica funciona."*

---

## 3. Otros flujos importantes para mostrar

### 3.1 Pago (mock) con webhook idempotente — RF-04, RN-06, ADR-03
- Como asistente, entra a un evento **de pago** → **"Inscribirse y pagar"** → te lleva a la **pasarela simulada** (`/pay`).
- Pulsa **"Pagar (aprobar)"** → el webhook confirma → inscripción `confirmada`. *Resalta:* el adaptador mock simula la pasarela; el cambio a un proveedor real es solo configuración (Factory + Adapter). La idempotencia evita doble cobro (mismo `idempotency_key`).

### 3.2 Concurrencia sin sobreventa — RNF-08, RN-01, ADR-05 (¡el punto técnico más fuerte!)
```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml run --rm api-test \
  sh -c "alembic upgrade head && pytest tests/integration/test_concurrency.py -v"
```
*Resalta:* 50 inscripciones simultáneas al último cupo → **1 confirmada, 49 × 409, 0 sobreventa**, gracias a `SELECT … FOR NO KEY UPDATE`.

### 3.3 Seguridad RBAC — RNF-12 (E5 del SAD)
- Como **asistente**, intenta entrar a **Administración** (o `curl` a `/api/admin/dashboard`): **403**. *Resalta:* validación de rol en servidor + **el intento queda auditado** (`access_denied`). Muéstralo en Auditoría (admin) o en `make logs` (`WARNING regla de negocio: forbidden`).

### 3.4 Auditoría inmutable — RF-29, RN-07, ADR-10
```bash
docker compose exec postgres psql -U pgea_app_user -d pgea -c "DELETE FROM audit_log;"
# -> ERROR 42501: audit_log es append-only (ADR-10)
```
*Resalta:* inmutabilidad garantizada por trigger de BD (defensa en profundidad, aplica incluso al dueño).

### 3.5 Privacidad Ley 1581 — RNF-10, RN-07
- Como asistente: **"Mis datos"** → consulta de datos (queda auditado el acceso a PII) → **"Solicitar supresión"** → anonimiza conservando trazabilidad. *Resalta:* el admin puede ver el **log de acceso a PII** (`/admin/pii-access`).

### 3.6 Modificabilidad: cambiar de proveedor sin tocar código — RNF-15, E6
```bash
# Cambia el proveedor de correo en .env y reinicia: el adaptador se sustituye por configuración
sed -i 's/EMAIL_PROVIDER=mock/EMAIL_PROVIDER=smtp/' .env && docker compose up -d api worker
```
*Resalta:* Factory Method + Adapter; ningún servicio de negocio cambia. (Vuelve a `mock` después.)

---

## 4. Pruebas de volumetría (Locust)

```bash
# Escenarios del documento (RNF-06 catálogo, RNF-07 inscripción) con reporte HTML+CSV
make load
# Escenarios EXIGENTES (200 VUs escalonado, 100 VUs mixto, pico) — margen de capacidad
make load-stress
```
- Los reportes quedan en **`backend/tests/load/reports/*.html`** — ábrelos: traen gráficas de RPS, percentiles y distribución.
- **Mientras corren**, ten Grafana abierto (sección 5): verás moverse Rate/Errors/Duration en vivo.
- **Qué decir:** dentro del requisito el sistema cumple el SLO (catálogo p95 ≤ 500 ms con 50 VUs; inscripción p95 ≤ 2 s con 20 VUs). Al **cuadruplicar** la carga (200 VUs) la latencia sube pero **sin errores** — degradación elegante. (Detalle y tabla comparativa: `docs/ENTREGA_DEMO.md §7` y la comparación de tiempos.)

---

## 5. Observabilidad en Grafana (Prometheus + Loki + Tempo) — el eje del proyecto (RNF-01..05, CU-06)

> Este es el cierre de oro de la demo: muestra que cada acción es **diagnosticable de extremo a extremo**.

### 5.1 Las señales RED (Prometheus)
- Grafana → **Dashboards → PGEA — RED + SLO**. Explica los paneles:
  - **Rate** (req/s por ruta), **Errors** (tasa 5xx), **Duration** (p50/p95/p99) → método RED (RNF-02).
  - **SLO**: "Catálogo p95 ≤ 500 ms" e "Inscripción p95 ≤ 2 s" en verde.
  - **Negocio/async**: `enrollment_queue_size` (cola), `notification_sent_total`, `webhook_processed_total`, generación de certificados/embeddings.
- Genera tráfico (navega la SPA o corre `make load`) y muestra los paneles moverse en tiempo real.

### 5.2 Correlación por `trace_id` (Loki → Tempo) — diagnóstico en ≤ 5 min (CU-06)
1. En la SPA haz una acción (p. ej. inscríbete). En **DevTools → Network**, abre la respuesta de `register` y copia la cabecera **`X-Trace-Id`**. *(O provoca un error, p. ej. inscripción duplicada: el toast muestra el `trace_id`.)*
2. Grafana → **Explore → fuente Loki** → consulta: `{service="pgea-api"} |= "<trace_id>"` → aparece el **log JSON** de esa petición (con `route`, `status`, `duration_ms`, `user_id`).
3. En ese log, expande y haz clic en el campo **`trace_id`** (link derivado) → salta a **Tempo** y muestra la **traza**: span HTTP raíz + span de negocio `enrollment.reserve_capacity` + consultas a PostgreSQL (asyncpg). *Resalta:* RNF-03 (W3C trace context).
4. Cierra el círculo: *"con un solo `trace_id` reconstruyo qué endpoint se invocó, cuánto tardó, qué consultas hizo y qué usuario fue — el criterio del SAD: causa raíz en ≤ 5 min."*

### 5.3 Niveles de log claros (RNF-01)
- En `make logs` muestra los niveles: **INFO** (`Inscripción gratuita confirmada…`, `POST /enrollments/... -> 201`), **WARNING** con la razón de negocio (`regla de negocio: duplicate_registration — …`, `forbidden`), **ERROR** para 5xx. Todo en JSON correlacionado.

### 5.4 Health checks y recuperación (RNF-04, RNF-09)
```bash
curl -s http://localhost:8080/api/health/ready | python3 -m json.tool   # estado por dependencia
docker compose stop postgres        # simula caída de la BD
curl -s http://localhost:8080/api/health/ready                          # -> "degraded" (503)
docker compose start postgres                                           # se recupera (restart: always)
```
*Resalta:* detección de fallo de dependencia y recuperación automática.

### 5.5 (Opcional) Trazas como métricas
- En Tempo, abre **Service Graph** (Grafana genera métricas RED a partir de spans). Muestra el grafo de servicios api → postgres.

---

## 6. Paso a paso: llevar todo a otro computador → GitHub → AWS Lightsail

> Resumen ejecutable; el detalle completo está en `docs/ENTREGA_DEMO.md §4`. La convención del proyecto es:
> rama **`stage`** → instancia de **pruebas/validación** · rama **`main`** → instancia de **producción**.

### Paso 1 — Empaquetar y pasar el proyecto
```bash
# En este equipo (excluye artefactos pesados; el .env NO viaja)
cd /home/sfanchi && tar --exclude='projects/.git' --exclude='**/node_modules' \
  --exclude='**/__pycache__' --exclude='**/reports/*' -czf pgea.tgz projects/
# Copia pgea.tgz al otro equipo (USB/scp) y descomprime allí.
```
En el otro equipo instala **Docker + Docker Compose** y valida en local: `cp .env.example .env && make up && make seed && make test`.

### Paso 2 — Inicializar Git y subir a GitHub
```bash
cd projects
git init -b main
git add . && git commit -m "PGEA: POC inicial (backend, frontend, observabilidad, infra, tests, docs)"
git branch stage
# Crea el repo (requiere gh CLI autenticado) o créalo en la web y agrega el remoto:
gh repo create <org>/pgea --private --source=. --remote=origin
git push -u origin main
git push -u origin stage
```
> Flujo de trabajo: ramas `feature/*` → Pull Request a `stage` → PR a `main`. El CI corre en cada PR.

### Paso 3 — Configurar Secrets en GitHub
GitHub → repo → *Settings → Secrets and variables → Actions* → crea:
`OPENAI_API_KEY`, `LIGHTSAIL_STAGE_HOST`, `LIGHTSAIL_PROD_HOST`, `LIGHTSAIL_SSH_KEY`.
> Al hacer merge a `stage`/`main`, el CI construye imágenes, las publica en **GHCR** y dispara el deploy.

### Paso 4 — Crear las dos instancias AWS Lightsail
Crea 2 instancias **Ubuntu 22.04** (stage: 1 GB RAM · prod: 2 GB RAM). En **cada** una:
```bash
curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker ubuntu   # reconecta sesión SSH
sudo mkdir -p /opt/pgea && sudo chown ubuntu /opt/pgea && cd /opt/pgea
git clone https://github.com/<org>/pgea.git . && git checkout stage    # 'main' en la de producción
cp .env.example .env && chmod 600 .env
#   edita .env: POSTGRES_PASSWORD/JWT_SECRET fuertes, EMBEDDING_PROVIDER=openai, OPENAI_API_KEY,
#   GHCR_OWNER=<org>, TAG=stage|latest, ENV=stage|prod
docker compose -f docker-compose.yml -f infra/compose/docker-compose.stage.yml up -d   # (prod usa el override prod)
docker compose exec api alembic upgrade head
docker compose exec api python -m scripts.seed_data    # datos demo (opcional)
```

### Paso 5 — Producción: dominio y TLS
- Apunta tu dominio a la **IP pública** de la instancia prod; abre puertos 80/443 en el firewall de Lightsail.
- Edita `infra/nginx/nginx.prod.conf` (reemplaza `DOMAIN`) y emite el certificado **Let's Encrypt** (certbot).
- Verifica: `https://tu-dominio/` (SPA con TLS), `https://tu-dominio/api/health/ready`.

### Paso 6 — De aquí en adelante, automático
- `git push` a `stage` → despliega en la instancia de pruebas. `git push` a `main` → despliega en producción.
- Cada deploy hace `docker pull` desde GHCR, corre migraciones y verifica `/health/ready` (rollback si falla).

> Observabilidad en AWS: en stage Grafana queda en el puerto 3000; en prod **no se expone** públicamente — accede por **túnel SSH** (`ssh -L 3000:localhost:3000 ubuntu@<host_prod>`) y abre `http://localhost:3000`.

---

### Resumen de "qué prueba cada cosa" (para responder al profesor)
| Demostración | Requisitos que evidencia |
|---|---|
| Flujo estudiante (1) | RF-01/02/03/18/19/21/30, RN-05, CU-01/04 |
| Flujo organizador/admin (2) | RF-05/06/09/11/12/14/24/25/26/29, CU-02/07 |
| Pago mock (3.1) | RF-04, RN-06, ADR-03 |
| Concurrencia (3.2) | RNF-08, RN-01, ADR-05 |
| RBAC (3.3) | RNF-12 |
| Auditoría inmutable (3.4) | RF-29, RN-07, ADR-10 |
| Ley 1581 (3.5) | RNF-10, RN-07 |
| Modificabilidad (3.6) | RNF-15/16, ADR-03 |
| Volumetría (4) | RNF-06/07/08/17/18 |
| Observabilidad (5) | RNF-01/02/03/04/05/09, RN-10, CU-06 |
