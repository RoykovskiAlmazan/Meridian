import typer

from meridian.bus import redis_bus

app = typer.Typer(help="Salud del bus interno (Redis Streams).")


@app.command("status")
def status(stream: str = typer.Option(..., "--stream", help="ej: meridian:intents:main")) -> None:
    typer.echo(redis_bus.stream_info(stream))
