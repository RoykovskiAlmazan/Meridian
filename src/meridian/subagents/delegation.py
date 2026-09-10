"""Permite que un subagente delegue trabajo en uno o más sub-subagentes -- ver
docs/design/0014-sub-subagents.md. Un subagente que quiera delegar llama a `delegate()`
desde dentro de su propio `handler` (el mismo que le pasa a `worker_base.run`); el mensaje
resultante pasa por el `main` exactamente igual que cualquier otro TaskIntent (misma
validación de allowlist -- aquí contra `subagent_subagent_allowlist`, mismo esquema,
mismo `correlation_id` para que quede en la misma traza de auditoría).

No hay atajos: un subagente NO puede publicar directo al stream de otro subagente sin
pasar por el `main` -- si pudiera, se saltaría la autorización explícita, justo lo que la
plataforma no permite en ningún otro punto (sección 3 del brief).
"""
from __future__ import annotations

from typing import Any

from meridian.bus.redis_bus import publish_intent_to_main
from meridian.messages import new_task_intent


def delegate(
    *,
    parent_subagent_id: str,
    tenant_id: str,
    intent_type: str,
    child_subagent_ids: list[str],
    payload: dict[str, Any],
    correlation_id: str | None = None,
    causation_id: str | None = None,
) -> dict[str, Any]:
    """Construye y publica un TaskIntent delegado. Si se pasa `correlation_id` (el de la
    solicitud original que este subagente está atendiendo), el sub-subagente queda en la
    misma traza de punta a punta -- normalmente eso es lo que se quiere."""
    intent = new_task_intent(
        tenant_id=tenant_id,
        gateway_id=parent_subagent_id,
        gateway_type="subagent_delegate",
        scopes=[],
        intent_type=intent_type,
        subagent_ids=child_subagent_ids,
        payload=payload,
        correlation_id=correlation_id,
        causation_id=causation_id,
    )
    publish_intent_to_main(intent)
    return intent
