import getpass
from datetime import UTC, datetime
from uuid import UUID

import typer

from meridian.bus import redis_bus
from meridian.cli.console import fail, ok, print_records
from meridian.identity import repository
from meridian.messages import new_task_result

app = typer.Typer(help="Tareas que quedaron detenidas esperando que un humano las apruebe o rechace, según la policy del subagente.")


@app.command(
    "list",
    help="Lista los intents retenidos por policy (requires_approval_intents), por default los que siguen 'pending'.",
    epilog="Ejemplos:\n\n  meridianctl approvals list\n  meridianctl approvals list --status denied --tenant 697580ae-...",
)
def list_(
    status: str = typer.Option("pending", "--status", help="pending | approved | denied"),
    tenant: str | None = typer.Option(None, "--tenant"),
) -> None:
    print_records(
        repository.list_pending_approvals(status, UUID(tenant) if tenant else None),
        title=f"Approvals ({status})",
    )


@app.command(
    "approve",
    help="Aprueba una aprobación pendiente: reenvía el intent original al subagente como si nunca se hubiera detenido.",
    epilog="Ejemplo:\n\n  meridianctl approvals approve --id 3f1a9c2e-...",
)
def approve(id_: str = typer.Option(..., "--id")) -> None:
    approval = repository.get_pending_approval(UUID(id_))
    if approval is None:
        fail(f"no existe una aprobación con id={id_}")
        raise typer.Exit(code=1)
    if approval["status"] != "pending":
        fail(f"la aprobación {id_} ya fue decidida (status={approval['status']})")
        raise typer.Exit(code=1)

    redis_bus.publish(redis_bus.intent_stream_for_subagent(str(approval["subagent_id"])), approval["intent"])
    repository.decide_pending_approval(UUID(id_), "approved", getpass.getuser())
    repository.log_audit(
        approval["tenant_id"], approval["correlation_id"], UUID(approval["intent"]["message_id"]),
        "main", "approved", {"subagent_id": str(approval["subagent_id"]), "approval_id": id_, "decided_by": getpass.getuser()},
    )
    ok(f"aprobación {id_} aprobada -- intent reenviado a subagent={approval['subagent_id']}")


@app.command(
    "deny",
    help="Deniega una aprobación pendiente: publica un TaskResult de error para no dejar el fan-in colgado, el subagente nunca la ejecuta.",
    epilog="Ejemplo:\n\n  meridianctl approvals deny --id 3f1a9c2e-...",
)
def deny(id_: str = typer.Option(..., "--id")) -> None:
    approval = repository.get_pending_approval(UUID(id_))
    if approval is None:
        fail(f"no existe una aprobación con id={id_}")
        raise typer.Exit(code=1)
    if approval["status"] != "pending":
        fail(f"la aprobación {id_} ya fue decidida (status={approval['status']})")
        raise typer.Exit(code=1)

    intent = approval["intent"]
    result = new_task_result(
        correlation_id=str(approval["correlation_id"]),
        in_response_to=intent["message_id"],
        tenant_id=str(approval["tenant_id"]),
        subagent_id=str(approval["subagent_id"]),
        status="error",
        started_at=datetime.now(UTC).isoformat(),
        error={"code": "approval_denied", "message": "Un operador denegó la aprobación requerida para este intent."},
    )
    redis_bus.publish_result_to_main(result)

    repository.decide_pending_approval(UUID(id_), "denied", getpass.getuser())
    repository.log_audit(
        approval["tenant_id"], approval["correlation_id"], UUID(intent["message_id"]),
        "main", "approval_denied", {"subagent_id": str(approval["subagent_id"]), "approval_id": id_, "decided_by": getpass.getuser()},
    )
    ok(f"aprobación {id_} denegada -- se publicó un TaskResult de error para no dejar el fan-in colgado")
