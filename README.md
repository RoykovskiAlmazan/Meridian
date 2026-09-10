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

**Entregable 5 completo**: segundo gateway real (cron, `meridianctl cron`) agregado sin
tocar `main_agent` — confirma que el contrato interno aguanta un tipo de gateway distinto
al mock HTTP. Ver [docs/design/0006-cron-gateway.md](docs/design/0006-cron-gateway.md).

Siguiente: un tercer gateway conversacional real (ej. Telegram) para seguir estresando el
contrato, o profundizar en el primer subagente de dominio real — pendiente de decidir con
Rodrigo.

## Stack

- Python
- Postgres (identidad, scopes, allowlists, auditoría)
- Redis Streams (bus interno gateways ↔ main ↔ subagentes)
- Vault externo (HashiCorp Vault / 1Password) para secretos
- Docker (un contenedor por subagente)
- Multi-proveedor LLM configurable por agente (Claude, Codex/OpenAI, Gemini)

## Estructura

Ver [docs/design/0002-repo-structure-and-cli.md](docs/design/0002-repo-structure-and-cli.md).
