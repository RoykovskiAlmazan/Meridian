"""Wrapper delgado sobre Redis Streams para publicar/consumir TaskIntent y TaskResult.

Convención de nombres de stream:
  meridian:intents:main            -- gateway -> main
  meridian:intents:<subagent_id>   -- main -> ese subagente (fan-out = N publish, uno por subagente)
  meridian:results:main            -- subagente -> main (fan-in: el main agrupa por correlation_id)
  meridian:results:gateway:<id>    -- main -> gateway (resultado final agregado)

Cada mensaje se guarda como un único campo "data" con el JSON completo -- así el schema
JSON Schema (schemas/*.schema.json) sigue siendo la fuente de verdad del contrato, no el
mapeo a campos de Redis.
"""
from __future__ import annotations

import json
from typing import Any, Iterator

import redis

from meridian.config import settings

_INTENT_MAIN_STREAM = "meridian:intents:main"
_RESULT_MAIN_STREAM = "meridian:results:main"


def intent_stream_for_subagent(subagent_id: str) -> str:
    return f"meridian:intents:{subagent_id}"


def result_stream_for_gateway(gateway_id: str) -> str:
    return f"meridian:results:gateway:{gateway_id}"


def get_client() -> redis.Redis:
    return redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)


def publish(stream: str, message: dict[str, Any]) -> str:
    client = get_client()
    return client.xadd(stream, {"data": json.dumps(message)})


def publish_intent_to_main(intent: dict[str, Any]) -> str:
    return publish(_INTENT_MAIN_STREAM, intent)


def publish_result_to_main(result: dict[str, Any]) -> str:
    return publish(_RESULT_MAIN_STREAM, result)


def ensure_group(stream: str, group: str) -> None:
    client = get_client()
    try:
        client.xgroup_create(stream, group, id="0", mkstream=True)
    except redis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def consume(
    stream: str, group: str, consumer: str, count: int = 10, block_ms: int = 5000
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Lee mensajes nuevos de un consumer group y hace yield de (redis_message_id, payload).
    El caller es responsable de llamar `ack()` tras procesar cada mensaje."""
    ensure_group(stream, group)
    client = get_client()
    response = client.xreadgroup(group, consumer, {stream: ">"}, count=count, block=block_ms)
    for _stream_name, entries in response or []:
        for entry_id, fields in entries:
            yield entry_id, json.loads(fields["data"])


def ack(stream: str, group: str, entry_id: str) -> None:
    get_client().xack(stream, group, entry_id)


def stream_info(stream: str) -> dict[str, Any]:
    client = get_client()
    try:
        length = client.xlen(stream)
        groups = client.xinfo_groups(stream)
    except redis.ResponseError:
        return {"stream": stream, "exists": False}
    return {
        "stream": stream,
        "exists": True,
        "length": length,
        "groups": [
            {
                "name": g["name"],
                "consumers": g["consumers"],
                "pending": g["pending"],
                "lag": g.get("lag"),
            }
            for g in groups
        ],
    }
