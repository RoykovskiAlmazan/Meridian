import typer

from meridian.identity import repository

app = typer.Typer(help="Alta y consulta de tenants.")


@app.command("create")
def create(name: str = typer.Option(..., "--name")) -> None:
    tenant = repository.create_tenant(name)
    typer.echo(tenant)


@app.command("list")
def list_() -> None:
    for tenant in repository.list_tenants():
        typer.echo(tenant)
