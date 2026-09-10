from uuid import UUID

import typer

from meridian.cli.console import ok, print_record, print_records
from meridian.identity import repository

app = typer.Typer(help="Alta y consulta de subagentes.")


@app.command("create")
def create(
    tenant: str = typer.Option(..., "--tenant", help="tenant_id (uuid)"),
    name: str = typer.Option(..., "--name"),
    domain: str = typer.Option(..., "--domain", help="Etiqueta libre (tú decides qué significa: 'inventario', 'archivos', 'investigación', lo que sea)."),
) -> None:
    subagent = repository.create_subagent(UUID(tenant), name, domain)
    ok(f"subagente '{name}' creado")
    print_record(subagent)


@app.command("list")
def list_(tenant: str | None = typer.Option(None, "--tenant")) -> None:
    print_records(repository.list_subagents(UUID(tenant) if tenant else None), title="Subagentes")
