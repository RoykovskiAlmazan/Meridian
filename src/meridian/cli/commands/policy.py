import json
from uuid import UUID

import typer

from meridian.cli.console import ok, print_record
from meridian.identity import repository
from meridian.policy import DEFAULT_POLICY, resolve_policy, validate_policy

app = typer.Typer(help="Reglas de comportamiento de un subagente: qué tareas necesitan aprobación humana antes de ejecutarse, qué tan agresivo reintenta, y qué tono usar.")


@app.command(
    "set",
    help="Reemplaza la policy completa de un subagente desde un archivo JSON (no acepta flags sueltos -- ver schemas/subagent_policy.v1.schema.json para el shape completo). Sin policy propia, un subagente hereda el default conservador (`show-default`).",
    epilog=(
        "Ejemplo (subagente de solo lectura, sin aprobación):\n\n"
        "  cat > policy.json <<'EOF'\n"
        "  {\n"
        '    "schema_version": "1.0",\n'
        '    "requires_approval_intents": [],\n'
        '    "destructive": { "allowed": false, "requires_approval": true }\n'
        "  }\n"
        "  EOF\n"
        "  meridianctl policy set --subagent 88fc9c58-... --file policy.json"
    ),
)
def set_(
    subagent: str = typer.Option(..., "--subagent", help="subagent_id (uuid)"),
    file: str = typer.Option(..., "--file", help="Ruta a un JSON con la policy, validado contra schemas/subagent_policy.v1.schema.json"),
) -> None:
    with open(file, encoding="utf-8") as f:
        policy = json.load(f)
    validate_policy(policy)
    repository.set_subagent_policy(UUID(subagent), policy)
    ok(f"policy actualizada para subagent={subagent}")


@app.command(
    "get",
    help="Muestra la policy efectiva de un subagente -- la suya propia si tiene una, si no el default conservador resuelto (nunca None).",
    epilog="Ejemplo:\n\n  meridianctl policy get --subagent 88fc9c58-...",
)
def get(subagent: str = typer.Option(..., "--subagent")) -> None:
    stored = repository.get_subagent_policy(UUID(subagent))
    print_record(resolve_policy(stored))


@app.command(
    "show-default",
    epilog="Ejemplo:\n\n  meridianctl policy show-default",
)
def show_default() -> None:
    """Muestra la policy conservadora que aplica a un subagente sin policy configurada."""
    print_record(DEFAULT_POLICY)
