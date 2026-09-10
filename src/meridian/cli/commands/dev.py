import subprocess
from pathlib import Path

import typer

app = typer.Typer(help="Levanta/baja la infra de soporte local (Postgres, Redis, Vault dev).")

_REPO_ROOT = Path(__file__).resolve().parents[4]
_COMPOSE_FILE = _REPO_ROOT / "docker" / "docker-compose.yml"


@app.command("up")
def up(subagents: bool = typer.Option(False, "--subagents", help="Incluir sample_subagent_a/b (requiere SUBAGENT_A_ID/SUBAGENT_B_ID en .env).")) -> None:
    cmd = ["docker", "compose", "-f", str(_COMPOSE_FILE), "up", "-d", "--build"]
    if subagents:
        cmd = ["docker", "compose", "-f", str(_COMPOSE_FILE), "--profile", "subagents", "up", "-d", "--build"]
    subprocess.run(cmd, check=True, cwd=_REPO_ROOT)


@app.command("down")
def down() -> None:
    subprocess.run(
        ["docker", "compose", "-f", str(_COMPOSE_FILE), "--profile", "subagents", "down"],
        check=True,
        cwd=_REPO_ROOT,
    )
