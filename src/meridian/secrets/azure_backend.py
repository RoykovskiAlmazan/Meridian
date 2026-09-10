"""Resuelve un SecretRef de Azure Key Vault: `azure-kv:<vault_name>/<secret_name>#<version>`.

`<version>` es opcional -- vacío pide la versión más reciente. Igual que Secret Manager de
GCP, Key Vault guarda un string por versión de secreto, no campos múltiples.

Solo lectura: se asume que el secreto ya existe en el Key Vault (dado de alta por quien
administra esa suscripción de Azure). Requiere credenciales resueltas por
`DefaultAzureCredential` (variables de entorno, Azure CLI logueado, managed identity, etc.)
-- Meridian no las gestiona, solo las usa.
"""
from __future__ import annotations


def resolve(vault_name: str, secret_name: str, version: str = "") -> str:
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    vault_url = f"https://{vault_name}.vault.azure.net"
    client = SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())
    secret = client.get_secret(secret_name, version=version or None)
    return secret.value
