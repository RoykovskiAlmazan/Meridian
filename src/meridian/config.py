"""Carga de configuración desde variables de entorno (.env en desarrollo)."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    postgres_host: str = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_db: str = os.getenv("POSTGRES_DB", "meridian")
    postgres_user: str = os.getenv("POSTGRES_USER", "meridian")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "meridian_dev_only")

    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))

    vault_addr: str = os.getenv("VAULT_ADDR", "http://localhost:8200")
    vault_token: str = os.getenv("VAULT_TOKEN", "dev-only-root-token")

    mock_gateway_port: int = int(os.getenv("MOCK_GATEWAY_PORT", "8080"))

    @property
    def postgres_dsn(self) -> str:
        return (
            f"host={self.postgres_host} port={self.postgres_port} "
            f"dbname={self.postgres_db} user={self.postgres_user} "
            f"password={self.postgres_password}"
        )


settings = Settings()
