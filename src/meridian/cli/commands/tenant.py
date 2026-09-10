import typer

from meridian.cli.console import ok, print_record, print_records
from meridian.identity import repository

app = typer.Typer(help="Alta y consulta de tenants.")


@app.command("create")
def create(name: str = typer.Option(..., "--name")) -> None:
    tenant = repository.create_tenant(name)
    ok(f"tenant '{name}' creado")
    print_record(tenant)


@app.command("list")
def list_() -> None:
    print_records(repository.list_tenants(), title="Tenants")
