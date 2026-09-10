import typer

from meridian.cli.console import ok, print_record, print_records
from meridian.identity import repository

app = typer.Typer(help="Un tenant es tu organización (o un cliente, si operas para varios) dentro de Meridian -- el primer paso antes de crear nada más. Aquí lo das de alta y consultas.")


@app.command(
    "create",
    help="Crea un tenant nuevo -- el contenedor de aislamiento para un cliente/operador/caso de uso. Usa uno distinto por cada dominio que no deba mezclarse (datos, allowlists y policies nunca cruzan tenants).",
    epilog="Ejemplo:\n\n  meridianctl tenant create --name sandbox-personal",
)
def create(name: str = typer.Option(..., "--name")) -> None:
    tenant = repository.create_tenant(name)
    ok(f"tenant '{name}' creado")
    print_record(tenant)


@app.command(
    "list",
    epilog="Ejemplo:\n\n  meridianctl tenant list",
)
def list_() -> None:
    print_records(repository.list_tenants(), title="Tenants")
