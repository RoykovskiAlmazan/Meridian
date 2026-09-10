# Entregable 4 — Reglas de comportamiento: qué es fijo vs. qué es configurable

Estado: implementado (modelo de datos + CLI). **Enforcement pendiente** — ver sección 4.

## 1. Por qué esto cambió de forma

La primera versión de `behavior/AGENTS.md`/`IDENTITY.md` asumía casos concretos de negocio
(ej. "cancelar una orden", "eliminar un listing de marketplace") como ejemplos a rellenar.
Rodrigo corrigió esto: **Meridian no tiene un dominio fijo**. Quien la instale puede
configurarla para gestión de inventario, para ordenar archivos, para investigar y redactar
papers, o para cualquier otra cosa — un subagente "ordenar archivos" y un subagente
"investigación" tienen nociones completamente distintas de qué es irreversible, cuándo
pedir aprobación, o qué tono usar.

Esto separa el comportamiento de Meridian en dos capas:

1. **Reglas de plataforma (fijas, en `behavior/AGENTS.md`)** — aplican sin importar el
   dominio: nunca confiar en scopes declarados, allowlist estricta, todo auditado, deny by
   default. Estas no cambian entre instalaciones.
2. **Policy de comportamiento (configurable, por subagente)** — qué es irreversible, cuándo
   pedir aprobación, reintentos, notificaciones, tono. Esto lo define quien instale
   Meridian, subagente por subagente, no el código ni un documento fijo del repo.

## 2. Modelo de datos

Nueva tabla `subagent_policy` (`docker/init/postgres_schema.sql`): una fila JSONB por
subagente, validada contra
[`schemas/subagent_policy.v1.schema.json`](../../schemas/subagent_policy.v1.schema.json).

Campos:

| Campo | Para qué sirve |
|---|---|
| `requires_approval_intents` | Lista de `intent.type` (o `"*"`) que requieren aprobación humana antes de ejecutarse. |
| `destructive.allowed` | Si este subagente puede hacer algo irreversible en absoluto. |
| `destructive.requires_approval` | Si, aun permitiéndolo, cada acción irreversible necesita aprobación puntual. |
| `retry_policy` | `max_retries` / `backoff_seconds` ante fallos transitorios. |
| `notify_on_error` | Si y por qué canal (`channel_ref`, nunca un contacto en claro) notificar errores. |
| `tone` | Guía de tono libre para las respuestas/errores de ese subagente. |

`meridian/policy.py` define `DEFAULT_POLICY` — el default para un subagente sin policy
configurada explícitamente es **conservador**: todo requiere aprobación, nada destructivo
permitido, sin reintentos. Coherente con "seguro por defecto" (sección 5 del brief): un
operador tiene que decidir activamente bajar la guardia para un subagente concreto.

## 3. Cómo se configura (`meridianctl policy`)

```bash
# ver el default conservador
meridianctl policy show-default

# configurar un subagente "ordenar archivos": mover está bien, borrar no, y sin aprobación
# para reordenar (bajo riesgo), pero eliminar archivos SÍ requiere aprobación siempre
cat > policy_file_organizer.json <<'EOF'
{
  "schema_version": "1.0",
  "requires_approval_intents": ["files.delete"],
  "destructive": {"allowed": true, "requires_approval": true},
  "retry_policy": {"max_retries": 2, "backoff_seconds": 5},
  "notify_on_error": {"enabled": false, "channel_ref": null},
  "tone": "directo y técnico"
}
EOF
meridianctl policy set --subagent <subagent_id> --file policy_file_organizer.json

# configurar un subagente "investigación de papers": nada destructivo, puede buscar/leer/
# resumir libremente sin pedir aprobación en cada paso
cat > policy_research.json <<'EOF'
{
  "schema_version": "1.0",
  "requires_approval_intents": [],
  "destructive": {"allowed": false, "requires_approval": true},
  "retry_policy": {"max_retries": 3, "backoff_seconds": 10},
  "notify_on_error": {"enabled": false, "channel_ref": null},
  "tone": "formal y citando fuentes"
}
EOF
meridianctl policy set --subagent <otro_subagent_id> --file policy_research.json

meridianctl policy get --subagent <subagent_id>
```

Estos dos ejemplos (organización de archivos vs. investigación) son deliberadamente
distintos de dominio para dejar explícito que la policy no asume nada sobre qué hace el
subagente — son solo ilustrativos, no una limitación de qué dominios soporta Meridian.

## 4. Qué falta (fuera de alcance de este entregable)

**La policy hoy es solo datos: `main_agent/service.py` y `worker_base.py` no la leen ni la
hacen cumplir todavía.** Falta:

- Que el `main` (o el propio subagente antes de actuar) consulte `requires_approval` para
  el intent en curso y, si aplica, deje el `TaskResult` en un estado `pending_approval` en
  vez de ejecutar directo — necesita un mecanismo de aprobación (`meridianctl approvals
  approve/deny`, mencionado como alternativa descartada por ahora en
  docs/design/0004-sandbox-exec-model.md sección 2, pero que sigue siendo compatible con
  este modelo de datos).
- Que `retry_policy` y `notify_on_error` se conecten al loop de `worker_base.py`.

Se implementó el modelo de datos y la CLI ahora (para que la configuración por subagente
exista desde que se crea un subagente real) pero el enforcement se conecta cuando exista
el primer subagente de dominio real que lo necesite — construir la ejecución antes que el
caso de uso real habría sido diseñar a ciegas.
