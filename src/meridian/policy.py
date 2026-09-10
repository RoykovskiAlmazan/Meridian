"""Policy de comportamiento por subagente -- ver docs/design/0005-behavior-policy.md.

Meridian no asume ningún dominio (puede orquestar inventario, organización de archivos,
investigación, lo que sea que el operador configure). Lo que SÍ es irreversible, cuándo se
necesita aprobación humana, reintentos y tono no viven hardcodeados en el código ni en
behavior/AGENTS.md -- son datos configurables por subagente, validados contra
schemas/subagent_policy.v1.schema.json.

DEFAULT_POLICY es deliberadamente conservador (nada destructivo, todo requiere aprobación)
-- "seguro por defecto" (sección 5 del brief). El `main` SÍ hace cumplir esto desde el
entregable de policy enforcement (ver docs/design/0013-policy-enforcement.md): un
subagente NUEVO, sin `meridianctl policy set` explícito, no ejecuta nada hasta que un
operador apruebe cada intent con `meridianctl approvals approve`. Esto es intencional, no
un bug -- si quieres que un subagente opere sin fricción, configúrale una policy explícita
con `requires_approval_intents: []`.
"""
from __future__ import annotations

import json
from typing import Any

import jsonschema

from meridian.messages import _find_schemas_dir  # reutiliza la misma resolución robusta

_POLICY_SCHEMA = json.loads((_find_schemas_dir() / "subagent_policy.v1.schema.json").read_text())

DEFAULT_POLICY: dict[str, Any] = {
    "schema_version": "1.0",
    "requires_approval_intents": ["*"],
    "destructive": {"allowed": False, "requires_approval": True},
    "retry_policy": {"max_retries": 0, "backoff_seconds": 0},
    "notify_on_error": {"enabled": False, "channel_ref": None},
    "tone": "directo y técnico",
}


def validate_policy(policy: dict[str, Any]) -> None:
    jsonschema.validate(policy, _POLICY_SCHEMA)


def resolve_policy(stored_policy: dict[str, Any]) -> dict[str, Any]:
    """Un subagente sin policy configurada explícitamente hereda DEFAULT_POLICY completo
    (conservador). Una policy parcial se completa con los defaults campo por campo."""
    if not stored_policy:
        return dict(DEFAULT_POLICY)
    return {**DEFAULT_POLICY, **stored_policy}


def requires_approval(policy: dict[str, Any], intent_type: str) -> bool:
    approval_list = policy.get("requires_approval_intents", [])
    return "*" in approval_list or intent_type in approval_list
