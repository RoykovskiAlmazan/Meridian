from uuid import UUID

import typer
from croniter import croniter

from meridian.cli.console import fail, ok, print_record, print_records
from meridian.identity import repository

app = typer.Typer(help="Programa tareas repetidas (como un crontab de Linux) para disparar un subagente automáticamente cada cierto tiempo, sin que nadie tenga que pedirlo a mano.")


@app.command(
    "create",
    help="Da de alta un job programado: qué se dispara, cuándo, y contra qué subagentes. Requiere que ya exista la allowlist (`allow set`) para el intent_type que uses.",
    epilog=(
        "Ejemplo (cada hora, contra un subagente propio):\n\n"
        "  meridianctl cron create --tenant 697580ae-... --gateway b2f22873-... \\\n"
        "    --name mi-job --schedule '@hourly' --intent-type mi_dominio.mi_accion \\\n"
        "    --subagents 88fc9c58-... --payload '{\"lo\":\"que necesite tu handle\"}'"
    ),
)
def create(
    tenant: str = typer.Option(..., "--tenant", help="tenant_id (uuid)"),
    gateway: str = typer.Option(..., "--gateway", help="gateway_id (uuid) de tipo cron, dado de alta con `gateway create --type cron`"),
    name: str = typer.Option(..., "--name"),
    schedule: str = typer.Option(..., "--schedule", help='Expresión cron estándar de 5 campos ("*/15 * * * *") o un macro tipo crontab (@hourly, @daily, @weekly, @monthly, @yearly).'),
    intent_type: str = typer.Option(..., "--intent-type", help="ej. <dominio>.<accion>, definido por quien instala Meridian"),
    subagents: str = typer.Option(..., "--subagents", help="subagent_ids separados por coma"),
    payload: str = typer.Option("{}", "--payload", help="JSON del payload a enviar en cada disparo"),
) -> None:
    import json

    if not croniter.is_valid(schedule):
        fail(f"'{schedule}' no es una expresión cron válida ni un macro reconocido (@hourly, @daily, @weekly, @monthly, @yearly, o 5 campos estándar).")
        raise typer.Exit(code=1)

    subagent_ids = [s.strip() for s in subagents.split(",") if s.strip()]
    job = repository.create_cron_job(
        UUID(tenant), UUID(gateway), name, schedule, intent_type, subagent_ids, json.loads(payload)
    )
    ok(f"cron job '{name}' creado")
    print_record(job)


@app.command(
    "list",
    epilog="Ejemplo:\n\n  meridianctl cron list --tenant 697580ae-...",
)
def list_(tenant: str | None = typer.Option(None, "--tenant")) -> None:
    print_records(repository.list_cron_jobs(UUID(tenant) if tenant else None), title="Cron jobs")


@app.command(
    "enable",
    help="Reactiva un job deshabilitado -- no cambia last_run_at, así que puede disparar de inmediato si ya 'tocaba' según su schedule.",
    epilog="Ejemplo:\n\n  meridianctl cron enable --id a5601603-...",
)
def enable(id_: str = typer.Option(..., "--id")) -> None:
    repository.set_cron_job_enabled(UUID(id_), True)
    ok(f"cron_job {id_} habilitado")


@app.command(
    "disable",
    help="Detiene un job sin borrarlo -- queda en `cron list` para reactivarlo después con `enable`.",
    epilog="Ejemplo:\n\n  meridianctl cron disable --id a5601603-...",
)
def disable(id_: str = typer.Option(..., "--id")) -> None:
    repository.set_cron_job_enabled(UUID(id_), False)
    ok(f"cron_job {id_} deshabilitado")
