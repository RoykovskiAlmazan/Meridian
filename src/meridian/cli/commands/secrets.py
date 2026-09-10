import typer

from meridian.secrets.vault_client import put_secret

app = typer.Typer(help="Alta de secretos en Vault (API keys de LLM, tokens, etc.) -- nunca en texto plano en el repo.")


@app.command("put")
def put(
    mount: str = typer.Option("secret", "--mount"),
    path: str = typer.Option(..., "--path", help="ej. llm/anthropic"),
    field: str = typer.Option("api_key", "--field"),
) -> None:
    """Pide el valor de forma oculta (nunca aparece en la terminal, el historial de shell,
    ni se lo pasas a Claude/a nadie más) y lo guarda en Vault. Imprime el credential_ref
    resultante para usarlo en otros comandos (ej. `meridianctl llm set`)."""
    value = typer.prompt("Valor del secreto", hide_input=True)
    credential_ref = put_secret(mount, path, field, value)
    typer.echo(f"guardado. credential_ref = {credential_ref}")
