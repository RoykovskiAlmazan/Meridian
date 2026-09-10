from uuid import UUID

import typer

from meridian.identity import repository

app = typer.Typer(help="Alta y consulta de subagentes.")


@app.command("create")
def create(
    tenant: str = typer.Option(..., "--tenant", help="tenant_id (uuid)"),
    name: str = typer.Option(..., "--name"),
    domain: str = typer.Option(..., "--domain"),
) -> None:
    subagent = repository.create_subagent(UUID(tenant), name, domain)
    typer.echo(subagent)


@app.command("list")
def list_(tenant: str | None = typer.Option(None, "--tenant")) -> None:
    for sa in repository.list_subagents(UUID(tenant) if tenant else None):
        typer.echo(sa)
