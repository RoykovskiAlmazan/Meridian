# Entregable 5 — Segundo gateway real: cron

Estado: implementado y verificado end-to-end en esta máquina.

## 1. Por qué cron primero

Se eligió un gateway de tipo cron (en vez de Telegram/WhatsApp) como segundo gateway real
porque no depende de ninguna cuenta/token de un tercero — permite validar el contrato
`gateway → main → subagente` con un caso 100% determinista y reproducible, sin fricción de
onboarding externo. El objetivo del entregable no es "sumar canales", es **probar que el
contrato interno (intent + procedencia + scopes) no necesitó romperse ni tener casos
especiales** para un gateway de naturaleza completamente distinta al mock HTTP (uno se
dispara por una request entrante, el otro por el paso del tiempo).

## 2. Qué se construyó

- Tabla `cron_jobs` (Postgres): cada fila es un disparo programado — `schedule` (expresión
  cron de 5 campos), `intent_type`, `subagent_ids`, `payload`, `enabled`, `last_run_at`.
  **Qué dispara, cuándo, y contra quién es 100% configuración**, no código — coherente con
  que Meridian no asume ningún dominio (puede ser "sincroniza cada hora" para un caso de
  inventario o "revisa papers nuevos cada lunes" para uno de investigación).
- `src/meridian/gateways/cron_gateway/service.py` — loop que cada 15s revisa los
  `cron_jobs` habilitados, calcula con `croniter` si ya tocaba dispararse desde su
  `last_run_at`, y si sí, construye un `TaskIntent` (con `meridian.messages.new_task_intent`,
  el mismo constructor que usa el mock gateway) y lo publica al bus
  (`redis_bus.publish_intent_to_main`, también el mismo código).
- `meridianctl cron create/list/enable/disable` — administración vía consola, igual que el
  resto de la plataforma.
- Un gateway de tipo `cron` se da de alta exactamente igual que cualquier otro
  (`meridianctl gateway create --type cron ...`) y se autoriza con la misma allowlist
  (`meridianctl allow set`) — **cero cambios en `main_agent/core.py` o `service.py`** para
  soportarlo.

## 3. Verificación hecha

Se creó un cron job de prueba (`* * * * *`, dispara cada minuto) apuntando al mismo
`sample_subagent_a` del entregable 2, con `intent_type: demo.heartbeat`. Con el contenedor
`cron_gateway` corriendo sin intervención manual, se confirmaron dos disparos automáticos
consecutivos en los logs:

```
cron_gateway  fired cron_job=... intent_type=demo.heartbeat correlation_id=b741c282-...
main          forwarded intent=... -> subagent=f7da0cbd-...
main          correlation_id=b741c282-... fan-in complete, published to gateway=05021ceb-...
subagent:f7da... processed intent=... status=success

cron_gateway  fired cron_job=... intent_type=demo.heartbeat correlation_id=2e296ff2-...
main          forwarded intent=... -> subagent=f7da0cbd-...
main          correlation_id=2e296ff2-... fan-in complete, published to gateway=05021ceb-...
subagent:f7da... processed intent=... status=success
```

Esto confirma la hipótesis del roadmap (sección 7 del brief): el contrato interno
sobrevivió a un segundo gateway de naturaleza distinta sin romperse ni necesitar casos
especiales en el `main`.

## 4. Cómo probarlo tú mismo

```bash
TENANT_ID=<tu tenant>
CRON_GW=$(meridianctl gateway create --tenant $TENANT_ID --type cron --name mi-scheduler --token unused-for-cron | ...)  # anota el id

meridianctl allow set --gateway <cron_gw_id> --subagent <subagent_id> --intents <tu_intent>
meridianctl cron create --tenant $TENANT_ID --gateway <cron_gw_id> --name mi-job \
  --schedule "*/5 * * * *" --intent-type <tu_intent> --subagents <subagent_id> \
  --payload '{"lo que quieras": true}'

# levantar el contenedor
docker compose -f docker/docker-compose.yml up -d --build cron_gateway

meridianctl cron list --tenant $TENANT_ID
meridianctl audit tail --tenant $TENANT_ID
```

## 5. Fuera de alcance / abierto

- Sin manejo de "catch-up" si el gateway estuvo caído más de un ciclo (hoy dispara una
  sola vez apenas detecta que ya tocaba, no re-dispara los ciclos perdidos) — aceptable
  para el MVP, a revisar si algún caso de uso real necesita disparos perdidos garantizados.
- Sin soporte de timezone explícito en `schedule` (usa UTC vía `croniter` sobre
  timestamps `timestamptz`) — si algún caso de uso necesita horario local, se agrega un
  campo `timezone` a `cron_jobs` cuando haga falta.
