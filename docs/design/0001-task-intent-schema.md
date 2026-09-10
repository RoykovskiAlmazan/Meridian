# Entregable 1 — Schema de Task/Intent y modelo de identidad/scopes

Estado: propuesta v1 para revisión con Rodrigo. No implementado todavía.

## 1. Objetivo

Definir el contrato de mensajes que cruza `gateway → main → subagente(s)` y de vuelta
(`subagente → main → gateway`), de forma que:

- Cualquier mensaje sea auditable de punta a punta (`correlation_id` + `trace`).
- La procedencia (qué gateway, de qué tenant, con qué scopes) viaje siempre con el mensaje,
  nunca se infiera fuera de banda.
- El `main` pueda validar la allowlist gateway↔subagente sin tener que consultar nada más
  que el propio mensaje + la tabla de allowlist en Postgres.
- Soporte fan-out (un intent dispara N subagentes) y fan-in (N resultados se agregan bajo el
  mismo `correlation_id`) desde el día uno.
- Sea versionable sin romper consumidores viejos (`schema_version` explícito).

## 2. Dos tipos de mensaje

1. **TaskIntent** — gateway → main, y main → subagente(s) (reenviado, con un hop nuevo en `trace`).
2. **TaskResult** — subagente → main, y main → gateway (agregando resultados si hubo fan-out).

Ambos comparten `schema_version`, `correlation_id`, `tenant_id`, `trace`.

## 3. TaskIntent v1

Ver [`schemas/task_intent.v1.schema.json`](../../schemas/task_intent.v1.schema.json).

Campos clave y su razón de ser:

| Campo | Por qué existe |
|---|---|
| `schema_version` | Permite evolucionar el contrato sin romper consumidores que aún esperan v1. Nunca se muta un schema publicado — se agrega v2. |
| `message_id` | Identidad única de *este* mensaje (un hop). Distinto de `correlation_id`. |
| `correlation_id` | Une todos los mensajes de una misma solicitud de extremo a extremo (intent original + reenvíos a subagentes + resultados). Es lo que permite fan-out/fan-in. |
| `causation_id` | El `message_id` del mensaje que directamente causó este (ej. el TaskIntent que el main reenvía a un subagente referencia como `causation_id` el `message_id` del intent original del gateway). Da la cadena causal exacta dentro de un mismo `correlation_id`. |
| `tenant_id` | Obligatorio desde el día uno por la decisión de multi-tenancy real. Todo namespacing (Postgres, Redis stream keys, Vault paths) cuelga de aquí. |
| `idempotency_key` | Opcional. Si el gateway reintenta el envío (ej. timeout de red), el `main` puede deduplicar sin depender de que `message_id` se haya regenerado o no. |
| `origin.gateway_id` / `origin.gateway_type` | Identidad propia del gateway (no un secreto compartido — requisito no negociable de la sección 5 del brief). |
| `origin.scopes` | Scopes que ese gateway tiene *en ese tenant*, resueltos por el main contra Postgres al momento de aceptar el mensaje — no confiar en scopes que el propio gateway declare sin validar. |
| `origin.credential_ref` | Referencia (`SecretRef`) a Vault, nunca el secreto en crudo. |
| `intent.type` | Nombre namespaced del intent (ej. `billing.send_invoice`), para que el main rutee sin necesidad de tabla de rutas propia. |
| `intent.target.mode` | `single` o `fan_out` — explícito, no inferido del número de subagentes. |
| `intent.target.subagent_ids` | Lista explícita. El main valida cada uno contra la allowlist antes de reenviar. |
| `trace[]` | Un registro por hop (gateway→main, main→subagente_1, main→subagente_2, ...) con decisión (`allowed`/`denied`/`forwarded`) y motivo. Es el rastro de auditoría que exige la sección 5 del brief, embebido en el propio mensaje además de persistirse en `audit_log`. |

### Validación de allowlist (responsabilidad del `main`)

Al recibir un `TaskIntent` de un gateway, el `main`:

1. Resuelve `origin.gateway_id` contra Postgres → confirma que existe, está activo, y pertenece a `tenant_id`.
2. Resuelve los scopes reales del gateway en Postgres (ignora `origin.scopes` si el mensaje ya trae uno — se recalcula, no se confía en el payload entrante para autorización).
3. Para cada `subagent_id` en `intent.target.subagent_ids`, verifica en `gateway_subagent_allowlist` que ese gateway puede invocar ese subagente con ese `intent.type`.
4. Si algún subagente no está permitido: se marca `denied` en el `trace` para ese hop y **no se le reenvía nada** — el resto de subagentes permitidos sigue su curso normalmente (fallo parcial, no total).
5. Se persiste un registro en `audit_log` por cada decisión, con `correlation_id`, `message_id`, `tenant_id`, y el resultado.

## 4. TaskResult v1

Ver [`schemas/task_result.v1.schema.json`](../../schemas/task_result.v1.schema.json).

| Campo | Por qué existe |
|---|---|
| `in_response_to` | `message_id` del `TaskIntent` específico que este resultado responde (el que el subagente recibió, no el original del gateway). |
| `correlation_id` | El mismo del intent original — así el main puede hacer fan-in agrupando por este campo aunque hayan llegado N resultados de N subagentes. |
| `status` | `success` \| `error` \| `partial`. `partial` es relevante en fan-out: algunos subagentes responden bien, otros fallan. |
| `output` | Payload de dominio, libre — el schema no intenta tipar el dominio del subagente. |
| `error` | Presente solo si `status != success`. Código + mensaje, nunca un stack trace crudo (evita fuga de detalles internos hacia el gateway/usuario final). |

## 5. Modelo de identidad/scopes (Postgres)

Tablas mínimas para el MVP (entregable 1 y 2):

```
tenants
  id (pk), name, status, created_at

gateways
  id (pk), tenant_id (fk tenants), type, name,
  credential_ref,        -- SecretRef a Vault, nunca el secreto
  status,                -- active | revoked
  created_at, rotated_at

subagents
  id (pk), tenant_id (fk tenants), name, domain,
  status, created_at

gateway_subagent_allowlist
  gateway_id (fk gateways), subagent_id (fk subagents),
  allowed_intents (text[]),   -- ej. {'billing.send_invoice','crm.update_contact'}
  created_at
  PRIMARY KEY (gateway_id, subagent_id)

audit_log
  id (pk), tenant_id, correlation_id, message_id,
  agent_id,               -- quién tomó la decisión (main, o el subagente)
  event_type,             -- received | allowed | denied | forwarded | completed | failed
  detail (jsonb),
  created_at
```

Notas:
- `credential_ref` es siempre una referencia opaca (ej. `vault:kv/gateways/{gateway_id}/token`), resuelta en runtime por el proceso que la necesita, nunca almacenada ni logueada en claro.
- `allowed_intents` como array de texto es suficiente para el MVP (2 subagentes de prueba). Si el número de intents crece mucho, se puede normalizar a tabla propia sin romper el contrato hacia afuera — es un detalle de implementación de la allowlist, no del schema de mensajes.
- Todo tiene `tenant_id` (directo o vía FK) — ninguna tabla es "global" implícitamente, coherente con multi-tenancy real.

## 6. Abierto / fuera de alcance de este entregable

- Formato exacto de `intent.payload` por dominio (ej. qué campos lleva `billing.send_invoice`) — se define cuando se construya el primer subagente real, no aquí.
- Firma criptográfica de mensajes entre gateway y main (hoy la autenticidad depende de la validación de `credential_ref` vía Vault en el transporte; una firma por mensaje es una capa adicional a evaluar en el entregable 3 de sandbox/seguridad si se considera necesaria).
- Política de retención de `audit_log` — se decide en el entregable 6 (observabilidad).
