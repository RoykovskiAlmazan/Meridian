"""Lógica de autorización y ruteo del `main`.

Regla no negociable (sección 3 del brief + docs/design/0001-task-intent-schema.md, sección 3):
el main NUNCA confía en los scopes que el propio TaskIntent declara -- siempre los recalcula
contra Postgres antes de decidir si reenvía a un subagente.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from meridian.identity import repository


@dataclass
class RoutingDecision:
    allowed_subagent_ids: list[str]
    denied: list[tuple[str, str]]  # (subagent_id, reason)


def authorize_and_route(intent: dict[str, Any]) -> RoutingDecision:
    tenant_id = intent["tenant_id"]
    gateway_id = intent["origin"]["gateway_id"]
    intent_type = intent["intent"]["type"]
    requested_subagent_ids = intent["intent"]["target"]["subagent_ids"]

    gateway = repository.get_gateway(UUID(gateway_id))
    if gateway is None:
        reason = "gateway_not_found"
        return RoutingDecision([], [(sid, reason) for sid in requested_subagent_ids])
    if gateway["status"] != "active":
        reason = "gateway_revoked"
        return RoutingDecision([], [(sid, reason) for sid in requested_subagent_ids])
    if str(gateway["tenant_id"]) != tenant_id:
        reason = "tenant_mismatch"
        return RoutingDecision([], [(sid, reason) for sid in requested_subagent_ids])

    allowed: list[str] = []
    denied: list[tuple[str, str]] = []

    for subagent_id in requested_subagent_ids:
        subagent = repository.get_subagent(UUID(subagent_id))
        if subagent is None:
            denied.append((subagent_id, "subagent_not_found"))
            continue
        if subagent["status"] != "active":
            denied.append((subagent_id, "subagent_revoked"))
            continue
        if str(subagent["tenant_id"]) != tenant_id:
            denied.append((subagent_id, "tenant_mismatch"))
            continue

        entry = repository.get_allowlist_entry(UUID(gateway_id), UUID(subagent_id))
        if entry is None:
            denied.append((subagent_id, "not_in_allowlist"))
            continue
        if intent_type not in entry["allowed_intents"]:
            denied.append((subagent_id, "intent_not_allowed"))
            continue

        allowed.append(subagent_id)

    return RoutingDecision(allowed_subagent_ids=allowed, denied=denied)
