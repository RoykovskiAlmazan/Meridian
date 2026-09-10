"""Gateway de prueba para el MVP (entregable 2): expone un endpoint HTTP mínimo que
arma un TaskIntent y lo publica al bus. Sirve para probar el flujo end-to-end
gateway -> main -> subagentes -> main -> gateway sin necesitar un canal real
(WhatsApp/Telegram/etc.) todavía.
"""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from meridian.bus import redis_bus
from meridian.identity import repository
from meridian.messages import new_task_intent

app = FastAPI(title="Meridian mock gateway")


class SendIntentRequest(BaseModel):
    tenant_id: str
    gateway_id: str
    intent_type: str
    subagent_ids: list[str]
    payload: dict[str, Any] = {}


@app.post("/intent")
def send_intent(req: SendIntentRequest) -> dict[str, Any]:
    gateway = repository.get_gateway(UUID(req.gateway_id))
    if gateway is None:
        raise HTTPException(status_code=404, detail="gateway not found")
    if gateway["status"] != "active":
        raise HTTPException(status_code=403, detail="gateway is revoked")

    intent = new_task_intent(
        tenant_id=req.tenant_id,
        gateway_id=req.gateway_id,
        gateway_type=gateway["type"],
        scopes=[],  # informativo; el main recalcula autorización real contra Postgres
        intent_type=req.intent_type,
        subagent_ids=req.subagent_ids,
        payload=req.payload,
    )
    redis_bus.publish_intent_to_main(intent)
    return {"message_id": intent["message_id"], "correlation_id": intent["correlation_id"]}


@app.get("/result/{correlation_id}")
def get_result(correlation_id: str, gateway_id: str) -> dict[str, Any]:
    """Busca en el stream de resultados de este gateway una entrada con ese correlation_id.
    Polling simple (XRANGE) -- suficiente para probar el MVP, no para un gateway real de producción."""
    client = redis_bus.get_client()
    stream = redis_bus.result_stream_for_gateway(gateway_id)
    for _entry_id, fields in client.xrange(stream):
        payload = json.loads(fields["data"])
        if payload["correlation_id"] == correlation_id:
            return payload
    return {"status": "pending"}
