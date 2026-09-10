"""Loop genérico de un subagente: consume TaskIntent de su propio stream, corre un
`handler(payload) -> output` y publica un TaskResult a meridian:results:main.

Los subagentes de dominio real (lo que sea que quien instale Meridian necesite automatizar)
implementarán su propio `handler`;
para el MVP (entregable 2) los dos subagentes de prueba solo validan que el contrato
de mensajes y el fan-out/fan-in funcionan de punta a punta.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from meridian.bus import redis_bus
from meridian.logging_setup import configure
from meridian.messages import new_task_result

Handler = Callable[[dict[str, Any]], dict[str, Any]]


def run(subagent_id: str, handler: Handler) -> None:
    log = configure(f"subagent:{subagent_id}")

    stream = redis_bus.intent_stream_for_subagent(subagent_id)
    group = "subagent"
    consumer = f"{subagent_id}-1"

    log.info("subagent worker starting, listening on %s", stream)
    while True:
        for entry_id, intent in redis_bus.consume(stream, group, consumer, block_ms=2000):
            started_at = datetime.now(timezone.utc).isoformat()
            try:
                output = handler(intent["intent"]["payload"])
                result = new_task_result(
                    correlation_id=intent["correlation_id"],
                    in_response_to=intent["message_id"],
                    tenant_id=intent["tenant_id"],
                    subagent_id=subagent_id,
                    status="success",
                    started_at=started_at,
                    output=output,
                )
            except Exception as exc:  # noqa: BLE001 -- se reporta como TaskResult de error, no se relanza
                log.exception(
                    "handler failed for intent=%s", intent["message_id"],
                    extra={"extra_fields": {"correlation_id": intent["correlation_id"], "message_id": intent["message_id"]}},
                )
                result = new_task_result(
                    correlation_id=intent["correlation_id"],
                    in_response_to=intent["message_id"],
                    tenant_id=intent["tenant_id"],
                    subagent_id=subagent_id,
                    status="error",
                    started_at=started_at,
                    error={"code": "handler_error", "message": str(exc)},
                )
            redis_bus.publish_result_to_main(result)
            redis_bus.ack(stream, group, entry_id)
            log.info(
                "processed intent=%s status=%s", intent["message_id"], result["status"],
                extra={"extra_fields": {"correlation_id": intent["correlation_id"], "message_id": intent["message_id"], "status": result["status"]}},
            )
