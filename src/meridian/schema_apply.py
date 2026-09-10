"""Aplica el schema (SQLAlchemy Core, ver `meridian.identity.schema_meta`) contra la base
configurada -- útil para `meridianctl doctor --fix` cuando una base ya existía antes de
agregar una tabla nueva.

`metadata.create_all()` es idempotente por diseño de SQLAlchemy (revisa qué tablas ya
existen antes de crear), y funciona igual contra Postgres/MySQL/MSSQL -- ver
docs/design/0017-database-compatibility.md. A diferencia del script SQL crudo que se usó
hasta el entregable de compatibilidad de bases de datos, esto NO agrega columnas nuevas a
una tabla que ya existe con un schema viejo (create_all únicamente crea tablas que faltan
por completo) -- una migración real de columnas requeriría una herramienta tipo Alembic,
fuera de alcance por ahora (ver docs/design/0012-improvement-opportunities.md).
"""
from __future__ import annotations

from meridian.identity.db import get_engine
from meridian.identity.schema_meta import metadata


def apply_schema() -> None:
    metadata.create_all(get_engine())
