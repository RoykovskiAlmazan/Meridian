from uuid import UUID

import typer

from meridian.cli.commands.secrets import read_secret_value
from meridian.cli.console import ok, print_record, print_records
from meridian.identity import repository
from meridian.secrets.vault_client import put_secret

app = typer.Typer(help="Alta, consulta, rotación y revocación de gateways.")


@app.command("create")
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


@app.command("list")
def list_(tenant: str | None = typer.Option(None, "--tenant")) -> None:
    print_records(repository.list_gateways(UUID(tenant) if tenant else None), title="Gateways")


@app.command("revoke")
def revoke(id_: str = typer.Option(..., "--id")) -> None:
    repository.revoke_gateway(UUID(id_))
    ok(f"gateway {id_} revocado")


@app.command("rotate-credential")
def rotate_credential(
    id_: str = typer.Option(..., "--id"),
    from_file: str = typer.Option(None, "--from-file", help="Lee la nueva credencial de un archivo local en vez de pedirla interactivo (para scripts/CI)."),
) -> None:
    token = read_secret_value("Nueva credencial del gateway", from_file)
    credential_ref = put_secret("secret", f"gateways/{id_}", "token", token)
    repository.rotate_gateway_credential(UUID(id_), credential_ref)
    ok(f"credencial de gateway {id_} rotada -> {credential_ref}")
