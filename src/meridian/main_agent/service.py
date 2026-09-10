"""Proceso `main`: consume TaskIntent de gateways, autoriza y rutea a subagentes (fan-out),
luego consume TaskResult de subagentes y agrega por correlation_id (fan-in) antes de
publicar el resultado final al stream del gateway de origen.

El estado de agregación en curso vive en Redis (`redis_bus.init_fanin`/`add_fanin_result`),
no en memoria del proceso -- así un reinicio del `main` a mitad de un fan-out no pierde la
agregación (ver docs/design/0012-improvement-opportunities.md, mejora ya implementada).

También reclama periódicamente mensajes que quedaron "pending" sin ack (un consumer que
murió a mitad de procesar) vía `redis_bus.claim_stale`, con dead-letter automático tras
demasiados reintentos -- ver el mismo documento.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from meridian.bus import redis_bus
from meridian.identity import repository
from meridian.logging_setup import configure
from meridian.main_agent.core import authorize_and_route

log = configure("main_agent")

_GROUP = "main"
_CONSUMER = "main-1"
_INTENT_STREAM = "meridian:intents:main"
_RESULT_STREAM = "meridian:results:main"
_MAX_DELIVERIES = 3


def _handle_intent(entry_id: str, intent: dict[str, Any]) -> None:
    correlation_id = intent["correlation_id"]
    tenant_id = intent["tenant_id"]
    gateway_id = intent["origin"]["gateway_id"]

    repository.log_audit(
        UUID(tenant_id), UUID(correlation_id), UUID(intent["message_id"]),
        "main", "received", {"gateway_id": gateway_id},
    )

    decision = authorize_and_route(intent)
    hop = len(intent["trace"])

    for subagent_id, reason in decision.denied:
        repository.log_audit(
            UUID(tenant_id), UUID(correlation_id), UUID(intent["message_id"]),
            "main", "denied", {"subagent_id": subagent_id, "reason": reason},
        )
        log.info("denied intent=%s subagent=%s reason=%s", intent["message_id"], subagent_id, reason)

    if decision.allowed_subagent_ids:
        redis_bus.init_fanin(correlation_id, gateway_id, decision.allowed_subagent_ids)

    for subagent_id in decision.allowed_subagent_ids:
        forwarded = dict(intent)
        forwarded["message_id"] = intent["message_id"]  # se re-emite el mismo hop de intent; el subagente ve el intent original
        forwarded["trace"] = intent["trace"] + [{
            "hop": hop,
            "agent_id": "main",
            "received_at": datetime.now(UTC).isoformat(),
            "decision": "forwarded",
            "reason": None,
        }]
        redis_bus.publish(redis_bus.intent_stream_for_subagent(subagent_id), forwarded)
        repository.log_audit(
            UUID(tenant_id), UUID(correlation_id), UUID(intent["message_id"]),
            "main", "forwarded", {"subagent_id": subagent_id},
        )
        log.info("forwarded intent=%s -> subagent=%s", intent["message_id"], subagent_id)

    if not decision.allowed_subagent_ids:
        # fan-out completo denegado: no hay nada que esperar, se podría notificar
        # al gateway de inmediato -- fuera de alcance del MVP (entregable 2).
        log.info("intent=%s completely denied, nothing forwarded", intent["message_id"])


def _handle_result(entry_id: str, result: dict[str, Any]) -> None:
    correlation_id = result["correlation_id"]
    state = redis_bus.add_fanin_result(correlation_id, result["subagent_id"], result)
    if state is None:
        log.warning("result for unknown/expired correlation_id=%s, dropping", correlation_id)
        return

    repository.log_audit(
        UUID(result["tenant_id"]), UUID(correlation_id), UUID(result["message_id"]),
        "main", "completed", {"subagent_id": result["subagent_id"], "status": result["status"]},
    )

    if set(state["expected"]) <= state["results"].keys():
        aggregated = {
            "correlation_id": correlation_id,
            "results": list(state["results"].values()),
        }
        redis_bus.publish(redis_bus.result_stream_for_gateway(state["gateway_id"]), aggregated)
        log.info("correlation_id=%s fan-in complete, published to gateway=%s", correlation_id, state["gateway_id"])
        redis_bus.delete_fanin(correlation_id)


def _reclaim_stale() -> None:
    for entry_id, intent in redis_bus.claim_stale(_INTENT_STREAM, _GROUP, _CONSUMER, max_deliveries=_MAX_DELIVERIES):
        log.warning("reclaimed stale intent=%s, reprocessing", intent.get("message_id"))
        try:
            _handle_intent(entry_id, intent)
        finally:
            redis_bus.ack(_INTENT_STREAM, _GROUP, entry_id)

    for entry_id, result in redis_bus.claim_stale(_RESULT_STREAM, _GROUP, _CONSUMER, max_deliveries=_MAX_DELIVERIES):
        log.warning("reclaimed stale result=%s, reprocessing", result.get("message_id"))
        try:
            _handle_result(entry_id, result)
        finally:
            redis_bus.ack(_RESULT_STREAM, _GROUP, entry_id)


def run() -> None:
    log.info("main agent starting, listening on %s and %s", _INTENT_STREAM, _RESULT_STREAM)
    loop_count = 0
    while True:
        for entry_id, intent in redis_bus.consume(_INTENT_STREAM, _GROUP, _CONSUMER, block_ms=1000):
            try:
                _handle_intent(entry_id, intent)
            finally:
                redis_bus.ack(_INTENT_STREAM, _GROUP, entry_id)

        for entry_id, result in redis_bus.consume(_RESULT_STREAM, _GROUP, _CONSUMER, block_ms=1000):
            try:
                _handle_result(entry_id, result)
            finally:
                redis_bus.ack(_RESULT_STREAM, _GROUP, entry_id)

        loop_count += 1
        if loop_count % 30 == 0:  # cada ~30 iteraciones (~1 min con block_ms=1000 x2 streams)
            _reclaim_stale()


if __name__ == "__main__":
    run()
