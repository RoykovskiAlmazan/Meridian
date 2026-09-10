import typer

from meridian.bus import redis_bus
from meridian.cli.console import print_record

app = typer.Typer(help="Salud del bus interno (Redis Streams).")


@app.command("status")
def status(stream: str = typer.Option(..., "--stream", help="ej: meridian:intents:main")) -> None:
    print_record(redis_bus.stream_info(stream))
