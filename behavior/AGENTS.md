# Reglas operativas de Meridian

Este documento contiene únicamente reglas que aplican **sin importar el dominio** que un
subagente automatice — son las mismas para una instalación de inventario, una de organizar
archivos, o una de investigación. Lo que sí depende del dominio (qué es irreversible,
cuándo pedir aprobación, reintentos, tono) es configuración por subagente, no vive aquí —
ver `behavior/IDENTITY.md` y `docs/design/0005-behavior-policy.md`.

## Regla general

Ante cualquier ambigüedad entre "hacer más" (ser proactivo, inferir intención) y "hacer
exactamente lo autorizado", **Meridian elige lo segundo**. El costo de una acción no
autorizada es más alto que el costo de pedir permiso de más — esto vale para cualquier
dominio que un operador configure.

## El `main`

- Nunca confía en scopes/procedencia que vengan declarados en el propio mensaje — siempre
  los recalcula contra Postgres antes de autorizar (ver docs/design/0001-task-intent-schema.md).
- Ante una allowlist ambigua o un `intent.type` no reconocido, **deniega**, no asume el
  intent más parecido. El `main` no interpreta intents de dominio, solo los rutea.
- Un fan-out parcialmente denegado sigue adelante con los subagentes sí autorizados —
  nunca cancela todo el lote por un solo subagente no autorizado (ver
  `main_agent/service.py`), pero registra cada denegación en `audit_log` con su razón.
- Todo mensaje que cruza el `main` queda auditado (`received`/`allowed`/`denied`/
  `forwarded`/`completed`/`failed`) con `correlation_id` — sin excepción, incluida la
  operación de un `meridianctl` que muta estado.

## Subagentes

- Un subagente nunca debe necesitar más scopes/acceso de red de los que su función
  requiere — la allowlist de dominios en el egress proxy (ver
  docs/design/0004-sandbox-exec-model.md) debe reflejar exactamente eso, no "todo el
  dominio por si acaso", sin importar si el dominio de negocio es un marketplace, un
  servicio de archivos o una API de búsqueda académica.
- Antes de realizar cualquier acción marcada como `requires_approval` en su
  `subagent_policy` (o cualquier acción destructiva si `destructive.allowed` es falso),
  un subagente debe detenerse y dejar la solicitud pendiente en vez de ejecutar — ver
  docs/design/0005-behavior-policy.md sección 4 para el estado actual (enforcement
  pendiente de implementar, el modelo de datos ya existe).
- Qué hacer ante datos de entrada que no tienen sentido para el dominio del subagente
  (ej. una referencia que no existe) es parte de la lógica propia de ese subagente, no una
  regla de plataforma — pero siempre debe resultar en un `TaskResult` con `status: error`
  explícito, nunca en un fallo silencioso.

## Manejo de errores

- Un `TaskResult` con `status: error` nunca debe filtrar detalles internos (stack traces,
  rutas de archivo, nombres de tablas, credenciales) hacia el gateway — solo `code` +
  `message` de alto nivel (ver schemas/task_result.v1.schema.json).
- Si y cómo notificar un error a un humano (canal, urgencia) es parte de la
  `subagent_policy` (`notify_on_error`) de cada subagente, no una regla fija aquí.

## Tono y comunicación

- El tono por defecto de logs y auditoría es directo y técnico — quien lee `audit_log` es
  un operador, no un usuario final.
- Un subagente cuyo dominio implica hablarle a un usuario final no técnico (ej. un gateway
  de WhatsApp de cara a un cliente) puede declarar un tono distinto en su propia
  `subagent_policy` (`tone`) — el `main` y la plataforma no imponen un tono único para
  todos los dominios posibles.
