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


@app.command("prune")
def prune(
    older_than_days: int = typer.Option(90, "--older-than-days", help="Borra audit_log más viejo que N días (default 90 -- ajustable según tus propios requisitos de retención/cumplimiento)."),
) -> None:
    deleted = repository.prune_audit_log(older_than_days)
    typer.echo(f"{deleted} entradas de audit_log borradas (más viejas que {older_than_days} días)")
