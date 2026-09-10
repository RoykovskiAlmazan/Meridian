"""Conexión a la base configurada (`DB_BACKEND`: postgres | mysql | mssql) vía SQLAlchemy
Core -- ver docs/design/0017-database-compatibility.md. Un connection-per-call (con su
propia transacción) es suficiente para el MVP; pool de conexiones queda para cuando haya
carga real."""
import contextlib

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from meridian.config import settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.database_url)
    return _engine


@contextlib.contextmanager
def get_conn():
    engine = get_engine()
    with engine.begin() as conn:  # engine.begin() hace commit al salir, rollback si hay excepción
        yield conn


def dispose_engine() -> None:
    """Para pruebas/reconfiguración -- fuerza recrear el engine en la próxima llamada a
    get_engine() (útil si settings.database_url cambió, ej. en tests)."""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None
