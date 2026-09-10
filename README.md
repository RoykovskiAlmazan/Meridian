# Meridian (codename: Project Foreman)

Plataforma propia de orquestación multiagente: múltiples gateways → agente `main` →
subagentes especializados, con multi-tenancy real, contenedores por subagente, y
administración completa vía CLI (`meridianctl`).

Ver [PROJECT_BRIEF.md](PROJECT_BRIEF.md) para objetivo, contexto, decisiones tomadas y
roadmap. Ver [docs/design/](docs/design/) para los documentos de diseño de cada entregable.

Estado actual: **entregables 1, 2 y 3 completos y verificados end-to-end** en esta máquina
(schema de mensajes + identidad, mock gateway + main + 2 subagentes de prueba sobre Redis
Streams/Postgres/Vault con fan-out/fan-in y auditoría, y sandbox de red por contenedor con
egress deny-by-default vía proxy Squid). Ver
[docs/design/0003-entregable-2-status.md](docs/design/0003-entregable-2-status.md) y
[docs/design/0004-sandbox-exec-model.md](docs/design/0004-sandbox-exec-model.md).

**Entregable 4 completo**: reglas de plataforma fijas (`behavior/`) + policy de
comportamiento configurable por subagente (`meridianctl policy`) — Meridian no asume
ningún dominio, cada subagente define qué es irreversible, cuándo pedir aprobación,
reintentos y tono. Ver [docs/design/0005-behavior-policy.md](docs/design/0005-behavior-policy.md).

**Roadmap original (PROJECT_BRIEF.md sección 7) completo**: entregables 1-6 implementados
y verificados end-to-end, incluyendo un caso de prueba de dominio real (buscador de papers
en arXiv, [0007](docs/design/0007-paper-search-app.md)), observabilidad
([0008](docs/design/0008-observability.md)) y una capa multi-proveedor LLM
(Anthropic/OpenAI, [0009](docs/design/0009-llm-provider-layer.md)).

Pendiente de un paso manual de Rodrigo (no delegable: entrar una API key real): guardar su
credencial de Anthropic/OpenAI vía `meridianctl secrets put` y correr `meridianctl llm
test` para confirmar la llamada real al proveedor.

Próximos pasos posibles, sin decidir todavía: un tercer gateway conversacional real
(Telegram), conectar el enforcement de `subagent_policy` al camino de ejecución, o el
primer subagente de un dominio de negocio real.

## Stack

- Python
- Postgres (identidad, scopes, allowlists, auditoría)
- Redis Streams (bus interno gateways ↔ main ↔ subagentes)
- Vault externo (HashiCorp Vault / 1Password) para secretos
- Docker (un contenedor por subagente)
- Multi-proveedor LLM configurable por agente (Claude, Codex/OpenAI, Gemini)

## Estructura

Ver [docs/design/0002-repo-structure-and-cli.md](docs/design/0002-repo-structure-and-cli.md).
