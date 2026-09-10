# Instalabilidad, `meridianctl doctor` y UX de consola (beta)

Estado: implementado y verificado en esta máquina.

## 1. Objetivo

Pasar de "un proyecto que solo yo (Claude) sé levantar porque lo fui armando paso a paso"
a "un repo que alguien más puede clonar, instalar y usar" — sin que el onboarding fuerce
a nadie a montar el ejemplo de papers ni a asumir el dominio de inventario de Rodrigo.

## 2. Qué cambió

- **README.md reescrito** como guía de instalación real (requisitos, quickstart,
  `meridianctl doctor`, cómo escribir tu propio subagente, referencia de CLI, seguridad),
  con el ejemplo de `paper_search`/`paper_summarizer` movido a una sección explícitamente
  marcada como opcional (no se levanta con `meridianctl dev up` normal, solo con
  `--research`).
- **`docker/init/postgres_schema.sql` ahora es 100% idempotente**
  (`CREATE TABLE/INDEX IF NOT EXISTS` en todas partes) -- necesario tanto para una
  instalación nueva (sin cambios de comportamiento) como para que `doctor --fix` pueda
  reaplicarlo sin riesgo sobre una base que ya tiene datos.
- **`meridian/schema_apply.py`**: aplica ese SQL contra la base configurada, con la misma
  estrategia de resolución de ruta por candidatos que ya se usa en `messages.py` para
  `schemas/` (lección del entregable 2: una ruta relativa al archivo fuente no sobrevive
  una instalación empaquetada).
- **`meridianctl doctor`** (`src/meridian/cli/commands/doctor.py`): valida `.env`, Docker
  (CLI + daemon), Postgres (conectividad + que existan las 8 tablas esperadas), Redis,
  Vault (autenticación + que el secrets engine `secret` esté montado), y que `schemas/` se
  resuelva. `--fix` repara lo seguro de reparar solo: crear `.env` desde `.env.example` si
  falta, aplicar tablas de Postgres que falten. No toca nada que requiera una decisión
  humana (credenciales, `VAULT_TOKEN`, etc.).
- **UX de consola** (`src/meridian/cli/console.py`): banner ASCII con versión al invocar
  `meridianctl` sin argumentos, `--version`, y tablas de Rich (`print_records`/
  `print_record`) reemplazando los `typer.echo(dict)` crudos en todos los comandos de
  alta/consulta (tenant, gateway, subagent, allow, cron, policy, llm, audit, bus).
- **Corrección de seguridad de paso**: `gateway create --token <valor>` y
  `rotate-credential --token <valor>` pasaban el secreto como argumento de CLI (visible en
  el historial de shell) -- se cambiaron a un prompt oculto (`typer.prompt(hide_input=True)`),
  igual que `meridianctl secrets put`. Inconsistente dejar uno seguro y el otro no.

## 3. Bug encontrado y corregido: símbolos Unicode tumbaban la consola de Windows

`console.ok()`/`fail()` usaban "✓"/"✗" (fuera del rango de `cp1252`). En una consola
clásica de Windows (sin Windows Terminal) esto producía un `UnicodeEncodeError` real y
tumbaba el comando -- se comprobó al correr `meridianctl doctor` por primera vez. Se
reemplazaron por marcadores ASCII (`[OK]`/`[FAIL]`/`[WARN]`) que funcionan en cualquier
terminal (cmd.exe, PowerShell, Git Bash, Windows Terminal, Linux).

## 4. Verificación hecha

- `meridianctl doctor` corrido limpio contra la instalación real (todos los chequeos en
  `[OK]`).
- Simulado un `DROP TABLE subagent_llm_config` y confirmado que `doctor` lo detecta como
  `[FAIL]` y que `doctor --fix` lo repara sin tocar el resto del schema ni los datos
  existentes.
- Simulado un `.env` ausente (renombrado temporalmente) y confirmado tanto la detección
  como la reparación con `--fix`, restaurando después el `.env` real sin pérdida de datos.
- `meridianctl --version`, el banner de `meridianctl` sin argumentos, y las tablas de
  `tenant/gateway/subagent/cron/policy list|get` corridos contra datos reales, sin errores.

## 5. Fuera de alcance (para una beta más adelante)

- Un `meridianctl init` interactivo tipo wizard (hoy el quickstart del README es la guía
  paso a paso; un wizard que automatice esos pasos es una mejora incremental, no crítica).
- Empaquetado como binario único (`pyinstaller`/`shiv`) para instalar sin tener Python
  configurado -- no hay pedido concreto de esto todavía.
- Ancho de las tablas de Rich no se ajusta perfectamente en terminales muy angostas o no
  interactivas (pipes) -- en una terminal real (Windows Terminal, iTerm, etc.) se ve bien;
  no se optimizó más allá porque no hay una queja concreta sobre esto.
