import uuid

import jsonschema
import pytest

from meridian.messages import new_task_intent, new_task_result, validate_task_intent


def test_new_task_intent_round_trips_and_validates():
    intent = new_task_intent(
        tenant_id=str(uuid.uuid4()),
        gateway_id=str(uuid.uuid4()),
        gateway_type="internal_api",
        scopes=["demo.read"],
        intent_type="demo.hello",
        subagent_ids=[str(uuid.uuid4()), str(uuid.uuid4())],
        payload={"msg": "hola"},
    )
    assert intent["schema_version"] == "1.0"
    assert intent["intent"]["target"]["mode"] == "fan_out"
    validate_task_intent(intent)  # no exception


def test_new_task_intent_single_target_mode():
    intent = new_task_intent(
        tenant_id=str(uuid.uuid4()),
        gateway_id=str(uuid.uuid4()),
        gateway_type="cron",
        scopes=[],
        intent_type="demo.hello",
        subagent_ids=[str(uuid.uuid4())],
        payload={},
    )
    assert intent["intent"]["target"]["mode"] == "single"


def test_task_intent_rejects_bad_intent_type():
    with pytest.raises(jsonschema.ValidationError):
        new_task_intent(
            tenant_id=str(uuid.uuid4()),
            gateway_id=str(uuid.uuid4()),
            gateway_type="internal_api",
            scopes=[],
            intent_type="NOT VALID",
            subagent_ids=[str(uuid.uuid4())],
            payload={},
        )


def test_new_task_result_error_requires_error_field():
    result = new_task_result(
        correlation_id=str(uuid.uuid4()),
        in_response_to=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        subagent_id=str(uuid.uuid4()),
        status="error",
        started_at="2026-01-01T00:00:00+00:00",
        error={"code": "boom", "message": "algo falló"},
    )
    assert result["status"] == "error"
    assert result["error"]["code"] == "boom"


def test_new_task_result_success_has_no_error_required():
    result = new_task_result(
        correlation_id=str(uuid.uuid4()),
        in_response_to=str(uuid.uuid4()),
        tenant_id=str(uuid.uuid4()),
        subagent_id=str(uuid.uuid4()),
        status="success",
        started_at="2026-01-01T00:00:00+00:00",
        output={"ok": True},
    )
    assert result["error"] is None
