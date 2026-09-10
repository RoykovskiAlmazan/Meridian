# Caso de prueba de dominio real: buscador de papers

Estado: implementado y verificado end-to-end en esta máquina.

## 1. Por qué este caso de prueba

Hasta ahora Meridian solo se había probado con subagentes de eco (entregable 2) y un
gateway sin dependencias externas (entregable 5, cron). Este caso de prueba usa un dominio
real (investigación académica, deliberadamente distinto del contexto de inventario de
Rodrigo, para reforzar que Meridian no asume ningún dominio) y, sobre todo, prueba por
primera vez que el **sandbox de red permite tráfico real a un dominio externo declarado**
(entregable 3) en vez de solo demostrar que deniega todo.

## 2. Diseño

Un solo `TaskIntent` (`intent.type: research.find_papers`, `payload: {"query": "..."}`)
con fan-out a dos subagentes que consultan el mismo API público de arXiv de forma
independiente y en paralelo -- sin dependencia entre ellos, coherente con el modelo de
fan-out/fan-in actual del `main` (que no soporta pipelines secuenciales todavía):

- **`paper_search`** (`src/meridian/subagents/paper_search/main.py`): busca los N papers
  más relevantes para la query y devuelve título/url/fecha/autores de cada uno.
- **`paper_summarizer`** (`src/meridian/subagents/paper_summarizer/main.py`): busca el
  paper más relevante para la misma query y genera un resumen **extractivo** (primeras
  oraciones del abstract) -- deliberadamente NO usa un LLM todavía, porque la capa de
  abstracción multi-proveedor (Claude/Codex/Gemini) sigue siendo un punto abierto en
  `PROJECT_BRIEF.md` (sección 4, punto 3). Este subagente es el candidato natural para
  conectarla cuando esa decisión se tome.

Ambos comparten `src/meridian/subagents/arxiv_client.py` (cliente mínimo del API público
de arXiv, parseo de Atom con `xml.etree.ElementTree`).

## 3. Sandbox de red

Se agregaron IPs fijas nuevas en `meridian_internal` (`172.28.1.12` para `paper_search`,
`172.28.1.13` para `paper_summarizer`) y dos ACLs nuevas en `docker/sandbox/squid.conf`
permitiendo `dstdomain .arxiv.org` únicamente para esas dos IPs -- allowlist mínima
(solo el dominio que necesitan), nada de "todo internet por si acaso" (ver
docs/design/0004-sandbox-exec-model.md).

## 4. Bug encontrado y corregido: `.env` no se resolvía de forma confiable

Al levantar `paper_search`/`paper_summarizer` con
`docker compose -f docker/docker-compose.yml --profile research up`, `SUBAGENT_ID` llegaba
vacío al contenedor pese a estar definido en `.env` en la raíz del repo -- Docker Compose
no garantiza tomar el `.env` del cwd cuando el archivo compose se referencia con una ruta a
otro directorio (`docker/docker-compose.yml`); el "directorio de proyecto" que usa para
resolver `.env` no es necesariamente el cwd. Se corrigió pasando `--env-file` explícito
apuntando a la raíz del repo, tanto en `meridianctl dev up/down`
(`src/meridian/cli/commands/dev.py`) como en cualquier invocación manual de
`docker compose`. `meridianctl dev up` ahora acepta también `--research` además de
`--subagents`.

## 5. Verificación hecha

Dos disparos reales de `research.find_papers` vía el mock gateway, con queries distintas
("multi-agent orchestration" y "retrieval augmented generation"), ambos con:

- `paper_search` devolviendo 5 resultados reales de arXiv con metadata completa.
- `paper_summarizer` devolviendo el paper más relevante + un resumen extractivo de su
  abstract.
- Fan-in agregado correctamente por el `main` sin ningún cambio de código en
  `main_agent/`.

## 6. Cómo probarlo tú mismo

```bash
# (asumiendo que ya tienes un tenant y un gateway dados de alta)
meridianctl subagent create --tenant <tenant_id> --name paper-search --domain research
meridianctl subagent create --tenant <tenant_id> --name paper-summarizer --domain research

meridianctl allow set --gateway <gateway_id> --subagent <paper_search_id> --intents research.find_papers
meridianctl allow set --gateway <gateway_id> --subagent <paper_summarizer_id> --intents research.find_papers

echo "PAPER_SEARCH_SUBAGENT_ID=<paper_search_id>" >> .env
echo "PAPER_SUMMARIZER_SUBAGENT_ID=<paper_summarizer_id>" >> .env

meridianctl dev up --research

curl -X POST http://localhost:8080/intent \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"<tenant_id>","gateway_id":"<gateway_id>","intent_type":"research.find_papers","subagent_ids":["<paper_search_id>","<paper_summarizer_id>"],"payload":{"query":"lo que quieras buscar"}}'

curl "http://localhost:8080/result/<correlation_id>?gateway_id=<gateway_id>"
```

## 7. Fuera de alcance

- Resumen real vía LLM en `paper_summarizer` -- pendiente de la capa multi-proveedor.
- `policy` de comportamiento aún no aplicada a estos subagentes (podrían configurarse con
  `meridianctl policy set` siguiendo el ejemplo de investigación de
  docs/design/0005-behavior-policy.md, pero el enforcement sigue sin estar conectado).
