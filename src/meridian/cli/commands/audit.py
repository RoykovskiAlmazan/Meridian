from uuid import UUID

import typer

from meridian.cli.console import ok, print_records
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
    print_records(entries, title="Audit log")


@app.command("prune")
def prune(
    older_than_days: int = typer.Option(90, "--older-than-days", help="Borra audit_log más viejo que N días (default 90 -- ajustable según tus propios requisitos de retención/cumplimiento)."),
) -> None:
    deleted = repository.prune_audit_log(older_than_days)
    ok(f"{deleted} entradas de audit_log borradas (más viejas que {older_than_days} días)")


@app.command("export")
def export(
    out: str = typer.Option(..., "--out", help="Ruta del archivo de salida. La extensión (.json o .csv) decide el formato."),
    tenant: str | None = typer.Option(None, "--tenant"),
    correlation_id: str | None = typer.Option(None, "--correlation-id"),
    limit: int = typer.Option(10_000, "--limit", help="Tope de filas a exportar."),
) -> None:
    """Exporta el audit_log a un archivo -- para un reporte de cumplimiento, una auditoría
    externa, o análisis fuera de la terminal (ej. abrir en Excel/Sheets)."""
    import csv
    import json as json_module

    entries = repository.tail_audit(
        UUID(tenant) if tenant else None,
        UUID(correlation_id) if correlation_id else None,
        limit,
    )

    if out.lower().endswith(".csv"):
        with open(out, "w", newline="", encoding="utf-8") as f:
            if entries:
                writer = csv.DictWriter(f, fieldnames=list(entries[0].keys()))
                writer.writeheader()
                for row in entries:
                    writer.writerow({k: (json_module.dumps(v) if isinstance(v, dict) else v) for k, v in row.items()})
    else:
        with open(out, "w", encoding="utf-8") as f:
            json_module.dump(entries, f, indent=2, default=str, ensure_ascii=False)

    ok(f"{len(entries)} entradas exportadas a {out}")
