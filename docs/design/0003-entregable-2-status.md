# Entregable 2 — estado y guía de prueba manual

Estado: primera versión funcional escrita y verificada con smoke tests locales
(compilación, imports en cadena, round-trip de `TaskIntent`/`TaskResult` contra los
JSON Schemas, `--help` de `meridianctl`). **No se ha corrido todavía el flujo end-to-end
con Docker/Postgres/Redis/Vault reales** — requiere Docker Desktop activo en esta máquina,
que no se asumió disponible al momento de escribir esto.

## 1. Qué quedó construido

- `src/meridian/messages.py` — construye y valida `TaskIntent`/`TaskResult` contra
  `schemas/*.schema.json`.
- `src/meridian/identity/` — conexión a Postgres (`db.py`) y CRUD de tenants, gateways,
  subagentes, allowlist y audit_log (`repository.py`), sobre el schema de
  `docker/init/postgres_schema.sql`.
- `src/meridian/secrets/vault_client.py` — `SecretRef` (`vault:<mount>/<path>#<field>`),
  escritura y resolución contra Vault (KV v2).
- `src/meridian/bus/redis_bus.py` — publish/consume sobre Redis Streams con consumer
  groups, convención de nombres de stream documentada en el propio archivo.
- `src/meridian/main_agent/` — `core.py` (autorización: recalcula scopes/allowlist contra
  Postgres, nunca confía en el mensaje entrante) y `service.py` (loop que consume intents,
  rutea con fan-out, y agrega resultados con fan-in en memoria de proceso).
- `src/meridian/gateways/mock_gateway/app.py` — FastAPI con `POST /intent` y
  `GET /result/{correlation_id}`.
- `src/meridian/subagents/` — `worker_base.py` genérico + `sample_subagent_a` y
  `sample_subagent_b` (hacen eco del payload, para validar el contrato sin lógica de
  dominio real).
- `src/meridian/cli/` — `meridianctl` con `dev up/down`, `config check`, `tenant`,
  `gateway`, `subagent`, `allow`, `audit tail`, `bus status`.
- `docker/docker-compose.yml` + Dockerfiles — postgres, redis, vault (dev), main_agent,
  mock_gateway, y sample_subagent_a/b bajo el profile `subagents`.

## 2. Cómo probarlo de punta a punta (pendiente de ejecutar)

```bash
# 1. Levantar infra + main + mock gateway
pip install -e .
cp .env.example .env
meridianctl dev up
meridianctl config check

# 2. Dar de alta identidades
meridianctl tenant create --name mercadazo
# -> anotar tenant_id

meridianctl gateway create --tenant <tenant_id> --type internal_api --name mock-gw --token dummy-token
# -> anotar gateway_id

meridianctl subagent create --tenant <tenant_id> --name subagent-a --domain test
meridianctl subagent create --tenant <tenant_id> --name subagent-b --domain test
# -> anotar subagent_a_id, subagent_b_id

# 3. Autorizar el fan-out gateway -> ambos subagentes
meridianctl allow set --gateway <gateway_id> --subagent <subagent_a_id> --intents billing.send_invoice
meridianctl allow set --gateway <gateway_id> --subagent <subagent_b_id> --intents billing.send_invoice

# 4. Levantar los subagentes de prueba con sus ids reales
echo "SUBAGENT_A_ID=<subagent_a_id>" >> .env
echo "SUBAGENT_B_ID=<subagent_b_id>" >> .env
meridianctl dev up --subagents

# 5. Disparar un intent vía el mock gateway (HTTP, según lo acordado)
curl -X POST http://localhost:8080/intent \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"<tenant_id>","gateway_id":"<gateway_id>","intent_type":"billing.send_invoice","subagent_ids":["<subagent_a_id>","<subagent_b_id>"],"payload":{"sku":"ABC-123","qty":10}}'
# -> devuelve {"message_id": "...", "correlation_id": "..."}

# 6. Consultar el resultado agregado (fan-in)
curl "http://localhost:8080/result/<correlation_id>?gateway_id=<gateway_id>"

# 7. Ver la traza de auditoría de esa solicitud puntual
meridianctl audit tail --correlation-id <correlation_id>
```

## 3. Limitaciones conocidas de esta primera versión (documentadas, no ocultas)

- El estado de agregación fan-in del `main` vive en memoria de proceso — un reinicio del
  `main` a mitad de un fan-out pierde esa agregación puntual (no el mensaje: los subagentes
  igual procesan y publican su resultado, pero nadie los agrega hasta que se reinicie el
  `main` y vuelvan a llegar). Aceptable para 2 subagentes de prueba; a resolver si el
  entregable 5/6 lo justifica.
- `sample_subagent_a`/`b` no tienen lógica de dominio, solo hacen eco — es intencional,
  el objetivo de este entregable es validar el contrato y el bus, no construir un subagente
  de dominio real (Meridian no asume ningún dominio fijo; el payload de prueba usado aquí
  es solo un ejemplo arbitrario, no una elección de producto).
- No hay reintentos ni dead-letter para mensajes que fallan repetidamente en un subagente
  (`XPENDING`/`XCLAIM` de Redis Streams no están implementados todavía).
- El fan-out completamente denegado (ningún subagente autorizado) no notifica al gateway
  de vuelta — solo queda en `audit_log`. Ver nota en `main_agent/service.py`.

## 4. Siguiente paso

Correr la guía de la sección 2 en esta máquina (requiere Docker Desktop encendido) y
confirmar con Rodrigo que el flujo end-to-end se comporta como se espera antes de dar por
cerrado el entregable 2.
