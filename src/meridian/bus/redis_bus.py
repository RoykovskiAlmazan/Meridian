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
from collections.abc import Iterator
from typing import Any

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


def claim_stale(
    stream: str, group: str, consumer: str, min_idle_ms: int = 60_000, max_deliveries: int = 3
) -> Iterator[tuple[str, dict[str, Any]]]:
    """Reclama mensajes que quedaron "pending" (leídos por un consumer que murió antes de
    hacer ack) más de `min_idle_ms` sin confirmar, vía XAUTOCLAIM. Si un mensaje ya se
    entregó `max_deliveries` veces o más, se manda a `<stream>:dead` (dead-letter) y se
    hace ack del original -- deja de reintentarse solo, pero no se pierde: queda auditable
    en el stream de dead-letter para revisión manual. Los demás se devuelven al caller para
    que los reprocese con el mismo `handler`, igual que un mensaje nuevo.

    Sin esto, un subagente que se cae a mitad de procesar un intent lo deja "colgado" para
    siempre en el pending list del consumer group -- ver docs/design/0012-improvement-opportunities.md.
    """
    ensure_group(stream, group)
    client = get_client()
    dead_letter_stream = f"{stream}:dead"

    _cursor, claimed, _deleted = client.xautoclaim(
        stream, group, consumer, min_idle_time=min_idle_ms, start_id="0-0", count=50
    )
    for entry_id, fields in claimed:
        if not fields:  # el mensaje ya no existe en el stream (fue trimmed)
            client.xack(stream, group, entry_id)
            continue

        delivery_count = None
        pending_detail = client.xpending_range(stream, group, min=entry_id, max=entry_id, count=1)
        if pending_detail:
            delivery_count = pending_detail[0]["times_delivered"]

        if delivery_count is not None and delivery_count > max_deliveries:
            client.xadd(dead_letter_stream, {
                "data": fields["data"],
                "original_entry_id": entry_id,
                "delivery_count": str(delivery_count),
            })
            client.xack(stream, group, entry_id)
            continue  # no se reprocesa -- queda constancia en <stream>:dead

        yield entry_id, json.loads(fields["data"])


# ---- estado de fan-in (persistente en Redis, no en memoria del proceso) --------
# Antes vivía en un dict de Python dentro de main_agent/service.py: si el `main` se
# reiniciaba a mitad de un fan-out, la agregación en curso se perdía (documentado desde el
# entregable 2). Guardarlo en Redis lo hace sobrevivir un reinicio del `main`.

_FANIN_TTL_SECONDS = 24 * 60 * 60


def _fanin_key(correlation_id: str) -> str:
    return f"meridian:fanin:{correlation_id}"


def init_fanin(correlation_id: str, gateway_id: str, expected_subagent_ids: list[str]) -> None:
    client = get_client()
    key = _fanin_key(correlation_id)
    client.hset(key, mapping={
        "gateway_id": gateway_id,
        "expected": json.dumps(expected_subagent_ids),
        "results": json.dumps({}),
    })
    client.expire(key, _FANIN_TTL_SECONDS)


def add_fanin_result(correlation_id: str, subagent_id: str, result: dict[str, Any]) -> dict[str, Any] | None:
    """Agrega un resultado a la agregación en curso. Devuelve el estado completo
    (gateway_id/expected/results) si ya existe la fila en Redis, o None si no existe
    (mensaje huérfano: no hay fan-out en curso con ese correlation_id -- ya se agregó y
    se borró, o nunca se inicializó)."""
    client = get_client()
    key = _fanin_key(correlation_id)
    raw = client.hgetall(key)
    if not raw:
        return None

    results = json.loads(raw["results"])
    results[subagent_id] = result
    client.hset(key, "results", json.dumps(results))

    return {
        "gateway_id": raw["gateway_id"],
        "expected": json.loads(raw["expected"]),
        "results": results,
    }


def delete_fanin(correlation_id: str) -> None:
    get_client().delete(_fanin_key(correlation_id))


def tail_gateway_results(gateway_id: str, limit: int = 20) -> list[dict[str, Any]]:
    """Lee (sin consumir/hacer ack -- XRANGE, igual que `mock_gateway`'s `/result`) las
    últimas `limit` entradas del stream de resultados agregados de un gateway, más reciente
    primero. Sirve para inspeccionar desde `meridianctl results tail` el resultado real de
    un intent disparado por cualquier gateway (cron incluido, que no tiene un endpoint HTTP
    propio para consultarlo como mock_gateway sí tiene)."""
    client = get_client()
    stream = result_stream_for_gateway(gateway_id)
    try:
        entries = client.xrevrange(stream, count=limit)
    except redis.ResponseError:
        return []
    return [json.loads(fields["data"]) for _entry_id, fields in entries]


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
