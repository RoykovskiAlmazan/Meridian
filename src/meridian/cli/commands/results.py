"""Inspección de resultados: qué contestó de verdad un subagente, no solo el resumen de
estado que guarda `audit_log`. El resultado completo (`output`/`error` de cada
TaskResult) solo vive brevemente en el stream de Redis del gateway de origen -- por
diseño `audit_log` es un rastro de auditoría (quién hizo qué, cuándo), no almacenamiento
de datos (ver docs/design/0008-observability.md). Un gateway como `mock_gateway` expone su
propio endpoint HTTP para esto; los demás (ej. `cron_gateway`, que dispara y se olvida) no
tienen ninguno -- este comando cubre ese hueco desde la consola para cualquier gateway.
"""
from __future__ import annotations

import json as json_module

import typer
from rich.json import JSON
from rich.panel import Panel

from meridian.bus import redis_bus
from meridian.cli.console import console, info

app = typer.Typer(help="Ve lo que un subagente contestó de verdad (no solo si salió bien o mal) para las tareas que pasaron por un gateway.")


@app.command(
    "tail",
    help="Muestra el output/error real de los últimos intents completados para un gateway -- lee directo el stream de Redis, no `audit_log` (que solo guarda status, no el contenido).",
    epilog=(
        "Ejemplos:\n\n"
        "  meridianctl results tail --gateway b2f22873-...\n"
        "  meridianctl results tail --gateway b2f22873-... --limit 5\n"
        "  meridianctl results tail --gateway b2f22873-... --correlation-id c46475b4-..."
    ),
)
def tail(
    gateway: str = typer.Option(..., "--gateway", help="gateway_id (uuid) cuyo stream de resultados quieres ver"),
    limit: int = typer.Option(10, "--limit", help="Cuántos fan-in completos mostrar, más reciente primero"),
    correlation_id: str | None = typer.Option(None, "--correlation-id", help="Filtra a un solo correlation_id"),
) -> None:
    aggregates = redis_bus.tail_gateway_results(gateway, limit=limit if not correlation_id else 1000)
    if correlation_id:
        aggregates = [a for a in aggregates if a["correlation_id"] == correlation_id][:limit]

    if not aggregates:
        info("(sin resultados todavía para este gateway -- ¿ya corrió algún intent? revisa `meridianctl audit tail`)")
        return

    for aggregate in aggregates:
        for result in aggregate["results"]:
            status = result["status"]
            style = "bold green" if status == "success" else "bold red"
            header = (
                f"[{style}]{status}[/{style}]  subagent={result['subagent_id']}  "
                f"correlation_id={aggregate['correlation_id']}"
            )
            body = JSON(json_module.dumps(result.get("output") or result.get("error") or {}))
            console.print(Panel(body, title=header, subtitle=f"{result['started_at']} -> {result['completed_at']}"))
