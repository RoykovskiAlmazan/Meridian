"""Subagente de prueba A -- para el MVP solo hace eco del payload marcado con su nombre.
Uso: SUBAGENT_ID=<uuid de subagents.id> python -m meridian.subagents.sample_subagent_a.main
"""
import os
import sys
from typing import Any

from meridian.subagents.worker_base import run


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    return {"handled_by": "sample_subagent_a", "echo": payload}


def main() -> None:
    subagent_id = os.environ.get("SUBAGENT_ID")
    if not subagent_id:
        print("Falta SUBAGENT_ID en el entorno (uuid de subagents.id en Postgres)", file=sys.stderr)
        raise SystemExit(1)
    run(subagent_id, handle)


if __name__ == "__main__":
    main()
