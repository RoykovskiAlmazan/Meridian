"""Resuelve un SecretRef de AWS Secrets Manager: `aws-sm:<secret_id>#<campo>`.

`<secret_id>` es el nombre o ARN del secreto en Secrets Manager. Si el secreto está
guardado como JSON (lo más común, ej. `{"api_key": "..."}`), `<campo>` es la clave dentro
de ese JSON. Si el secreto es un string plano (SecretString sin estructura), usa
`<campo> = "value"` como convención para pedir el string completo.

Solo lectura: a diferencia de Vault, este módulo no expone un `put_secret` -- se asume que
el secreto ya existe en Secrets Manager (dado de alta por quien administra esa cuenta de
AWS, fuera de Meridian). Requiere credenciales de AWS resueltas por la cadena normal de
boto3 (variables de entorno, perfil de `~/.aws/credentials`, IAM role, etc.) -- Meridian no
gestiona esas credenciales, solo las usa.
"""
from __future__ import annotations

import json


class SecretRefError(ValueError):
    pass


def resolve(secret_id: str, field: str, *, region_name: str | None = None, endpoint_url: str | None = None) -> str:
    import boto3

    client = boto3.client("secretsmanager", region_name=region_name, endpoint_url=endpoint_url)
    response = client.get_secret_value(SecretId=secret_id)
    raw = response.get("SecretString")
    if raw is None:
        raise SecretRefError(f"El secreto {secret_id!r} no tiene SecretString (¿es binario?)")

    if field == "value":
        return raw

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SecretRefError(
            f"El secreto {secret_id!r} no es JSON -- usa el campo 'value' para pedir el string completo."
        ) from exc

    if field not in data:
        raise SecretRefError(f"Campo {field!r} no encontrado en el secreto {secret_id!r}")
    return data[field]
