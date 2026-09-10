"""Aplica docker/init/postgres_schema.sql contra la base configurada -- útil para
`meridianctl doctor --fix` cuando un volumen de Postgres ya existía antes de agregar una
tabla nueva (el init script de Docker solo corre en un volumen vacío la primera vez).

El schema es 100% idempotente (`CREATE TABLE/INDEX IF NOT EXISTS`), así que aplicarlo de
más nunca rompe nada -- ver docker/init/postgres_schema.sql.
"""
from __future__ import annotations

import os
from pathlib import Path

from meridian.identity.db import get_conn


def _find_schema_file() -> Path:
    override = os.environ.get("MERIDIAN_SCHEMA_FILE")
    if override:
        return Path(override)

    candidates = [
        Path(__file__).resolve().parents[2] / "docker" / "init" / "postgres_schema.sql",
        Path.cwd() / "docker" / "init" / "postgres_schema.sql",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "No se encontró docker/init/postgres_schema.sql en ninguna ubicación candidata "
        f"({[str(c) for c in candidates]}). Define MERIDIAN_SCHEMA_FILE explícitamente."
    )


def apply_schema() -> None:
    sql = _find_schema_file().read_text(encoding="utf-8")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql)
