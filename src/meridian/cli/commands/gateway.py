from uuid import UUID

import typer

from meridian.cli.commands.secrets import read_secret_value
from meridian.cli.console import ok, print_record, print_records
from meridian.identity import repository
from meridian.secrets.vault_client import put_secret

app = typer.Typer(help="Un gateway es una vía de entrada de instrucciones (por horario, por API, etc.). Aquí lo creas, consultas, o le cambias/revocas la credencial.")


@app.command(
    "create",
    help="Da de alta un gateway (una vía de entrada de instrucciones) para un tenant. Pide la credencial de forma oculta y la guarda en Vault, nunca en Postgres ni en la terminal.",
    epilog=(
        "Ejemplo (gateway de tipo cron -- pedirá la credencial de forma oculta):\n\n"
        "  meridianctl gateway create --tenant 697580ae-... --type cron --name cron-sandbox"
    ),
)
def create(
    tenant: str = typer.Option(..., "--tenant", help="tenant_id (uuid)"),
    type_: str = typer.Option(..., "--type", help="whatsapp|telegram|internal_api|cron|web_panel|other"),
    name: str = typer.Option(..., "--name"),
    from_file: str = typer.Option(None, "--from-file", help="Lee la credencial de un archivo local en vez de pedirla interactivo (para scripts/CI)."),
) -> None:
    token = read_secret_value("Credencial del gateway (se guarda en Vault, nunca en Postgres)", from_file)
    gateway = repository.create_gateway(UUID(tenant), type_, name, credential_ref=None)
    credential_ref = put_secret("secret", f"gateways/{gateway['id']}", "token", token)
    repository.rotate_gateway_credential(gateway["id"], credential_ref)
    ok(f"gateway '{name}' creado")
    print_record({**gateway, "credential_ref": credential_ref})


@app.command(
    "list",
    epilog="Ejemplo:\n\n  meridianctl gateway list --tenant 697580ae-...",
)
def list_(tenant: str | None = typer.Option(None, "--tenant")) -> None:
    print_records(repository.list_gateways(UUID(tenant) if tenant else None), title="Gateways")


@app.command(
    "revoke",
    help="Marca un gateway como inactivo -- main ya no aceptará intents que digan venir de él, aunque siga en la tabla.",
    epilog="Ejemplo:\n\n  meridianctl gateway revoke --id b2f22873-...",
)
def revoke(id_: str = typer.Option(..., "--id")) -> None:
    repository.revoke_gateway(UUID(id_))
    ok(f"gateway {id_} revocado")


@app.command(
    "rotate-credential",
    help="Reemplaza la credencial de un gateway existente en Vault (prompt oculto o --from-file). El gateway sigue siendo el mismo, solo cambia el secreto.",
    epilog="Ejemplo:\n\n  meridianctl gateway rotate-credential --id b2f22873-...",
)
def rotate_credential(
    id_: str = typer.Option(..., "--id"),
    from_file: str = typer.Option(None, "--from-file", help="Lee la nueva credencial de un archivo local en vez de pedirla interactivo (para scripts/CI)."),
) -> None:
    token = read_secret_value("Nueva credencial del gateway", from_file)
    credential_ref = put_secret("secret", f"gateways/{id_}", "token", token)
    repository.rotate_gateway_credential(UUID(id_), credential_ref)
    ok(f"credencial de gateway {id_} rotada -> {credential_ref}")
