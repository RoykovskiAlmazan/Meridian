# Entregable — Sub-subagentes (delegación entre subagentes)

Estado: implementado y verificado end-to-end.

## 1. Diseño

Un subagente puede delegar en otro subagente ("hijo") sin que el `main` tenga que tratar
ese caso como algo especial: el hijo se autoriza con **el mismo modelo de allowlist
explícita** que gateway→subagente, solo que contra una tabla nueva,
`subagent_subagent_allowlist` (parent_subagent_id, child_subagent_id, allowed_intents).

Para que el `main` sepa que un `TaskIntent` viene de otro subagente y no de un gateway
externo, se agregó el valor `"subagent_delegate"` al enum de `origin.gateway_type` (schema
`task_intent.v1.schema.json`) -- en ese caso `origin.gateway_id` lleva el id del subagente
que delega, no un gateway real. `main_agent/core.py` rama sobre esto:
`gateway_type == "subagent_delegate"` → valida contra `subagents`/
`subagent_subagent_allowlist` en vez de `gateways`/`gateway_subagent_allowlist`. Ningún
otro cambio de esquema fue necesario.

`src/meridian/subagents/delegation.py` expone `delegate(...)`, que un `handler` de
subagente llama para delegar -- construye el `TaskIntent` (mismo `messages.new_task_intent`
de siempre) y lo publica al stream `meridian:intents:main`, exactamente como cualquier
otro intent. **Un subagente nunca publica directo al stream de otro** -- eso se saltaría
la autorización explícita, algo que la plataforma no permite en ningún otro punto.

## 2. Límite de profundidad

`MAX_DELEGATION_DEPTH = 5` en `main_agent/core.py`: si `len(intent["trace"]) >=` ese
límite, se deniega con `max_delegation_depth_exceeded` sin ni siquiera consultar la
allowlist -- evita que una allowlist mal configurada (o un ciclo A→B→A) genere una cadena
infinita de delegaciones.

## 3. Cómo se usa

```bash
meridianctl subagent create --tenant <id> --name mi-hijo --domain lo-que-sea --parent <parent_subagent_id>
meridianctl allow set-sub --parent <parent_subagent_id> --child <child_subagent_id> --intents <dominio>.<accion>
```

Y dentro del `handler` del subagente padre:

```python
from meridian.subagents.delegation import delegate

def handle(payload):
    delegate(
        parent_subagent_id=SUBAGENT_ID,  # su propio id (env SUBAGENT_ID)
        tenant_id=payload_or_intent_tenant_id,
        intent_type="mi_dominio.mi_subaccion",
        child_subagent_ids=[child_id],
        payload={...},
    )
    return {"delegated": True}
```

## 4. Verificación hecha

Con `subagent-a` como padre y `subagent-b` como hijo (los mismos subagentes de eco del
entregable 2, sin código nuevo -- se probó la delegación llamando a `delegate()`
directamente, no agregando lógica de delegación a su `handler`, para aislar la prueba del
mecanismo de ruteo del contenido del subagente): allowlist de delegación configurada,
`delegate()` invocado, `audit_log` mostró `received → forwarded → completed` bajo el mismo
`correlation_id`, exactamente igual que un fan-out gateway→subagente normal.

También se confirmó que, sin la entrada en `subagent_subagent_allowlist`, la delegación se
deniega con `not_in_allowlist` aunque `subagents.parent_subagent_id` ya reflejara la
relación -- la relación de parentesco por sí sola no autoriza nada (test unitario
`test_subagent_delegation_denied_without_delegation_allowlist_entry`).

## 5. Nota importante ligada al entregable de policy enforcement

Un sub-subagente sin `subagent_policy` explícita también hereda el default conservador
(`requires_approval_intents: ["*"]`) -- una delegación a un hijo sin policy configurada
queda pendiente de aprobación humana igual que cualquier otro intent. Es consistente con
el resto de la plataforma, no un caso especial.
