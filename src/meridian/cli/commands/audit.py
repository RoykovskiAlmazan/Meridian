from uuid import UUID

import typer

from meridian.cli.console import ok, print_records
from meridian.identity import repository

app = typer.Typer(help="Historial de quién pidió qué y qué pasó con cada tarea (recibida, reenviada, completada). Muestra solo el estado, no el resultado completo -- para eso usa `meridianctl results`.")


@app.command(
    "tail",
    help="Muestra las últimas entradas del audit_log (quién recibió/reenvió/completó qué, con correlation_id) -- no el output completo de un TaskResult, para eso usa `meridianctl results tail`.",
    epilog="Ejemplos:\n\n  meridianctl audit tail --tenant 697580ae-... --limit 20\n  meridianctl audit tail --correlation-id c46475b4-...",
)
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


@app.command(
    "prune",
    epilog="Ejemplo:\n\n  meridianctl audit prune --older-than-days 30",
)
def prune(
    older_than_days: int = typer.Option(90, "--older-than-days", help="Borra audit_log más viejo que N días (default 90 -- ajustable según tus propios requisitos de retención/cumplimiento)."),
) -> None:
    deleted = repository.prune_audit_log(older_than_days)
    ok(f"{deleted} entradas de audit_log borradas (más viejas que {older_than_days} días)")


@app.command(
    "export",
    epilog="Ejemplos:\n\n  meridianctl audit export --out reporte.csv --tenant 697580ae-...\n  meridianctl audit export --out reporte.json --correlation-id c46475b4-...",
)
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
