"""Pruebas de authorize_and_route sin Postgres real -- se sustituyen las funciones de
`meridian.identity.repository` por fakes en memoria (monkeypatch)."""
import uuid

import pytest

from meridian.main_agent import core

TENANT = str(uuid.uuid4())
OTHER_TENANT = str(uuid.uuid4())
GATEWAY = str(uuid.uuid4())
SUBAGENT_A = str(uuid.uuid4())
SUBAGENT_B = str(uuid.uuid4())


def make_intent(subagent_ids, intent_type="demo.hello", tenant_id=TENANT, gateway_id=GATEWAY):
    return {
        "tenant_id": tenant_id,
        "origin": {"gateway_id": gateway_id},
        "intent": {"type": intent_type, "target": {"subagent_ids": subagent_ids}},
    }


@pytest.fixture
def fake_repo(monkeypatch):
    gateways = {
        GATEWAY: {"tenant_id": uuid.UUID(TENANT), "status": "active"},
    }
    subagents = {
        SUBAGENT_A: {"tenant_id": uuid.UUID(TENANT), "status": "active"},
        SUBAGENT_B: {"tenant_id": uuid.UUID(TENANT), "status": "active"},
    }
    allowlist = {
        (GATEWAY, SUBAGENT_A): {"allowed_intents": ["demo.hello"]},
    }

    monkeypatch.setattr(core.repository, "get_gateway", lambda gid: gateways.get(str(gid)))
    monkeypatch.setattr(core.repository, "get_subagent", lambda sid: subagents.get(str(sid)))
    monkeypatch.setattr(
        core.repository,
        "get_allowlist_entry",
        lambda gid, sid: allowlist.get((str(gid), str(sid))),
    )
    return {"gateways": gateways, "subagents": subagents, "allowlist": allowlist}


def test_allowed_subagent_is_routed(fake_repo):
    decision = core.authorize_and_route(make_intent([SUBAGENT_A]))
    assert decision.allowed_subagent_ids == [SUBAGENT_A]
    assert decision.denied == []


def test_subagent_without_allowlist_entry_is_denied(fake_repo):
    decision = core.authorize_and_route(make_intent([SUBAGENT_B]))
    assert decision.allowed_subagent_ids == []
    assert decision.denied == [(SUBAGENT_B, "not_in_allowlist")]


def test_fan_out_partial_denial_does_not_block_allowed_ones(fake_repo):
    decision = core.authorize_and_route(make_intent([SUBAGENT_A, SUBAGENT_B]))
    assert decision.allowed_subagent_ids == [SUBAGENT_A]
    assert decision.denied == [(SUBAGENT_B, "not_in_allowlist")]


def test_intent_type_not_in_allowlist_is_denied(fake_repo):
    decision = core.authorize_and_route(make_intent([SUBAGENT_A], intent_type="demo.other"))
    assert decision.denied == [(SUBAGENT_A, "intent_not_allowed")]


def test_unknown_gateway_denies_everything(fake_repo):
    decision = core.authorize_and_route(make_intent([SUBAGENT_A], gateway_id=str(uuid.uuid4())))
    assert decision.allowed_subagent_ids == []
    assert decision.denied[0][1] == "gateway_not_found"


def test_revoked_gateway_denies_everything(fake_repo):
    fake_repo["gateways"][GATEWAY]["status"] = "revoked"
    decision = core.authorize_and_route(make_intent([SUBAGENT_A]))
    assert decision.denied == [(SUBAGENT_A, "gateway_revoked")]


def test_tenant_mismatch_on_gateway_denies_everything(fake_repo):
    decision = core.authorize_and_route(make_intent([SUBAGENT_A], tenant_id=OTHER_TENANT))
    assert decision.denied == [(SUBAGENT_A, "tenant_mismatch")]


def test_unknown_subagent_is_denied(fake_repo):
    missing = str(uuid.uuid4())
    decision = core.authorize_and_route(make_intent([missing]))
    assert decision.denied == [(missing, "subagent_not_found")]


def test_revoked_subagent_is_denied(fake_repo):
    fake_repo["subagents"][SUBAGENT_A]["status"] = "revoked"
    decision = core.authorize_and_route(make_intent([SUBAGENT_A]))
    assert decision.denied == [(SUBAGENT_A, "subagent_revoked")]


def test_never_trusts_scopes_declared_in_message(fake_repo):
    """El mensaje puede declarar lo que quiera en origin.scopes -- authorize_and_route ni
    siquiera lo lee. Ver docstring de core.py: la regla no negociable es recalcular contra
    Postgres, nunca confiar en el payload entrante."""
    intent = make_intent([SUBAGENT_A])
    intent["origin"]["scopes"] = ["admin.everything"]
    decision = core.authorize_and_route(intent)
    assert decision.allowed_subagent_ids == [SUBAGENT_A]
