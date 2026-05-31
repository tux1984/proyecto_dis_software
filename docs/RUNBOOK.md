# RUNBOOK operacional — PGEA

Guía de operación y diagnóstico. Complementa el SAD (§6.4, §10) y soporta el caso de uso **CU-06
(Supervisión operacional y diagnóstico)**.

## 1. Diagnóstico de un incidente por `trace_id` (≤ 5 min)

1. Obtén el `trace_id` de la respuesta fallida (cabecera `X-Trace-Id`) o del reporte del usuario.
2. **Loki** (Grafana → Explore): `{service="pgea-api"} |= "<trace_id>"` → log estructurado con `route`, `status`, `duration_ms`, `user_id`.
3. Desde el campo `trace_id` del log, salta a **Tempo**: reconstruye la cadena de spans (HTTP → servicio → BD/cola) y localiza el componente que falló.
4. Valida el impacto en **Grafana** (dashboard *PGEA — RED + SLO*): elevación de `error_rate` o p95.

## 2. SLI / SLO (SAD §10.2)

| Servicio | SLI | SLO |
|---|---|---|
| Catálogo de eventos | p95 latencia `GET /events` | ≤ 500 ms (RNF-06) |
| Inscripción gratuita | p95 latencia `POST /enrollments/*/register` | ≤ 2 s (RNF-07) |
| Webhooks de pago | tasa de procesamiento exitoso | ≥ 99 % (ventana 24 h) |
| Notificaciones | tiempo de procesamiento por job | p95 ≤ 30 s |
| API global | tasa de errores 5xx | ≤ 0.5 % (ventana 1 h) |

Alertas (Prometheus, `infra/prometheus/alerts.yml`): `error_rate > 1%` (5m), `p95 catálogo > 500ms`,
`enrollment_queue_size > 1000`, `webhook_processed_total{result="failure"} > 5` (5m).

## 3. Recuperación ante fallo de dependencia (RNF-09)

- `GET /health/ready` reporta el estado por dependencia (BD, cola, adaptadores). Detección ≤ 10 s.
- Política `restart: always` en todos los contenedores → recuperación ≤ 30 s.
- Simulacro de demo: `docker compose stop postgres` → `/health/ready` pasa a `degraded` (503); `docker compose start postgres` → vuelve a `ready`.

## 4. Operación de la cola asíncrona

```bash
# tamaño de la cola (gauge) y jobs muertos (DLQ)
docker compose exec postgres psql -U pgea_app_user -d pgea -c \
  "SELECT status, count(*) FROM queued_jobs GROUP BY status;"
docker compose exec postgres psql -U pgea_app_user -d pgea -c "SELECT count(*) FROM failed_jobs;"
docker compose logs -f worker        # procesamiento (reintentos con backoff)
```

## 5. Respaldo y recuperación (SAD §6.4.3)

```bash
# Backup manual (antes de demo / deploy)
docker compose exec -T postgres pg_dump -U pgea_app_user pgea > backup_$(date +%Y%m%d).sql
# Restauración
cat backup_YYYYMMDD.sql | docker compose exec -T postgres psql -U pgea_app_user -d pgea
```
- **RTO** objetivo: ≤ 2 h (restauración desde snapshot). **RPO**: ≤ 24 h (pg_dump diario).
- Volúmenes persistentes: `pgdata` (crítico), `grafanadata`, `lokidata`, `tempodata` (regenerables).

## 6. Verificación de auditoría inmutable (ADR-10)

```bash
docker compose exec postgres psql -U pgea_app_user -d pgea -c "DELETE FROM audit_log;"  # -> ERROR 42501 (append-only)
```

## 7. Cambiar proveedor de un adaptador (E6, modificabilidad)

Edita `.env` (p. ej. `EMAIL_PROVIDER=smtp` + credenciales SMTP) y `docker compose up -d api worker`.
No requiere cambios de código (Factory Method + Adapter).
