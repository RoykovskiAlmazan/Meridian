from uuid import UUID

import typer

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
    typer.echo(f"allowlist actualizada: gateway={gateway} subagent={subagent} intents={allowed_intents}")


@app.command("list")
def list_(
    gateway: str | None = typer.Option(None, "--gateway"),
    subagent: str | None = typer.Option(None, "--subagent"),
) -> None:
    entries = repository.list_allowlist(
        UUID(gateway) if gateway else None,
        UUID(subagent) if subagent else None,
    )
    for entry in entries:
        typer.echo(entry)
