# Entregable 6 (parte 1) — Observabilidad

Estado: implementado y verificado.

## 1. Decisión

- **Qué se loguea:** logs operativos (arranque, forward/deny/complete, errores de
  handler) de cada proceso (`main`, gateways, subagentes) como **JSON lines a stdout**
  (`meridian/logging_setup.py`), capturables por `docker logs` o cualquier recolector que
  el operador ya tenga (journald, un sidecar de Loki/Fluent Bit, etc.). Cada línea trae
  `ts`, `level`, `logger`, `message`, y campos extra (`correlation_id`, `message_id`,
  `status`) cuando aplica, para poder cruzarlos con `audit_log`.
- **Dónde:** local (stdout del contenedor) por defecto. **No se integra Prometheus/OTel
  ahora** -- no hay un requisito concreto que lo justifique todavía (nadie está operando
  esto en producción con SLOs que monitorear), y agregarlo sin ese contexto sería diseñar
  para un futuro hipotético. El formato JSON deja la puerta abierta: agregar un exporter
  más adelante es enchufar un colector, no rediseñar el logging.
- **Registro durable y consultable ("quién pidió qué y por qué se delegó")**: ya existe y
  es `audit_log` en Postgres (sección 5 del brief, entregable 1) -- los logs de arriba son
  para depuración operativa en caliente, `audit_log` es la fuente de verdad para
  auditoría/cumplimiento.
- **Retención:** `audit_log` no se purga solo. `meridianctl audit prune --older-than-days
  N` (default sugerido: 90 días) borra entradas más viejas que N días. Es una decisión que
  depende de los requisitos de negocio/cumplimiento de cada instalación (dato de negocio
  sensible, sección 5 del brief) -- Meridian no impone un período fijo, expone el comando
  para que cada operador lo agende (cron del propio SO, o un `cron_job` de Meridian que
  invoque `meridianctl` -- ver docs/design/0006-cron-gateway.md) con el período que le
  corresponda.

## 2. Qué cambió en el código

- Nuevo `src/meridian/logging_setup.py`: `configure(component)` reemplaza los
  `logging.basicConfig` sueltos que había en `main_agent/service.py`,
  `gateways/cron_gateway/service.py` y `subagents/worker_base.py`.
- `worker_base.py` ahora adjunta `correlation_id`/`message_id`/`status` como campos
  estructurados en sus logs de procesamiento y error.
- `repository.prune_audit_log(older_than_days)` + `meridianctl audit prune`.

## 3. Verificación hecha

Se reconstruyeron `main_agent` y `sample_subagent_a` y se confirmó que los logs salen
como JSON válido de una sola línea por evento, y que `meridianctl audit prune
--older-than-days 90` corre sin error contra el `audit_log` real de esta máquina.

## 4. Fuera de alcance

- Métricas (contadores/latencias) y tracing distribuido -- no hay caso de uso todavía que
  los necesite; se agregan cuando exista una razón concreta (ej. un SLO real que vigilar).
- `mock_gateway` (FastAPI/uvicorn) sigue con el logging por defecto de uvicorn -- no es un
  proceso de negocio (es un gateway de prueba del entregable 2), homogeneizarlo no aporta
  hoy.
