from uuid import UUID

import typer

from meridian.identity import repository

app = typer.Typer(help="Inspección del audit_log: quién pidió qué y por qué se delegó.")


@app.command("tail")
def tail(
    tenant: str | None = typer.Option(None, "--tenant"),
    correlation_id: str | None = typer.Option(None, "--correlation-id"),
    limit: int = typer.Option(50, "--limit"),
) -> None:
    entries = repository.tail_audit(
        UUID(tenant) if tenant else None,
        UUID(correlation_id) if correlation_id else None,
        limit,
    )
    for entry in entries:
        typer.echo(entry)
