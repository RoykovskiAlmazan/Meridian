import typer

from meridian.cli.console import fail
from meridian.cli.console import ok as ok_msg
from meridian.config import settings

app = typer.Typer(help="Valida que Postgres, Redis y Vault sean alcanzables. Para un diagnóstico más completo (con autoreparación), usa `meridianctl doctor`.")


@app.command("check")
def check() -> None:
    healthy = True

    try:
        import psycopg
        with psycopg.connect(settings.postgres_dsn, connect_timeout=3):
            ok_msg("postgres alcanzable")
    except Exception as exc:  # noqa: BLE001
        healthy = False
        fail(f"postgres: {exc}")

    try:
        from meridian.bus.redis_bus import get_client
        get_client().ping()
        ok_msg("redis alcanzable")
    except Exception as exc:  # noqa: BLE001
        healthy = False
        fail(f"redis: {exc}")

    try:
        import hvac
        client = hvac.Client(url=settings.vault_addr, token=settings.vault_token)
        if client.is_authenticated():
            ok_msg("vault alcanzable y autenticado")
        else:
            healthy = False
            fail("vault respondió pero el token no autenticó")
    except Exception as exc:  # noqa: BLE001
        healthy = False
        fail(f"vault: {exc}")

    raise typer.Exit(code=0 if healthy else 1)
