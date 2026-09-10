"""Punto de entrada único para resolver un SecretRef, sin importar en qué backend vive --
ver docs/design/0019-cloud-secret-backends.md. Todo el código de Meridian que necesita el
valor real de un secreto (gateways, proveedores LLM) debe pasar por aquí, no por un backend
específico, para poder mezclar Vault/AWS/GCP/Azure sin acoplarse a un SDK concreto (mismo
patrón que `meridian.llm.registry` para proveedores de LLM).

Formatos de SecretRef soportados:
  vault:<mount>/<path>#<field>              -- HashiCorp Vault (el único que Meridian
                                                también puede ESCRIBIR, vía `secrets put`)
  aws-sm:<secret_id>#<field|value>          -- AWS Secrets Manager (solo lectura)
  gcp-sm:<project_id>/<secret_id>#<version> -- Google Secret Manager (solo lectura)
  azure-kv:<vault_name>/<secret_name>#<version> -- Azure Key Vault (solo lectura)
"""
from __future__ import annotations


class SecretRefError(ValueError):
    pass


def resolve_secret_ref(secret_ref: str) -> str:
    if secret_ref.startswith("vault:"):
        from meridian.secrets.vault_client import resolve_secret_ref as _vault_resolve
        return _vault_resolve(secret_ref)

    if secret_ref.startswith("aws-sm:"):
        from meridian.secrets.aws_backend import resolve as _aws_resolve
        body = secret_ref[len("aws-sm:"):]
        secret_id, _, field = body.partition("#")
        if not (secret_id and field):
            raise SecretRefError(f"SecretRef mal formado, esperado 'aws-sm:<secret_id>#<field>': {secret_ref!r}")
        return _aws_resolve(secret_id, field)

    if secret_ref.startswith("gcp-sm:"):
        from meridian.secrets.gcp_backend import resolve as _gcp_resolve
        body = secret_ref[len("gcp-sm:"):]
        path, _, version = body.partition("#")
        project_id, _, secret_id = path.partition("/")
        if not (project_id and secret_id):
            raise SecretRefError(f"SecretRef mal formado, esperado 'gcp-sm:<project_id>/<secret_id>#<version>': {secret_ref!r}")
        return _gcp_resolve(project_id, secret_id, version)

    if secret_ref.startswith("azure-kv:"):
        from meridian.secrets.azure_backend import resolve as _azure_resolve
        body = secret_ref[len("azure-kv:"):]
        path, _, version = body.partition("#")
        vault_name, _, secret_name = path.partition("/")
        if not (vault_name and secret_name):
            raise SecretRefError(f"SecretRef mal formado, esperado 'azure-kv:<vault_name>/<secret_name>#<version>': {secret_ref!r}")
        return _azure_resolve(vault_name, secret_name, version)

    raise SecretRefError(f"Esquema de SecretRef no reconocido: {secret_ref!r} (usa vault:/aws-sm:/gcp-sm:/azure-kv:)")
