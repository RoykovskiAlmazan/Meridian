# Meridian

**Orquestación multiagente de propósito general.** *(codename: Project Foreman)*

[![status](https://img.shields.io/badge/status-beta-yellow)]()
[![python](https://img.shields.io/badge/python-3.11%2B-blue)]()
[![license](https://img.shields.io/badge/license-private-lightgrey)]()

Meridian recibe instrucciones de múltiples **gateways** (HTTP, cron, y lo que agregues),
las autoriza contra reglas explícitas, y las delega a **subagentes** especializados que
ejecutan tareas — de cualquier dominio que tú definas. Meridian no viene con un caso de
uso fijo: puede orquestar inventario, organizar archivos, investigación, atención a
clientes, o cualquier otra combinación de tareas automatizadas.

> **Estado: beta.** Núcleo funcional y probado end-to-end (ver [PROJECT_BRIEF.md](PROJECT_BRIEF.md)
> y [docs/design/](docs/design/)), pero sin garantías de estabilidad de API todavía.

## Por qué

- **Multi-gateway → main → multi-subagente**, con fan-out/fan-in y trazabilidad completa
  (`correlation_id` de punta a punta).
- **Multi-tenant real** desde el diseño: cada instalación puede aislar múltiples clientes/
  operadores con scopes propios.
- **Seguro por defecto**: cada subagente corre en su propio contenedor, sin ruta a
  internet salvo que declares explícitamente qué dominio necesita; nunca hay secretos en
  texto plano (todo vía referencias a Vault); allowlist explícita gateway↔subagente, nunca
  implícita.
- **Todo administrable desde consola** (`meridianctl`) — sin depender de un panel web.
- **Multi-proveedor LLM**: Anthropic, OpenAI (Gemini pendiente), configurable por subagente.

## Requisitos

- Python 3.11+
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (con el daemon corriendo)
- Git

## Instalación

```bash
git clone <la URL de tu fork/repo> meridian
cd meridian

python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

pip install -e .
cp .env.example .env
```

Levanta la infraestructura de soporte (Postgres, Redis, Vault en modo dev, y los
procesos de la plataforma) y corre el diagnóstico de salud:

```bash
meridianctl dev up
meridianctl doctor
```

`doctor` valida que todo esté realmente listo (Docker, `.env`, Postgres con el schema
completo, Redis, Vault) y con `--fix` intenta reparar lo que es seguro reparar solo
(crear `.env` desde el ejemplo si falta, aplicar tablas de Postgres que falten):

```bash
meridianctl doctor --fix
```

## Primeros pasos: crea tu primera identidad

Ejemplo genérico — sustituye por lo que tú quieras automatizar:

```bash
# 1. Un tenant (tu instalación, o un cliente si operas multi-tenant)
meridianctl tenant create --name mi-organizacion

# 2. Un gateway (cómo entran las instrucciones: HTTP, cron, etc.)
meridianctl gateway create --tenant <tenant_id> --type internal_api --name mi-gateway
# pide la credencial de forma oculta, nunca en texto plano

# 3. Un subagente (qué hace el trabajo -- tú escribes su lógica en src/meridian/subagents/)
meridianctl subagent create --tenant <tenant_id> --name mi-subagente --domain lo-que-sea

# 4. Autorización explícita gateway -> subagente para un intent específico
meridianctl allow set --gateway <gateway_id> --subagent <subagent_id> --intents mi_dominio.mi_accion
```

Dispara una instrucción de prueba vía el gateway HTTP mínimo incluido (`mock_gateway`):

```bash
curl -X POST http://localhost:8080/intent \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"<tenant_id>","gateway_id":"<gateway_id>","intent_type":"mi_dominio.mi_accion","subagent_ids":["<subagent_id>"],"payload":{}}'
```

## Escribir tu propio subagente

Un subagente es un proceso Python que consume de su propio stream y responde con un
resultado — ver `src/meridian/subagents/worker_base.py` y cualquiera de los subagentes
existentes como plantilla. Estructura mínima:

```python
from meridian.subagents.worker_base import run

def handle(payload: dict) -> dict:
    # tu lógica aquí -- payload es lo que venga en intent.payload
    return {"resultado": "lo que sea"}

run(subagent_id, handle)
```

Empaquétalo con su propio `Dockerfile` (copia el patrón de
`docker/subagents/sample_subagent_a.Dockerfile`) y agrégalo a `docker/docker-compose.yml`
bajo un profile propio.

## CLI (`meridianctl`)

```
meridianctl doctor              Diagnóstico de salud (con --fix)
meridianctl dev up/down         Infra de soporte (Docker Compose)
meridianctl tenant ...          Alta/consulta de tenants
meridianctl gateway ...         Alta/consulta/revocación de gateways
meridianctl subagent ...        Alta/consulta de subagentes
meridianctl allow ...           Allowlist explícita gateway x subagente
meridianctl policy ...          Comportamiento configurable por subagente
meridianctl secrets put         Alta de secretos en Vault (prompt oculto)
meridianctl llm set/get/test    Proveedor LLM por subagente
meridianctl cron ...            Gateway de tipo cron (disparos programados)
meridianctl audit tail/prune    Auditoría y retención
meridianctl bus status          Salud del bus interno (Redis Streams)
```

`meridianctl --help` y `meridianctl <comando> --help` documentan cada opción.

## Seguridad

- **Ningún secreto en texto plano**: credenciales de gateways y API keys de LLM viven en
  Vault, referenciadas por un `SecretRef` opaco. `meridianctl secrets put` y
  `gateway create` piden el valor con un prompt oculto, nunca como argumento de CLI.
- **Sandbox de red por contenedor**: un subagente nuevo no tiene salida a internet hasta
  que agregues explícitamente su dominio permitido en `docker/sandbox/squid.conf`. Ver
  [docs/design/0004-sandbox-exec-model.md](docs/design/0004-sandbox-exec-model.md).
- **Allowlist explícita**: ningún gateway puede invocar un subagente sin una entrada
  explícita en `gateway_subagent_allowlist`.
- **Auditoría completa**: todo mensaje que cruza el sistema queda en `audit_log` con su
  `correlation_id`, consultable con `meridianctl audit tail`.

## Ejemplo incluido (opcional): buscador de papers

El repo incluye un caso de prueba de dominio real bajo el profile `research` de Docker
Compose (`paper_search` + `paper_summarizer`, buscan y resumen papers de arXiv). **Es
solo un ejemplo de referencia, no un requisito de instalación** — no se levanta con
`meridianctl dev up` normal, solo con `meridianctl dev up --research`, y puedes ignorarlo
o borrarlo por completo si no lo necesitas. Ver
[docs/design/0007-paper-search-app.md](docs/design/0007-paper-search-app.md) si quieres
probarlo o usarlo como plantilla para tu propio subagente con LLM.

## Documentación

- [PROJECT_BRIEF.md](PROJECT_BRIEF.md) — objetivo, decisiones de arquitectura y su porqué.
- [docs/design/](docs/design/) — un documento por decisión/entregable, en orden.
- [behavior/](behavior/) — reglas de comportamiento de la plataforma (fijas) vs. policy
  configurable por subagente.
