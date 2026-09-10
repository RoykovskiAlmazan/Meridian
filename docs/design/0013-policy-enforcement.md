# Entregable — Enforcement real de `subagent_policy`

Estado: implementado y verificado end-to-end.

## 1. Qué cambió

Hasta ahora `subagent_policy` (entregable 4) era solo datos: nadie la consultaba antes de
ejecutar un intent. Ahora `main_agent/service.py`, justo antes de reenviar un intent
autorizado a un subagente, resuelve su policy (`resolve_policy(get_subagent_policy(id))`)
y llama a `requires_approval(policy, intent_type)`. Si es `True`:

1. No se reenvía el intent al subagente.
2. Se guarda una fila en `pending_approvals` (Postgres) con el `TaskIntent` completo ya
   armado (mismo `trace`, mismo `message_id`) — al aprobar, se reenvía tal cual, sin
   reconstruirlo.
3. Se audita `pending_approval`.
4. El subagente **sigue contando** en el `expected` del fan-in (ver
   `redis_bus.init_fanin`) -- el fan-in no se completa hasta que alguien decida.

`meridianctl approvals list/approve/deny`:
- `approve`: publica el intent guardado al stream del subagente (como si el `main` lo
  hubiera reenviado en el momento), marca `approved`, audita `approved`.
- `deny`: publica un `TaskResult` sintético con `status: error`, `code: approval_denied`
  directo al stream de resultados -- así el fan-in se completa igual (con un error para
  ese subagente) en vez de quedar colgado para siempre.

## 2. Implicación importante (no un bug): el default conservador ahora sí aplica

Un subagente **sin** `meridianctl policy set` explícito hereda `DEFAULT_POLICY`
(`requires_approval_intents: ["*"]`) -- ahora eso significa que **todo** intent a ese
subagente queda pendiente de aprobación hasta que un operador lo apruebe a mano. Es
"seguro por defecto" funcionando como se diseñó (sección 5 del brief), pero es un cambio
de comportamiento real: los subagentes de referencia (`sample_subagent_a/b`,
`paper_search`, `paper_summarizer`) necesitaron una policy explícita
(`requires_approval_intents: []`) para seguir respondiendo sin fricción en las demos.
**Cualquier subagente nuevo que crees necesita lo mismo si no quieres aprobar cada intent
a mano.**

## 3. Bug encontrado y corregido de paso: un error no manejado tumbaba todo el `main`

Durante la prueba de este entregable, un intent disparó una excepción no capturada en
`_handle_intent` (una columna de Postgres que faltaba por otro cambio en curso) y **tumbó
el contenedor completo de `main_agent`**, no solo ese mensaje. Se corrigió envolviendo
cada llamada a `_handle_intent`/`_handle_result` (en el loop normal y en el de
`claim_stale`) para que un error se loguee con `log.exception` y el mensaje se haga ack
igual (evita un loop de crashes), en vez de propagar y matar el proceso. Mismo patrón
aplicado al loop de `worker_base.py`.

## 4. Verificación hecha

- Intent a un subagente con `requires_approval_intents: ["inventory.sync_stock"]` →
  queda `pending`, `main_agent` sigue vivo.
- `meridianctl approvals approve` → se reenvía, el fan-in se completa con `status: success`.
- Otro intent igual, `meridianctl approvals deny` → el fan-in se completa con
  `status: error, code: approval_denied` en vez de quedar colgado.
- Fan-out normal (subagentes con policy permisiva) sigue funcionando sin fricción.
