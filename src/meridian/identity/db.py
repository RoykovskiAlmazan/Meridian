"""Conexión a Postgres. Un connection-per-call es suficiente para el MVP
(1 gateway + main + 2 subagentes de prueba); pool de conexiones queda para
cuando haya carga real (entregable 5+)."""
import contextlib
import psycopg

from meridian.config import settings


@contextlib.contextmanager
def get_conn():
    conn = psycopg.connect(settings.postgres_dsn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
