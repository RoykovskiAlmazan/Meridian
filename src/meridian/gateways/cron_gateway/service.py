"""Gateway de tipo cron (entregable 5): dispara TaskIntents en un horario configurado,
sin depender de ningún canal externo (WhatsApp/Telegram/etc.) -- ideal para validar el
contrato gateway -> main con un caso 100% determinista y sin credenciales de terceros.

Qué job corre, con qué horario, contra qué subagentes y con qué payload es 100% datos en
`cron_jobs` (Postgres), configurables vía `meridianctl cron create` -- Meridian no asume
ningún dominio, así que este gateway tampoco: puede disparar "sincroniza inventario cada
hora" o "revisa papers nuevos cada lunes", da igual, el gateway solo publica el TaskIntent
que la fila describe.
"""
from __future__ import annotations

import time
from datetime import UTC, datetime

from croniter import croniter

from meridian.bus.redis_bus import publish_intent_to_main
from meridian.identity import repository
from meridian.logging_setup import configure
from meridian.messages import new_task_intent

log = configure("cron_gateway")

POLL_INTERVAL_SECONDS = 15


def _is_due(job: dict) -> bool:
    baseline = job["last_run_at"] or job["created_at"]
    next_fire = croniter(job["schedule"], baseline).get_next(datetime)
    if next_fire.tzinfo is None:
        next_fire = next_fire.replace(tzinfo=UTC)
    return next_fire <= datetime.now(UTC)


def _fire(job: dict) -> None:
    now = datetime.now(UTC)
    intent = new_task_intent(
        tenant_id=str(job["tenant_id"]),
        gateway_id=str(job["gateway_id"]),
        gateway_type=job["gateway_type"],
        scopes=[],
        intent_type=job["intent_type"],
        subagent_ids=[str(s) for s in job["subagent_ids"]],
        payload=job["payload"],
    )
    publish_intent_to_main(intent)
    repository.mark_cron_job_run(job["id"], now)
    log.info(
        "fired cron_job=%s name=%s intent_type=%s correlation_id=%s",
        job["id"], job["name"], job["intent_type"], intent["correlation_id"],
    )


def run() -> None:
    log.info("cron gateway starting, polling every %ss", POLL_INTERVAL_SECONDS)
    while True:
        try:
            for job in repository.list_enabled_cron_jobs():
                if _is_due(job):
                    _fire(job)
        except Exception:
            log.exception("error checking/firing cron jobs, will retry next poll")
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
