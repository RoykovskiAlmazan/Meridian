# Compatibilidad de secretos con AWS/GCP/Azure

Estado: Vault (ya existía) y AWS Secrets Manager verificados (AWS vía mock realista, no
cuenta real). GCP y Azure implementados con el mismo patrón, sin probar (ver sección 3).

## 1. Diseño

Mismo patrón que la capa multi-proveedor LLM ([0009](docs/design/0009-llm-provider-layer.md)):
un `SecretRef` es una cadena con un prefijo que indica el backend, y
`meridian.secrets.resolver.resolve_secret_ref(ref)` es el único punto de entrada -- nadie
más debe importar un backend específico directo.

```
vault:<mount>/<path>#<field>               -- HashiCorp Vault (lectura Y escritura,
                                               `meridianctl secrets put`)
aws-sm:<secret_id>#<field|value>           -- AWS Secrets Manager (solo lectura)
gcp-sm:<project_id>/<secret_id>#<version>  -- Google Secret Manager (solo lectura)
azure-kv:<vault_name>/<secret_name>#<version> -- Azure Key Vault (solo lectura)
```

**Solo Vault soporta escritura** (`meridianctl secrets put`) -- para los tres backends de
nube se asume que el secreto ya existe, dado de alta por quien administra esa cuenta/
suscripción/proyecto, fuera de Meridian. Automatizar el alta en una cuenta de nube real
implicaría credenciales con permisos de escritura que nadie pidió dar a Meridian todavía;
si hace falta más adelante, es una extensión natural de `aws_backend.py`/etc., no un
cambio de diseño.

Cada backend (`meridian/secrets/aws_backend.py`, `gcp_backend.py`, `azure_backend.py`)
importa su SDK de forma perezosa (dentro de la función, no al nivel del módulo) -- así
`meridian.secrets.resolver` se puede importar sin tener instalados los tres SDKs de nube;
solo hace falta el de el/los backend(s) que realmente uses
(`pip install -e ".[aws]"` / `".[gcp]"` / `".[azure]"`).

## 2. `meridian.llm.registry` ahora usa el resolver genérico

Antes importaba `resolve_secret_ref` directo de `vault_client` -- se cambió a
`meridian.secrets.resolver`, así que un `subagent_llm_config.credential_ref` puede vivir
en cualquiera de los cuatro backends sin ningún cambio de código en la capa de LLM.

## 3. Qué se verificó y qué no

- **Vault**: ya estaba probado (entregables 6/16).
- **AWS Secrets Manager**: probado con `moto` (`tests/unit/test_secrets_aws_backend.py`) --
  mockea la API real de AWS en memoria, ejerciendo el código real de `boto3` (creación de
  secreto, lectura de un campo JSON, lectura de un string plano vía el campo `value`,
  manejo de campo inexistente) y el dispatch completo desde `resolve_secret_ref("aws-sm:...")`.
  Esto es una verificación real del comportamiento del backend, no solo de que el código
  compile -- pero no se probó contra una cuenta de AWS real.
- **GCP Secret Manager / Azure Key Vault**: implementados con el mismo patrón (misma forma
  de parsear el `SecretRef`, mismo manejo de errores), pero **sin ninguna verificación**,
  ni siquiera mockeada -- no hay un equivalente a `moto` igual de simple para estos dos en
  este entorno. Si Rodrigo necesita alguno de los dos en concreto, el siguiente paso es
  probarlo contra un proyecto/suscripción real (o una emulación oficial del proveedor,
  como el emulador de Secret Manager de GCP) antes de confiar en que funciona.

## 4. Nota importante: la API key de Anthropic real sigue sin restaurarse

Al migrar Vault a almacenamiento persistente ([0016](docs/design/0016-vault-persistence.md))
se perdió la API key de Anthropic que Rodrigo había cargado (Vault dev mode era efímero).
En ese momento quedó anotado que había que volver a cargarla, pero **no se completó ese
paso** -- `meridianctl llm test` contra `paper_summarizer` falla ahora mismo con
`InvalidPath` (Vault dice, correctamente, que `secret/llm/anthropic` no existe). Esto no es
un bug de este entregable ni del resolver nuevo -- el dispatch a Vault funciona
correctamente, simplemente no hay nada guardado en esa ruta. Rodrigo necesita correr de
nuevo:

```bash
meridianctl secrets put --path llm/anthropic --field api_key
```

(el `credential_ref` ya configurado en `subagent_llm_config` sigue apuntando a la ruta
correcta, no hace falta repetir `meridianctl llm set`).
