import typer

from meridian.config import settings

app = typer.Typer(help="Valida que Postgres, Redis y Vault sean alcanzables antes de operar.")


@app.command("check")
def check() -> None:
    ok = True

    try:
        import psycopg
        with psycopg.connect(settings.postgres_dsn, connect_timeout=3):
            typer.echo("[ok] postgres alcanzable")
    except Exception as exc:  # noqa: BLE001
        ok = False
        typer.echo(f"[fail] postgres: {exc}")

    try:
        from meridian.bus.redis_bus import get_client
        get_client().ping()
        typer.echo("[ok] redis alcanzable")
    except Exception as exc:  # noqa: BLE001
        ok = False
        typer.echo(f"[fail] redis: {exc}")

    try:
        import hvac
        client = hvac.Client(url=settings.vault_addr, token=settings.vault_token)
        if client.is_authenticated():
            typer.echo("[ok] vault alcanzable y autenticado")
        else:
            ok = False
            typer.echo("[fail] vault respondió pero el token no autenticó")
    except Exception as exc:  # noqa: BLE001
        ok = False
        typer.echo(f"[fail] vault: {exc}")

    raise typer.Exit(code=0 if ok else 1)
