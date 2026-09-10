import subprocess
from pathlib import Path

import typer

app = typer.Typer(help="Enciende o apaga los servicios base de Meridian en tu máquina (base de datos, cola de mensajes, bóveda de secretos) usando Docker.")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_COMPOSE_FILE = _REPO_ROOT / "docker" / "docker-compose.yml"
_ENV_FILE = _REPO_ROOT / ".env"

# --env-file explícito: `docker compose -f docker/docker-compose.yml` no siempre resuelve
# el .env de la raíz del repo de forma confiable a partir de solo el cwd (depende de cómo
# Compose calcule el "directorio de proyecto" a partir de -f) -- se comprobó en la práctica
# que sin esto SUBAGENT_ID/etc. de subagentes de dominio real quedaban vacíos en silencio.
_BASE_CMD = ["docker", "compose", "--env-file", str(_ENV_FILE), "-f", str(_COMPOSE_FILE)]

_PROFILES = ["subagents", "research"]


@app.command(
    "up",
    help="Levanta Postgres, Redis, Vault, main, y los gateways base con Docker Compose (usa `--env-file .env` explícito, ver comentario abajo). Vault puede necesitar `meridianctl vault unseal` después si el contenedor se reinició.",
    epilog=(
        "Ejemplos:\n\n"
        "  meridianctl dev up\n"
        "  meridianctl dev up --subagents          # + sample_subagent_a/b\n"
        "  meridianctl dev up --research            # + paper_search/paper_summarizer"
    ),
)
def up(
    subagents: bool = typer.Option(False, "--subagents", help="Incluir sample_subagent_a/b (requiere SUBAGENT_A_ID/SUBAGENT_B_ID en .env)."),
    research: bool = typer.Option(False, "--research", help="Incluir paper_search/paper_summarizer (requiere PAPER_SEARCH_SUBAGENT_ID/PAPER_SUMMARIZER_SUBAGENT_ID en .env)."),
) -> None:
    cmd = list(_BASE_CMD)
    if subagents:
        cmd += ["--profile", "subagents"]
    if research:
        cmd += ["--profile", "research"]
    cmd += ["up", "-d", "--build"]
    subprocess.run(cmd, check=True, cwd=_REPO_ROOT)


@app.command(
    "down",
    help="Baja todos los contenedores (todos los profiles incluidos) -- los datos en los volúmenes de Postgres/Vault no se borran.",
    epilog="Ejemplo:\n\n  meridianctl dev down",
)
def down() -> None:
    cmd = list(_BASE_CMD)
    for profile in _PROFILES:
        cmd += ["--profile", profile]
    cmd += ["down"]
    subprocess.run(cmd, check=True, cwd=_REPO_ROOT)
