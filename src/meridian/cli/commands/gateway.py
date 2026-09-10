from uuid import UUID

import typer

from meridian.identity import repository
from meridian.secrets.vault_client import put_secret

app = typer.Typer(help="Alta, consulta, rotación y revocación de gateways.")


@app.command("create")
def create(
    tenant: str = typer.Option(..., "--tenant", help="tenant_id (uuid)"),
    type_: str = typer.Option(..., "--type", help="whatsapp|telegram|internal_api|cron|web_panel|other"),
    name: str = typer.Option(..., "--name"),
    token: str = typer.Option(..., "--token", help="Credencial del gateway; se guarda en Vault, nunca en Postgres."),
) -> None:
    gateway = repository.create_gateway(UUID(tenant), type_, name, credential_ref=None)
    credential_ref = put_secret("secret", f"gateways/{gateway['id']}", "token", token)
    repository.rotate_gateway_credential(gateway["id"], credential_ref)
    typer.echo({**gateway, "credential_ref": credential_ref})


@app.command("list")
def list_(tenant: str | None = typer.Option(None, "--tenant")) -> None:
    for gw in repository.list_gateways(UUID(tenant) if tenant else None):
        typer.echo(gw)


@app.command("revoke")
def revoke(id_: str = typer.Option(..., "--id")) -> None:
    repository.revoke_gateway(UUID(id_))
    typer.echo(f"gateway {id_} revoked")


@app.command("rotate-credential")
def rotate_credential(
    id_: str = typer.Option(..., "--id"),
    token: str = typer.Option(..., "--token", help="Nuevo valor del token."),
) -> None:
    credential_ref = put_secret("secret", f"gateways/{id_}", "token", token)
    repository.rotate_gateway_credential(UUID(id_), credential_ref)
    typer.echo(f"gateway {id_} credential rotated -> {credential_ref}")
