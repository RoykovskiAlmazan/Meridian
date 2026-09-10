from uuid import UUID

import typer

from meridian.cli.console import ok, print_record, print_records
from meridian.identity import repository

app = typer.Typer(help="Un subagente es el trabajador que ejecuta una tarea específica -- tú escribes qué hace. Aquí lo das de alta y consultas.")


@app.command(
    "create",
    help="Da de alta un subagente: solo la identidad (id/nombre/dominio) -- la lógica que ejecuta la escribes tú aparte en src/meridian/subagents/, y necesita allowlist (`allow set`) para poder recibir intents.",
    epilog=(
        "Ejemplos:\n\n"
        "  meridianctl subagent create --tenant 697580ae-... --name mi-subagente --domain lo-que-sea\n"
        "  meridianctl subagent create --tenant 697580ae-... --name sub-tarea --domain research --parent 88fc9c58-..."
    ),
)
def create(
    tenant: str = typer.Option(..., "--tenant", help="tenant_id (uuid)"),
    name: str = typer.Option(..., "--name"),
    domain: str = typer.Option(..., "--domain", help="Etiqueta libre (tú decides qué significa: 'inventario', 'archivos', 'investigación', lo que sea)."),
    parent: str = typer.Option(None, "--parent", help="subagent_id (uuid) de otro subagente si este es un sub-subagente delegado (ver docs/design/0014-sub-subagents.md). Omitir para un subagente de primer nivel."),
) -> None:
    subagent = repository.create_subagent(UUID(tenant), name, domain, UUID(parent) if parent else None)
    ok(f"subagente '{name}' creado" + (f" (hijo de {parent})" if parent else ""))
    print_record(subagent)


@app.command(
    "list",
    epilog="Ejemplo:\n\n  meridianctl subagent list --tenant 697580ae-...",
)
def list_(tenant: str | None = typer.Option(None, "--tenant")) -> None:
    print_records(repository.list_subagents(UUID(tenant) if tenant else None), title="Subagentes")
