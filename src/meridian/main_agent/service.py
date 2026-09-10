"""Proceso `main`: consume TaskIntent de gateways, autoriza y rutea a subagentes (fan-out),
luego consume TaskResult de subagentes y agrega por correlation_id (fan-in) antes de
publicar el resultado final al stream del gateway de origen.

MVP: el estado de agregación en curso vive en memoria del proceso -- si el `main` se
reinicia a mitad de un fan-out, esa agregación se pierde. Aceptable para el entregable 2
(2 subagentes de prueba); persistir el estado de agregación en Postgres/Redis es trabajo
de un entregable posterior si la carga real lo justifica.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from meridian.bus import redis_bus
from meridian.identity import repository
from meridian.main_agent.core import authorize_and_route

logging.basicConfig(level=logging.INFO, format="%(asctime)s main %(message)s")
log = logging.getLogger("meridian.main_agent")

_GROUP = "main"
_CONSUMER = "main-1"

# correlation_id -> {"gateway_id": str, "expected": set[str], "results": dict[str, dict]}
_pending: dict[str, dict[str, Any]] = {}


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
        _pending[correlation_id] = {
            "gateway_id": gateway_id,
            "expected": set(decision.allowed_subagent_ids),
            "results": {},
        }

    for subagent_id in decision.allowed_subagent_ids:
        forwarded = dict(intent)
        forwarded["message_id"] = intent["message_id"]  # se re-emite el mismo hop de intent; el subagente ve el intent original
        forwarded["trace"] = intent["trace"] + [{
            "hop": hop,
            "agent_id": "main",
            "received_at": datetime.now(timezone.utc).isoformat(),
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
    pending = _pending.get(correlation_id)
    if pending is None:
        log.warning("result for unknown/expired correlation_id=%s, dropping", correlation_id)
        return

    pending["results"][result["subagent_id"]] = result
    repository.log_audit(
        UUID(result["tenant_id"]), UUID(correlation_id), UUID(result["message_id"]),
        "main", "completed", {"subagent_id": result["subagent_id"], "status": result["status"]},
    )

    if pending["expected"] <= pending["results"].keys():
        aggregated = {
            "correlation_id": correlation_id,
            "results": list(pending["results"].values()),
        }
        redis_bus.publish(redis_bus.result_stream_for_gateway(pending["gateway_id"]), aggregated)
        log.info("correlation_id=%s fan-in complete, published to gateway=%s", correlation_id, pending["gateway_id"])
        del _pending[correlation_id]


def run() -> None:
    log.info("main agent starting, listening on %s and %s", "meridian:intents:main", "meridian:results:main")
    while True:
        for entry_id, intent in redis_bus.consume("meridian:intents:main", _GROUP, _CONSUMER, block_ms=1000):
            try:
                _handle_intent(entry_id, intent)
            finally:
                redis_bus.ack("meridian:intents:main", _GROUP, entry_id)

        for entry_id, result in redis_bus.consume("meridian:results:main", _GROUP, _CONSUMER, block_ms=1000):
            try:
                _handle_result(entry_id, result)
            finally:
                redis_bus.ack("meridian:results:main", _GROUP, entry_id)


if __name__ == "__main__":
    run()
