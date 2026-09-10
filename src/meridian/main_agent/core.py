"""Lógica de autorización y ruteo del `main`.

Regla no negociable (sección 3 del brief + docs/design/0001-task-intent-schema.md, sección 3):
el main NUNCA confía en los scopes que el propio TaskIntent declara -- siempre los recalcula
contra Postgres antes de decidir si reenvía a un subagente.

Soporta dos tipos de "caller" (ver docs/design/0014-sub-subagents.md):
- gateway (el caso normal): origin.gateway_type != 'subagent_delegate'.
- otro subagente delegando en un sub-subagente: origin.gateway_type == 'subagent_delegate',
  origin.gateway_id lleva el id del subagente padre. Mismo modelo de allowlist explícita,
  solo que contra `subagent_subagent_allowlist` en vez de `gateway_subagent_allowlist`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from meridian.identity import repository

MAX_DELEGATION_DEPTH = 5


@dataclass
class RoutingDecision:
    allowed_subagent_ids: list[str]
    denied: list[tuple[str, str]]  # (subagent_id, reason)


def authorize_and_route(intent: dict[str, Any]) -> RoutingDecision:
    tenant_id = intent["tenant_id"]
    caller_id = intent["origin"]["gateway_id"]
    caller_type = intent["origin"]["gateway_type"]
    intent_type = intent["intent"]["type"]
    requested_subagent_ids = intent["intent"]["target"]["subagent_ids"]

    if caller_type == "subagent_delegate":
        # sub-subagentes: la profundidad de delegación se limita por el número de hops
        # ya en el trace -- evita que una allowlist mal configurada (o un ciclo) genere
        # una cadena infinita de delegaciones.
        if len(intent.get("trace", [])) >= MAX_DELEGATION_DEPTH:
            reason = "max_delegation_depth_exceeded"
            return RoutingDecision([], [(sid, reason) for sid in requested_subagent_ids])
        return _authorize_subagent_caller(tenant_id, caller_id, intent_type, requested_subagent_ids)

    return _authorize_gateway_caller(tenant_id, caller_id, intent_type, requested_subagent_ids)


def _authorize_gateway_caller(
    tenant_id: str, gateway_id: str, intent_type: str, requested_subagent_ids: list[str]
) -> RoutingDecision:
    gateway = repository.get_gateway(UUID(gateway_id))
    if gateway is None:
        return RoutingDecision([], [(sid, "gateway_not_found") for sid in requested_subagent_ids])
    if gateway["status"] != "active":
        return RoutingDecision([], [(sid, "gateway_revoked") for sid in requested_subagent_ids])
    if str(gateway["tenant_id"]) != tenant_id:
        return RoutingDecision([], [(sid, "tenant_mismatch") for sid in requested_subagent_ids])

    return _authorize_targets(
        tenant_id, requested_subagent_ids, intent_type,
        lookup_allowlist=lambda sid: repository.get_allowlist_entry(UUID(gateway_id), UUID(sid)),
    )


def _authorize_subagent_caller(
    tenant_id: str, parent_subagent_id: str, intent_type: str, requested_subagent_ids: list[str]
) -> RoutingDecision:
    parent = repository.get_subagent(UUID(parent_subagent_id))
    if parent is None:
        return RoutingDecision([], [(sid, "delegating_subagent_not_found") for sid in requested_subagent_ids])
    if parent["status"] != "active":
        return RoutingDecision([], [(sid, "delegating_subagent_revoked") for sid in requested_subagent_ids])
    if str(parent["tenant_id"]) != tenant_id:
        return RoutingDecision([], [(sid, "tenant_mismatch") for sid in requested_subagent_ids])

    return _authorize_targets(
        tenant_id, requested_subagent_ids, intent_type,
        lookup_allowlist=lambda sid: repository.get_subagent_delegation_entry(UUID(parent_subagent_id), UUID(sid)),
    )


def _authorize_targets(tenant_id: str, requested_subagent_ids, intent_type, lookup_allowlist) -> RoutingDecision:
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

        entry = lookup_allowlist(subagent_id)
        if entry is None:
            denied.append((subagent_id, "not_in_allowlist"))
            continue
        if intent_type not in entry["allowed_intents"]:
            denied.append((subagent_id, "intent_not_allowed"))
            continue

        allowed.append(subagent_id)

    return RoutingDecision(allowed_subagent_ids=allowed, denied=denied)
