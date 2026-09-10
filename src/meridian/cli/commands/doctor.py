"""`meridianctl doctor`: chequeo de salud de una instalación de Meridian, con
autoreparación opcional (`--fix`) para lo que es seguro arreglar solo.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import typer

from meridian.cli.console import console, fail, info, ok, warn
from meridian.config import settings

_REPO_ROOT = Path(__file__).resolve().parents[4]
_ENV_FILE = _REPO_ROOT / ".env"
_ENV_EXAMPLE = _REPO_ROOT / ".env.example"

_EXPECTED_TABLES = {
    "tenants", "gateways", "subagents", "gateway_subagent_allowlist",
    "subagent_policy", "cron_jobs", "subagent_llm_config", "audit_log",
}


def _check_env_file(fix: bool) -> bool:
    if _ENV_FILE.exists():
        ok(f".env encontrado ({_ENV_FILE})")
        return True
    if fix and _ENV_EXAMPLE.exists():
        shutil.copy(_ENV_EXAMPLE, _ENV_FILE)
        ok(".env no existía -- copiado desde .env.example (revisa/ajusta los valores)")
        return True
    fail(".env no encontrado -- copia .env.example a .env y ajusta los valores (o corre `doctor --fix`)")
    return False


def _check_docker() -> bool:
    if shutil.which("docker") is None:
        fail("Docker no está instalado o no está en el PATH -- instala Docker Desktop")
        return False
    result = subprocess.run(["docker", "info"], capture_output=True, text=True)
    if result.returncode != 0:
        fail("Docker está instalado pero el daemon no responde -- abre Docker Desktop")
        return False
    ok("Docker instalado y el daemon responde")
    return True


def _check_postgres(fix: bool) -> bool:
    try:
        import psycopg
        with psycopg.connect(settings.postgres_dsn, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
                )
                existing = {row[0] for row in cur.fetchall()}
    except Exception as exc:  # noqa: BLE001
        fail(f"Postgres no alcanzable: {exc}")
        return False

    ok("Postgres alcanzable")
    missing = _EXPECTED_TABLES - existing
    if not missing:
        ok("Schema completo (todas las tablas esperadas existen)")
        return True

    if fix:
        from meridian.schema_apply import apply_schema
        apply_schema()
        ok(f"Schema desactualizado -- se aplicó docker/init/postgres_schema.sql (faltaban: {', '.join(sorted(missing))})")
        return True

    fail(f"Faltan tablas en Postgres: {', '.join(sorted(missing))} -- corre `doctor --fix` para aplicarlas")
    return False


def _check_redis() -> bool:
    try:
        from meridian.bus.redis_bus import get_client
        get_client().ping()
    except Exception as exc:  # noqa: BLE001
        fail(f"Redis no alcanzable: {exc}")
        return False
    ok("Redis alcanzable")
    return True


def _check_vault() -> bool:
    try:
        import hvac
        client = hvac.Client(url=settings.vault_addr, token=settings.vault_token)
        if not client.is_authenticated():
            fail("Vault respondió pero el token no autenticó -- revisa VAULT_TOKEN en .env")
            return False
    except Exception as exc:  # noqa: BLE001
        fail(f"Vault no alcanzable: {exc}")
        return False
    ok("Vault alcanzable y autenticado")

    try:
        mounts = client.sys.list_mounted_secrets_engines()
        mount_paths = mounts["data"].keys() if "data" in mounts else mounts.keys()
        if not any(p.rstrip("/") == "secret" for p in mount_paths):
            warn("Vault no tiene montado el secrets engine 'secret' (KV) -- `vault secrets enable -path=secret kv-v2`")
            return False
    except Exception as exc:  # noqa: BLE001
        warn(f"No se pudo verificar el mount de secretos en Vault: {exc}")
        return False
    ok("Vault tiene el secrets engine 'secret' (KV) montado")
    return True


def _check_schemas_dir() -> bool:
    try:
        from meridian.messages import _SCHEMAS_DIR
        if not _SCHEMAS_DIR.exists():
            raise FileNotFoundError(_SCHEMAS_DIR)
    except Exception as exc:  # noqa: BLE001
        fail(f"No se pudo resolver el directorio schemas/: {exc}")
        return False
    ok("schemas/ (contrato de mensajes) resuelto correctamente")
    return True


def doctor(
    fix: bool = typer.Option(False, "--fix", help="Intenta reparar automáticamente lo que es seguro arreglar (crear .env desde el ejemplo, aplicar tablas de Postgres faltantes)."),
) -> None:
    console.print("[bold]Meridian doctor[/bold] -- diagnóstico de la instalación\n")

    results = []
    results.append(_check_env_file(fix))
    results.append(_check_docker())

    if results[-1]:
        results.append(_check_postgres(fix))
        results.append(_check_redis())
        results.append(_check_vault())
    else:
        info("se omiten los chequeos de Postgres/Redis/Vault -- Docker no está listo")

    results.append(_check_schemas_dir())

    console.print()
    if all(results):
        console.print("[bold green]Todo en orden.[/bold green] Meridian está listo para usarse.")
    else:
        console.print("[bold yellow]Hay problemas pendientes.[/bold yellow] Revisa los [FAIL] de arriba" + (" (ya se intentaron arreglar los que se pudo con --fix)." if fix else ", o corre `meridianctl doctor --fix`."))
        raise typer.Exit(code=1)
