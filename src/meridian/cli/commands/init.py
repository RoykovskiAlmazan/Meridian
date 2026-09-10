"""`meridianctl init`: wizard que encadena los primeros pasos de instalación (copiar
.env, levantar infra, inicializar Vault, doctor) para bajar la fricción de los primeros
minutos -- el README ya documenta estos mismos pasos uno por uno; esto los automatiza.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import typer

from meridian.cli.console import info, ok, print_banner, warn

_REPO_ROOT = Path(__file__).resolve().parents[4]
_ENV_FILE = _REPO_ROOT / ".env"
_ENV_EXAMPLE = _REPO_ROOT / ".env.example"


def init(
    subagents: bool = typer.Option(False, "--subagents", help="También levanta sample_subagent_a/b (requiere configurarlos después)."),
) -> None:
    print_banner()
    info("Wizard de instalación -- esto es lo mismo que el quickstart del README, automatizado.")

    if _ENV_FILE.exists():
        ok(".env ya existe, no se toca")
    else:
        shutil.copy(_ENV_EXAMPLE, _ENV_FILE)
        ok(".env creado desde .env.example")

    info("Levantando infraestructura (Postgres, Redis, Vault, main, mock_gateway)...")
    from meridian.cli.commands.dev import up as dev_up
    dev_up(subagents=subagents, research=False)

    import hvac

    from meridian.config import settings
    client = hvac.Client(url=settings.vault_addr)
    if not client.sys.is_initialized():
        info("Inicializando Vault (primera vez)...")
        from meridian.cli.commands.vault import init as vault_init
        vault_init()
        warn("IMPORTANTE: copia el VAULT_TOKEN de arriba a tu .env antes de seguir -- no puedo editarlo por ti sin que lo veas primero.")
    else:
        ok("Vault ya estaba inicializado")
        if client.sys.is_sealed():
            warn("Vault está sellado -- corre `meridianctl vault unseal` (necesita tu .vault-init.json).")

    typer.echo("")
    info("Corre `meridianctl doctor` para confirmar que todo quedó listo.")
    info("Luego: `meridianctl tenant create --name <tu-organizacion>` para tu primera identidad.")
