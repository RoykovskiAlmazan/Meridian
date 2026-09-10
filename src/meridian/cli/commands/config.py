import typer

from meridian.cli.console import fail
from meridian.cli.console import ok as ok_msg
from meridian.config import settings

app = typer.Typer(help="Prueba rápida de conexión a la base de datos, Redis y Vault. Para un diagnóstico completo con reparación automática, usa `meridianctl doctor` en su lugar.")


@app.command(
    "check",
    epilog="Ejemplo:\n\n  meridianctl config check",
)
def check() -> None:
    healthy = True

    try:
        from meridian.identity.db import get_engine
        with get_engine().connect():
            ok_msg(f"base de datos ({settings.db_backend}) alcanzable")
    except Exception as exc:  # noqa: BLE001
        healthy = False
        fail(f"base de datos: {exc}")

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
