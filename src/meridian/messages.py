"""Construcción y validación de TaskIntent / TaskResult contra los JSON Schemas
publicados en schemas/ (fuente de verdad del contrato, ver docs/design/0001-task-intent-schema.md).
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema


def _find_schemas_dir() -> Path:
    """Localiza schemas/ (fuente de verdad del contrato) tanto en desarrollo (instalación
    editable, __file__ vive bajo src/meridian/) como dentro de un contenedor (instalación
    normal en site-packages, con schemas/ copiado junto a src/ en el WORKDIR -- ver
    docker/*.Dockerfile). MERIDIAN_SCHEMAS_DIR permite forzar la ruta si ninguna aplica."""
    override = os.environ.get("MERIDIAN_SCHEMAS_DIR")
    if override:
        return Path(override)

    candidates = [
        Path(__file__).resolve().parents[2] / "schemas",  # repo root en instalación editable
        Path.cwd() / "schemas",                            # WORKDIR del contenedor
    ]
    for candidate in candidates:
        if (candidate / "task_intent.v1.schema.json").exists():
            return candidate

    raise FileNotFoundError(
        "No se encontró schemas/task_intent.v1.schema.json en ninguna ubicación candidata "
        f"({[str(c) for c in candidates]}). Define MERIDIAN_SCHEMAS_DIR explícitamente."
    )


_SCHEMAS_DIR = _find_schemas_dir()

_task_intent_schema = json.loads((_SCHEMAS_DIR / "task_intent.v1.schema.json").read_text())
_task_result_schema = json.loads((_SCHEMAS_DIR / "task_result.v1.schema.json").read_text())


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def new_task_intent(
    *,
    tenant_id: str,
    gateway_id: str,
    gateway_type: str,
    scopes: list[str],
    intent_type: str,
    subagent_ids: list[str],
    payload: dict[str, Any],
    correlation_id: str | None = None,
    causation_id: str | None = None,
    priority: str = "normal",
) -> dict[str, Any]:
    intent = {
        "schema_version": "1.0",
        "message_id": str(uuid.uuid4()),
        "correlation_id": correlation_id or str(uuid.uuid4()),
        "causation_id": causation_id,
        "tenant_id": tenant_id,
        "issued_at": _now_iso(),
        "expires_at": None,
        "idempotency_key": None,
        "origin": {
            "gateway_id": gateway_id,
            "gateway_type": gateway_type,
            "scopes": scopes,
            "credential_ref": None,
        },
        "intent": {
            "type": intent_type,
            "target": {
                "mode": "fan_out" if len(subagent_ids) > 1 else "single",
                "subagent_ids": subagent_ids,
            },
            "payload": payload,
            "priority": priority,
        },
        "trace": [],
    }
    validate_task_intent(intent)
    return intent


def new_task_result(
    *,
    correlation_id: str,
    in_response_to: str,
    tenant_id: str,
    subagent_id: str,
    status: str,
    started_at: str,
    output: dict[str, Any] | None = None,
    error: dict[str, str] | None = None,
) -> dict[str, Any]:
    result = {
        "schema_version": "1.0",
        "message_id": str(uuid.uuid4()),
        "correlation_id": correlation_id,
        "in_response_to": in_response_to,
        "tenant_id": tenant_id,
        "subagent_id": subagent_id,
        "status": status,
        "started_at": started_at,
        "completed_at": _now_iso(),
        "output": output,
        "error": error,
    }
    validate_task_result(result)
    return result


def validate_task_intent(message: dict[str, Any]) -> None:
    jsonschema.validate(message, _task_intent_schema)


def validate_task_result(message: dict[str, Any]) -> None:
    jsonschema.validate(message, _task_result_schema)
