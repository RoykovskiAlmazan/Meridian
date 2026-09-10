# Vault con almacenamiento persistente (ya no modo "dev")

Estado: implementado y verificado (incluyendo un reinicio real del contenedor).

## 1. Qué pasó

Vault corría en modo `-dev` desde el entregable 2: cómodo (sin inicializar/desellar), pero
**100% en memoria** -- cualquier recreación del contenedor borra todos los secretos. Esto
se manifestó de verdad en esta sesión: al agregar el healthcheck de Vault a
`docker-compose.yml` (mejora legítima, ver [0012](docs/design/0012-improvement-opportunities.md)),
Docker Compose recreó el contenedor de Vault en el siguiente `up`, y **se perdió la API
key real de Anthropic** que Rodrigo había cargado. Nada recuperable -- así es como se
supone que funciona el modo dev, el problema era seguir usándolo más allá de una prueba
rápida inicial.

## 2. Qué cambió

- `docker/vault/config.hcl`: backend de almacenamiento `"file"` (persistente, en un volumen
  Docker nombrado `vault_data`) en vez de `-dev`. Un solo listener TCP sin TLS (aceptable
  para desarrollo local en la misma máquina; ver sección 4 para producción real).
- `docker-compose.yml`: `vault` ya no usa `VAULT_DEV_ROOT_TOKEN_ID`/
  `VAULT_DEV_LISTEN_ADDRESS` -- monta el volumen + el config file, y el `command` es
  `["server"]` a secas (ver el bug de la sección 3).
- `meridianctl vault init` (nuevo): inicializa Vault una sola vez (Shamir 1-de-1, apropiado
  solo para desarrollo local de un operador), guarda la unseal key + root token en
  `.vault-init.json` (gitignored) y habilita el mount `secret/` (KV v2) que el modo dev
  traía solo.
- `meridianctl vault unseal`: desella usando la clave guardada -- necesario cada vez que el
  proceso de Vault se reinicia (comportamiento normal de Vault, no un bug).
- `meridianctl vault status`: `initialized`/`sealed` de un vistazo.
- `meridianctl doctor` ahora distingue "no inicializado" de "sellado" de "token inválido" y
  dice exactamente qué comando correr en cada caso.
- `VAULT_TOKEN` ya no es un valor fijo (`dev-only-root-token`) -- es el root token real que
  imprime `vault init`, y hay que ponerlo en `.env` a mano una vez.

## 3. Bug encontrado en el camino: el entrypoint oficial duplicaba el `-config`

Al construir esto, `vault server -config=/vault/config/vault.hcl` fallaba con
`address already in use` **incluso en un contenedor aislado sin ningún puerto de host
publicado, probando puertos nunca antes usados**. La causa: el `docker-entrypoint.sh` de
la imagen oficial de HashiCorp, cuando el primer argumento es `server`, agrega su propio
`-config="$VAULT_CONFIG_DIR"` (el directorio completo) **antes** de cualquier argumento
propio. Al pasar también nuestro `-config=/vault/config/vault.hcl`, Vault cargaba el mismo
archivo dos veces -- dos listeners idénticos, el segundo choca con el primero dentro del
mismo proceso. Se corrigió quitando nuestro `-config` explícito: basta con montar el
archivo en `/vault/config/vault.hcl` (el directorio que el entrypoint ya escanea solo) y
dejar `command: ["server"]`.

## 4. Consecuencia inmediata: hay que volver a cargar secretos

Todo lo que estaba en el Vault viejo (modo dev) se perdió, incluida la API key de
Anthropic de Rodrigo. **Esto no es recuperable por mí** -- Rodrigo necesita correr de
nuevo:

```bash
meridianctl secrets put --path llm/anthropic --field api_key
meridianctl llm set --subagent <paper_summarizer_id> --provider anthropic --model claude-sonnet-5 --credential-ref vault:secret/llm/anthropic#api_key
```

Los `credential_ref` de gateways sí se regeneraron automáticamente (con un token de prueba,
ya que hoy nada en el código verifica ese secreto en el camino de ejecución real).

## 5. Verificación hecha

- `meridianctl vault init` → inicializado, desellado, mount `secret/` habilitado.
- Flujo completo de fan-out/fan-in (gateway → main → 2 subagentes) funcionando con el
  Vault nuevo.
- **Reinicio real de `docker-vault-1`**: volvió `sealed=True` (los datos persistieron, a
  diferencia del modo dev donde no habría ni token que perder) → `meridianctl vault
  unseal` → un secreto guardado antes del reinicio se resolvió correctamente después.

## 6. Producción (fuera de alcance de este cambio, documentado para más adelante)

Esto sigue siendo apropiado solo para desarrollo local de un operador:

- Shamir 1-de-1 (una sola persona puede desellar) -- producción real quiere varios shares
  distribuidos entre personas distintas, o mejor, **auto-unseal vía KMS** (AWS KMS/GCP
  KMS/Azure Key Vault -- ver [0017-cloud-compatibility.md](docs/design/0017-cloud-compatibility.md)
  para cómo encaja esto con la compatibilidad de nube).
- Sin TLS entre servicios (`tls_disable = "true"`) -- aceptable solo porque todo corre en
  la misma máquina/red Docker local.
- `.vault-init.json` en el filesystem local, sin cifrar -- para producción, esas claves no
  deberían tocar disco en texto plano en ningún punto.
