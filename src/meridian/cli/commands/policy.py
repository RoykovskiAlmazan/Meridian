import json
from uuid import UUID

import typer

from meridian.cli.console import ok, print_record
from meridian.identity import repository
from meridian.policy import DEFAULT_POLICY, resolve_policy, validate_policy

app = typer.Typer(help="Comportamiento configurable por subagente (qué es irreversible, aprobación, reintentos, tono).")


@app.command("set")
def set_(
    subagent: str = typer.Option(..., "--subagent", help="subagent_id (uuid)"),
    file: str = typer.Option(..., "--file", help="Ruta a un JSON con la policy, validado contra schemas/subagent_policy.v1.schema.json"),
) -> None:
    with open(file, encoding="utf-8") as f:
        policy = json.load(f)
    validate_policy(policy)
    repository.set_subagent_policy(UUID(subagent), policy)
    ok(f"policy actualizada para subagent={subagent}")


@app.command("get")
def get(subagent: str = typer.Option(..., "--subagent")) -> None:
    stored = repository.get_subagent_policy(UUID(subagent))
    print_record(resolve_policy(stored))


@app.command("show-default")
def show_default() -> None:
    """Muestra la policy conservadora que aplica a un subagente sin policy configurada."""
    print_record(DEFAULT_POLICY)
