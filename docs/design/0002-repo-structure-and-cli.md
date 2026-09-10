# Estructura del repo y CLI de administración (meridianctl)

Estado: propuesta v1 para revisión con Rodrigo. Estructura ya creada como esqueleto
(carpetas + `.gitkeep`), sin lógica implementada todavía — eso es el entregable 2.

## 1. Por qué esta forma

- `src/meridian/` como único paquete Python instalable: todo el código (main, gateways,
  subagentes de referencia, cliente de bus, identidad, secretos, CLI) vive bajo el mismo
  paquete versionado, coherente con la separación código/estado que funcionó bien en OpenClaw
  (sección 2 del brief) — el repo es stateless, la config/credenciales/datos viven fuera
  (Postgres, Vault, volúmenes de Docker), nunca en el repo.
- Cada subagente de prueba tiene su propio subpaquete + su propio `Dockerfile` — refleja
  1:1 la decisión de "contenedor por subagente" (sección 8 del brief), nada de un contenedor
  compartido para todos.
- `cli/` es un subpaquete más del mismo proyecto, no un repo aparte — la petición de Rodrigo
  es poder administrar *todo* desde consola, así que la CLI debe tener acceso directo a los
  mismos módulos de identidad/bus/secretos que usa el runtime, no reimplementar llamadas HTTP
  contra sí mismo.
- `docker/docker-compose.yml` levanta la infra de soporte (Postgres, Redis, Vault en modo
  dev) para que el MVP completo corra igual en Windows y Linux con un solo comando.

## 2. Árbol de carpetas (esqueleto ya creado)

```
multiagent-platform/                 (raíz del repo; nombre de paquete interno: meridian)
├── PROJECT_BRIEF.md
├── README.md
├── pyproject.toml
├── .env.example
├── docs/
│   └── design/
│       ├── 0001-task-intent-schema.md
│       └── 0002-repo-structure-and-cli.md
├── schemas/
│   ├── task_intent.v1.schema.json
│   └── task_result.v1.schema.json
├── docker/
│   ├── docker-compose.yml          # postgres + redis + vault (dev mode)
│   └── subagents/
│       ├── sample_subagent_a.Dockerfile
│       └── sample_subagent_b.Dockerfile
├── src/
│   └── meridian/
│       ├── __init__.py
│       ├── main_agent/             # el orquestador "main": valida, rutea, agrega
│       ├── gateways/
│       │   └── mock_gateway/       # gateway de prueba para el MVP (entregable 2)
│       ├── subagents/
│       │   ├── sample_subagent_a/
│       │   └── sample_subagent_b/
│       ├── bus/                    # wrapper de Redis Streams (producer/consumer, fan-out/fan-in)
│       ├── identity/               # modelos + queries de Postgres: tenants, gateways, subagents, allowlist
│       ├── secrets/                # cliente de Vault + resolución de SecretRef
│       └── cli/                    # meridianctl (Typer)
│           └── commands/
└── tests/
    ├── unit/
    └── integration/
```

## 3. CLI: `meridianctl`

Objetivo de Rodrigo: poder configurar y operar toda la Plataforma desde consola, sin
depender de un panel web para tareas de administración. Propuesta de librería: **Typer**
(sobre Click) — es el estándar de facto en Python para CLIs con subcomandos, tipado y
autogeneración de `--help`, y corre igual en Windows/Linux.

Subcomandos propuestos para el MVP (entregable 1-2; se amplía según haga falta):

| Comando | Qué hace |
|---|---|
| `meridianctl dev up` / `dev down` | Levanta/baja la infra de soporte (`docker compose`: Postgres, Redis, Vault dev). |
| `meridianctl tenant create --name ...` | Alta de tenant. |
| `meridianctl tenant list` | Lista tenants y su estado. |
| `meridianctl gateway create --tenant ... --type whatsapp\|internal_api\|cron\|web_panel --name ...` | Alta de gateway; genera su identidad y crea el `credential_ref` en Vault. |
| `meridianctl gateway rotate-credential --id ...` | Rota la credencial de un gateway sin tocar su `id` ni sus scopes. |
| `meridianctl gateway revoke --id ...` | Revoca un gateway (`status = revoked`), efecto inmediato en la validación del `main`. |
| `meridianctl subagent create --tenant ... --name ... --domain ...` | Alta de subagente. |
| `meridianctl allow --gateway ... --subagent ... --intents billing.send_invoice,crm.update_contact` | Da de alta una entrada en la allowlist gateway↔subagente (nunca implícito, sección 3 del brief). |
| `meridianctl allow list --gateway ...` \| `--subagent ...` | Inspecciona la allowlist vigente. |
| `meridianctl audit tail --tenant ... [--correlation-id ...]` | Sigue el `audit_log` en vivo, filtrable por tenant o por una solicitud puntual — para depurar "quién pidió qué y por qué se delegó" (requisito de trazabilidad, sección 5). |
| `meridianctl bus status` | Salud del bus: streams activos, consumer groups, lag por consumidor. |
| `meridianctl config check` | Valida que `.env`/config apunten a Postgres, Redis y Vault accesibles antes de arrancar nada. |

Todo comando que muta estado (`create`, `revoke`, `rotate-credential`, `allow`) escribe su
propia entrada en `audit_log` con el usuario de SO que lo ejecutó — la CLI es, en sí misma,
otro actor que debe quedar trazado, igual que un gateway.

## 4. Abierto

- Si `meridianctl` termina necesitando autenticarse contra un `main` remoto (en vez de tener
  acceso directo a Postgres/Vault/Redis desde la máquina del operador) — relevante el día que
  la Plataforma no corra en la misma máquina que la consola del operador. No resuelto todavía;
  para el MVP asumimos acceso directo local/red interna.
