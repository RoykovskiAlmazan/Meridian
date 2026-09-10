from pathlib import Path

import typer

from meridian.cli.console import ok
from meridian.secrets.vault_client import put_secret

app = typer.Typer(help="Guarda contraseñas y API keys de forma segura en Vault -- nunca quedan en texto plano en el repo, en la terminal, ni en el historial de comandos.")


def read_secret_value(prompt_text: str, from_file: str | None) -> str:
    """Prompt oculto por defecto (no se puede automatizar por pipe en Windows/Linux --
    es intencional, evita que un secreto quede en el historial de shell). Para scripts/CI,
    `--from-file <ruta>` lee el valor de un archivo local en vez de pedirlo interactivo --
    sigue sin pasar por argumentos de CLI ni por variables de entorno del proceso, que son
    más fáciles de exponer por accidente (logs de CI, `docker inspect`, `/proc`)."""
    if from_file:
        return Path(from_file).read_text(encoding="utf-8").strip()
    return typer.prompt(prompt_text, hide_input=True)


@app.command(
    "put",
    epilog=(
        "Ejemplos:\n\n"
        "  meridianctl secrets put --path llm/anthropic --field api_key   # pide el valor de forma oculta\n"
        "  meridianctl secrets put --path llm/openai --from-file clave.txt # scripts/CI, sin prompt interactivo"
    ),
)
def put(
    mount: str = typer.Option("secret", "--mount"),
    path: str = typer.Option(..., "--path", help="ej. llm/anthropic"),
    field: str = typer.Option("api_key", "--field"),
    from_file: str = typer.Option(None, "--from-file", help="Lee el valor de un archivo local en vez de pedirlo interactivo (para scripts/CI). Borra el archivo después de usarlo."),
) -> None:
    """Guarda un secreto en Vault. Por defecto pide el valor de forma oculta (nunca
    aparece en la terminal, el historial de shell, ni se lo pasas a Claude/a nadie más).
    Imprime el credential_ref resultante para usarlo en otros comandos (ej.
    `meridianctl llm set`)."""
    value = read_secret_value("Valor del secreto", from_file)
    credential_ref = put_secret(mount, path, field, value)
    ok(f"guardado. credential_ref = {credential_ref}")
