# Entregable 6 (parte 2) — Capa multi-proveedor LLM

Estado: implementado, pendiente de prueba real con tus API keys (paso manual tuyo, ver
sección 3 -- yo no puedo introducir tus credenciales).

## 1. Diseño

- `meridian/llm/base.py` — interfaz `LLMProvider.complete(system, prompt, max_tokens) ->
  LLMResponse`. Deliberadamente mínima (una sola vuelta, sin tool-calling/streaming) porque
  el único consumidor real hoy (`paper_summarizer`) no necesita más — se amplía cuando un
  subagente real lo requiera.
- `meridian/llm/anthropic_provider.py` / `openai_provider.py` — un adapter por proveedor,
  cada uno traduce la interfaz común al SDK propio.
- `meridian/llm/registry.py` — `get_provider_for_subagent(subagent_id)` es el único punto
  de entrada que main/subagentes deben usar; nunca instancian un SDK de proveedor
  directamente. Devuelve `None` si el subagente no tiene proveedor configurado (el caller
  decide el fallback).
- Tabla `subagent_llm_config` (Postgres): `provider` + `model` + `credential_ref` por
  subagente — coherente con la decisión #8 del brief ("multi-proveedor, configurable por
  agente", no un default fijo de plataforma). `credential_ref` es siempre un `SecretRef` a
  Vault, nunca la API key en claro (mismo patrón que `gateways.credential_ref`).

## 2. CLI

```bash
# 1. Guardar la API key en Vault (prompt oculto -- nunca en argumentos ni en el chat)
meridianctl secrets put --mount secret --path llm/anthropic --field api_key
# -> credential_ref = vault:secret/llm/anthropic#api_key

# 2. Configurar qué subagente usa qué proveedor/modelo
meridianctl llm set --subagent <paper_summarizer_id> --provider anthropic \
  --model claude-sonnet-5 --credential-ref vault:secret/llm/anthropic#api_key

# 3. Probar la conexión real antes de confiar en ella en el flujo normal
meridianctl llm test --subagent <paper_summarizer_id> --prompt "Responde solo 'ok'."

# 4. Ver qué tiene configurado un subagente
meridianctl llm get --subagent <paper_summarizer_id>
```

Cambiar de proveedor es solo repetir el paso 1-2 con `--provider openai --model <modelo>
--credential-ref vault:secret/llm/openai#api_key` -- ningún cambio de código.

## 3. Por qué esto requiere un paso tuyo (no lo puedo hacer yo)

Entrar API keys reales es una acción prohibida para mí (sección de reglas de seguridad de
la sesión) incluso si tú me la "autorizas" en el chat -- así que el paso 1 de la sección 2
lo tienes que correr tú mismo, en tu propia terminal, con tu API key real de Anthropic y/o
OpenAI. El `credential_ref` resultante es determinístico
(`vault:secret/llm/<proveedor>#api_key` si sigues la ruta sugerida arriba), así que no
necesitas pegármelo de vuelta -- yo ya sé qué referencia usar en el paso 2 si seguimos esa
convención.

## 4. `paper_summarizer` ya está conectado

`src/meridian/subagents/paper_summarizer/main.py` ahora intenta
`get_provider_for_subagent(subagent_id)`: si hay un proveedor configurado, genera el
resumen con el LLM real (prompt de sistema pidiendo un resumen de 3 oraciones en español);
si no, sigue cayendo al resumen extractivo de antes. **Meridian nunca deja de responder
por no tener un LLM configurado**, solo degrada la calidad del resumen -- coherente con
"seguro/funcional por defecto".

## 5. Sandbox de red

Se amplió la allowlist de `paper_summarizer` (IP `172.28.1.13`) en
`docker/sandbox/squid.conf` para incluir `.anthropic.com` y `.openai.com`, además de
`.arxiv.org` que ya tenía.

## 6. Pendiente (una vez guardes tu API key)

1. Correr los comandos de la sección 2 con tu key real.
2. Reconstruir `paper_summarizer` (`docker compose ... up -d --build paper_summarizer`) y
   volver a disparar `research.find_papers` para confirmar que el resumen ahora viene
   marcado como `"summary_method": "llm:anthropic/claude-sonnet-5"` (o el proveedor/modelo
   que elijas) en vez de `"extractive"`.
