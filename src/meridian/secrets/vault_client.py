"""Cliente mínimo de Vault: resuelve SecretRef -> secreto en runtime.

Un SecretRef tiene la forma "vault:<mount>/<path>#<field>", nunca se guarda ni se
loguea el secreto en claro (ver requisitos no negociables, sección 5 del brief).
"""
from __future__ import annotations

import hvac

from meridian.config import settings

_SCHEME_PREFIX = "vault:"


class SecretRefError(ValueError):
    pass


def _client() -> hvac.Client:
    return hvac.Client(url=settings.vault_addr, token=settings.vault_token)


def make_secret_ref(mount: str, path: str, field: str) -> str:
    return f"{_SCHEME_PREFIX}{mount}/{path}#{field}"


def _parse_secret_ref(secret_ref: str) -> tuple[str, str, str]:
    if not secret_ref.startswith(_SCHEME_PREFIX):
        raise SecretRefError(f"SecretRef inválido, debe empezar con '{_SCHEME_PREFIX}': {secret_ref!r}")
    body = secret_ref[len(_SCHEME_PREFIX):]
    path_part, _, field = body.partition("#")
    mount, _, path = path_part.partition("/")
    if not (mount and path and field):
        raise SecretRefError(f"SecretRef mal formado, esperado 'vault:<mount>/<path>#<field>': {secret_ref!r}")
    return mount, path, field


def put_secret(mount: str, path: str, field: str, value: str) -> str:
    """Escribe un secreto en Vault (KV v2) y devuelve el SecretRef que lo referencia."""
    client = _client()
    client.secrets.kv.v2.create_or_update_secret(
        mount_point=mount, path=path, secret={field: value}
    )
    return make_secret_ref(mount, path, field)


def resolve_secret_ref(secret_ref: str) -> str:
    """Resuelve un SecretRef al valor real. Solo se llama en runtime, nunca al construir
    o loguear un mensaje."""
    mount, path, field = _parse_secret_ref(secret_ref)
    client = _client()
    result = client.secrets.kv.v2.read_secret_version(mount_point=mount, path=path)
    data = result["data"]["data"]
    if field not in data:
        raise SecretRefError(f"Campo '{field}' no encontrado en {secret_ref!r}")
    return data[field]
