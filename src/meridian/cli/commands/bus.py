import typer

from meridian.bus import redis_bus
from meridian.cli.console import print_record

app = typer.Typer(help="Diagnóstico avanzado del sistema de mensajería interno (Redis) -- para ver si un subagente se quedó atrás procesando tareas.")


@app.command(
    "status",
    help="Info de un stream de Redis (longitud, consumer groups, pendientes, lag) -- útil para ver si un subagente se quedó atrás procesando.",
    epilog="Ejemplos:\n\n  meridianctl bus status --stream meridian:intents:main\n  meridianctl bus status --stream meridian:intents:88fc9c58-...",
)
def status(stream: str = typer.Option(..., "--stream", help="ej: meridian:intents:main")) -> None:
    print_record(redis_bus.stream_info(stream))
