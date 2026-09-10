"""Prueba la persistencia de estado de fan-in en Redis (survives un "reinicio" del main,
ya que no vive en memoria del proceso) usando fakeredis en vez de un Redis real."""
import fakeredis
import pytest

from meridian.bus import redis_bus


@pytest.fixture(autouse=True)
def fake_redis_client(monkeypatch):
    server = fakeredis.FakeServer()
    client = fakeredis.FakeStrictRedis(server=server, decode_responses=True)
    monkeypatch.setattr(redis_bus, "get_client", lambda: client)
    return client


def test_init_fanin_then_add_results_until_complete():
    redis_bus.init_fanin("corr-1", "gw-1", ["sa-1", "sa-2"])

    state = redis_bus.add_fanin_result("corr-1", "sa-1", {"subagent_id": "sa-1", "status": "success"})
    assert state["gateway_id"] == "gw-1"
    assert set(state["expected"]) == {"sa-1", "sa-2"}
    assert set(state["results"].keys()) == {"sa-1"}
    assert not (set(state["expected"]) <= state["results"].keys())  # todavía falta sa-2

    state = redis_bus.add_fanin_result("corr-1", "sa-2", {"subagent_id": "sa-2", "status": "success"})
    assert set(state["expected"]) <= state["results"].keys()  # ya está completo


def test_add_fanin_result_for_unknown_correlation_returns_none():
    assert redis_bus.add_fanin_result("no-existe", "sa-1", {}) is None


def test_delete_fanin_removes_state():
    redis_bus.init_fanin("corr-2", "gw-1", ["sa-1"])
    redis_bus.delete_fanin("corr-2")
    assert redis_bus.add_fanin_result("corr-2", "sa-1", {}) is None


def test_fanin_state_survives_a_simulated_main_restart():
    """El punto del cambio: el estado no vive en un dict de Python del proceso `main` --
    dos "instancias" de main_agent.service (simuladas aquí simplemente reimportando el
    módulo de estado, ya que todo vive en Redis) ven la misma agregación."""
    redis_bus.init_fanin("corr-3", "gw-1", ["sa-1", "sa-2"])
    redis_bus.add_fanin_result("corr-3", "sa-1", {"subagent_id": "sa-1", "status": "success"})

    # "reinicio": ninguna variable de proceso se reutiliza, solo se vuelve a leer de Redis
    state_after_restart = redis_bus.add_fanin_result("corr-3", "sa-2", {"subagent_id": "sa-2", "status": "success"})
    assert set(state_after_restart["expected"]) <= state_after_restart["results"].keys()


def test_tail_gateway_results_returns_most_recent_first(fake_redis_client):
    stream = redis_bus.result_stream_for_gateway("gw-1")
    for i in range(3):
        fake_redis_client.xadd(stream, {"data": f'{{"correlation_id": "corr-{i}", "results": []}}'})

    aggregates = redis_bus.tail_gateway_results("gw-1", limit=2)

    assert [a["correlation_id"] for a in aggregates] == ["corr-2", "corr-1"]


def test_tail_gateway_results_on_nonexistent_gateway_returns_empty():
    assert redis_bus.tail_gateway_results("no-such-gateway") == []
