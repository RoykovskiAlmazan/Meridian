from uuid import UUID

import typer

from meridian.cli.console import ok, print_records
from meridian.identity import repository

app = typer.Typer(help="Allowlist explícita gateway x subagente (nunca implícita).")


@app.command("set")
def set_(
    gateway: str = typer.Option(..., "--gateway", help="gateway_id (uuid)"),
    subagent: str = typer.Option(..., "--subagent", help="subagent_id (uuid)"),
    intents: str = typer.Option(..., "--intents", help="lista separada por comas, ej: <dominio>.<accion>,<dominio>.<otra_accion> -- el dominio lo define quien instale Meridian, no es fijo"),
) -> None:
    allowed_intents = [i.strip() for i in intents.split(",") if i.strip()]
    repository.set_allowlist(UUID(gateway), UUID(subagent), allowed_intents)
    ok(f"allowlist actualizada: gateway={gateway} subagent={subagent} intents={allowed_intents}")


@app.command("list")
def list_(
    gateway: str | None = typer.Option(None, "--gateway"),
    subagent: str | None = typer.Option(None, "--subagent"),
) -> None:
    entries = repository.list_allowlist(
        UUID(gateway) if gateway else None,
        UUID(subagent) if subagent else None,
    )
    print_records(entries, title="Allowlist")


@app.command("set-sub")
def set_sub(
    parent: str = typer.Option(..., "--parent", help="subagent_id (uuid) del subagente padre que delega"),
    child: str = typer.Option(..., "--child", help="subagent_id (uuid) del sub-subagente autorizado a recibir la delegación"),
    intents: str = typer.Option(..., "--intents", help="lista separada por comas -- mismo formato que `allow set`"),
) -> None:
    """Allowlist explícita subagente padre -> sub-subagente (ver docs/design/0014-sub-subagents.md).
    Igual de estricta que gateway -> subagente: sin esta entrada, un subagente no puede
    delegar en otro aunque exista la relación `parent_subagent_id`."""
    allowed_intents = [i.strip() for i in intents.split(",") if i.strip()]
    repository.set_subagent_delegation_allowlist(UUID(parent), UUID(child), allowed_intents)
    ok(f"allowlist de delegación actualizada: parent={parent} child={child} intents={allowed_intents}")


@app.command("list-sub")
def list_sub(parent: str | None = typer.Option(None, "--parent")) -> None:
    entries = repository.list_subagent_delegation_allowlist(UUID(parent) if parent else None)
    print_records(entries, title="Allowlist de delegación (sub-subagentes)")
