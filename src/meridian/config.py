"""Carga de configuración desde variables de entorno (.env en desarrollo)."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    # DB_BACKEND: postgres (default) | mysql | mssql -- ver
    # docs/design/0017-database-compatibility.md. Las variables DB_HOST/DB_PORT/DB_NAME/
    # DB_USER/DB_PASSWORD son las nuevas genéricas; si no están definidas, se cae a las
    # POSTGRES_* de siempre para no romper instalaciones existentes.
    db_backend: str = os.getenv("DB_BACKEND", "postgres")
    db_host: str = os.getenv("DB_HOST", os.getenv("POSTGRES_HOST", "localhost"))
    db_port: str = os.getenv("DB_PORT", os.getenv("POSTGRES_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", os.getenv("POSTGRES_DB", "meridian"))
    db_user: str = os.getenv("DB_USER", os.getenv("POSTGRES_USER", "meridian"))
    db_password: str = os.getenv("DB_PASSWORD", os.getenv("POSTGRES_PASSWORD", "meridian_dev_only"))

    # Alias retrocompatibles -- código/docs viejos que lean settings.postgres_* siguen
    # funcionando sin cambios mientras el backend sea Postgres.
    postgres_host: str = db_host
    postgres_port: int = int(db_port)
    postgres_db: str = db_name
    postgres_user: str = db_user
    postgres_password: str = db_password

    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))

    vault_addr: str = os.getenv("VAULT_ADDR", "http://localhost:8200")
    vault_token: str = os.getenv("VAULT_TOKEN", "dev-only-root-token")

    mock_gateway_port: int = int(os.getenv("MOCK_GATEWAY_PORT", "8080"))

    # Nombre exacto del driver ODBC instalado en esta máquina -- varía según cuándo se
    # instaló ("ODBC Driver 17 for SQL Server" vs. "...18..."). Configurable porque no
    # todas las máquinas tienen la misma versión.
    mssql_odbc_driver: str = os.getenv("MSSQL_ODBC_DRIVER", "ODBC Driver 17 for SQL Server")

    @property
    def database_url(self) -> str:
        """URL de SQLAlchemy para el backend configurado -- ver
        docs/design/0017-database-compatibility.md."""
        if self.db_backend == "postgres":
            return f"postgresql+psycopg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        if self.db_backend == "mysql":
            return f"mysql+pymysql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
        if self.db_backend == "mssql":
            driver = self.mssql_odbc_driver.replace(" ", "+")
            return f"mssql+pyodbc://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}?driver={driver}&TrustServerCertificate=yes"
        raise ValueError(f"DB_BACKEND no soportado: {self.db_backend!r} (usa postgres | mysql | mssql)")


settings = Settings()
