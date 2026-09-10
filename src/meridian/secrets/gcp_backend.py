"""Resuelve un SecretRef de Google Secret Manager: `gcp-sm:<project_id>/<secret_id>#<version>`.

`<version>` es opcional -- vacío o "latest" pide la versión más reciente. A diferencia de
Vault (secretos con múltiples campos por entrada), Secret Manager guarda un string por
versión, así que no hay concepto de "campo" aquí: el `#<version>` selecciona QUÉ versión
del secreto, no una clave dentro de él.

Solo lectura: se asume que el secreto ya existe en Secret Manager (dado de alta por quien
administra ese proyecto de GCP). Requiere credenciales resueltas por la cadena normal de
Application Default Credentials (`gcloud auth application-default login`, una service
account, o el entorno de ejecución en GCP) -- Meridian no las gestiona, solo las usa.
"""
from __future__ import annotations


def resolve(project_id: str, secret_id: str, version: str = "latest") -> str:
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version or 'latest'}"
    response = client.access_secret_version(name=name)
    return response.payload.data.decode("utf-8")
