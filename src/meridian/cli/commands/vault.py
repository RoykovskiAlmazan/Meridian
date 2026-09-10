"""Inicialización/desello de Vault -- necesario una sola vez por instalación, ahora que
Vault usa almacenamiento persistente (backend "file") en vez del modo "dev" efímero. Ver
docs/design/0016-vault-persistence.md.
"""
from __future__ import annotations

import json
from pathlib import Path

import hvac
import typer

from meridian.cli.console import fail, ok, warn
from meridian.config import settings

app = typer.Typer(help="Enciende y desbloquea Vault, el lugar donde Meridian guarda todas las contraseñas y API keys. `init` es una sola vez; `unseal` hace falta cada vez que se reinicia.")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_INIT_FILE = _REPO_ROOT / ".vault-init.json"


def _client() -> hvac.Client:
    return hvac.Client(url=settings.vault_addr)


@app.command(
    "init",
    epilog="Ejemplo:\n\n  meridianctl vault init\n  # copia el VAULT_TOKEN=... que imprime a tu .env",
)
def init() -> None:
    """Inicializa Vault (una sola vez, la primera vez que se levanta un volumen nuevo de
    Vault). Guarda la unseal key + root token en .vault-init.json (gitignored, NUNCA se
    commitea) y desella de inmediato. Imprime el root token para que lo pongas en
    VAULT_TOKEN en tu .env -- el token fijo "dev-only-root-token" del modo dev ya no
    existe."""
    client = _client()
    if client.sys.is_initialized():
        fail("Vault ya está inicializado -- si perdiste .vault-init.json no hay forma de recuperarlo (Shamir), tendrías que reiniciar el volumen de Vault y volver a configurar todos los secretos.")
        raise typer.Exit(code=1)

    result = client.sys.initialize(secret_shares=1, secret_threshold=1)
    root_token = result["root_token"]
    unseal_key = result["keys"][0]

    _INIT_FILE.write_text(json.dumps({"root_token": root_token, "unseal_keys": [unseal_key]}, indent=2))

    client.sys.submit_unseal_key(unseal_key)

    # Un Vault recién inicializado con almacenamiento "file" no trae el mount "secret/"
    # (KV v2) habilitado por defecto -- a diferencia del modo dev, que sí lo hace solo.
    authed_client = hvac.Client(url=settings.vault_addr, token=root_token)
    authed_client.sys.enable_secrets_engine(backend_type="kv", path="secret", options={"version": "2"})

    ok(f"Vault inicializado, desellado, y con el mount 'secret/' (KV v2) listo. Claves guardadas en {_INIT_FILE}")
    warn(f"Pon esto en tu .env: VAULT_TOKEN={root_token}")
    warn(f"{_INIT_FILE.name} nunca se sube a git (ver .gitignore) -- guárdalo en un lugar seguro, es la única forma de desellar Vault de nuevo si el proceso se reinicia.")


@app.command(
    "unseal",
    epilog="Ejemplo:\n\n  meridianctl vault unseal",
)
def unseal() -> None:
    """Desella Vault usando la clave guardada en .vault-init.json -- necesario cada vez
    que el proceso de Vault se reinicia (el sellado es por diseño de Vault, no un bug)."""
    if not _INIT_FILE.exists():
        fail(f"No existe {_INIT_FILE} -- corre `meridianctl vault init` si es la primera vez, o restaura ese archivo si lo tenías guardado en otro lado.")
        raise typer.Exit(code=1)

    data = json.loads(_INIT_FILE.read_text())
    client = _client()
    if not client.sys.is_sealed():
        ok("Vault ya está desellado, nada que hacer.")
        return

    for key in data["unseal_keys"]:
        status = client.sys.submit_unseal_key(key)
        if not status["sealed"]:
            break
    ok("Vault desellado.")


@app.command(
    "status",
    help="Consulta rápida de initialized/sealed, sin autenticarse -- útil como chequeo previo a `doctor`.",
    epilog="Ejemplo:\n\n  meridianctl vault status",
)
def status() -> None:
    client = _client()
    initialized = client.sys.is_initialized()
    sealed = client.sys.is_sealed() if initialized else None
    typer.echo(f"initialized={initialized} sealed={sealed}")
    if not initialized:
        warn("Corre `meridianctl vault init` (una sola vez).")
    elif sealed:
        warn("Corre `meridianctl vault unseal`.")
    else:
        ok("Vault listo para usarse.")
