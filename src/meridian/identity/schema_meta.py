"""Definición del schema con SQLAlchemy Core -- fuente de verdad única, portable entre
Postgres/MySQL/MSSQL (ver docs/design/0017-database-compatibility.md). Reemplaza
docker/init/postgres_schema.sql (que documentaba el schema en SQL nativo de Postgres,
específico de ese motor -- IDs UUID nativos, JSONB, arrays TEXT[], `gen_random_uuid()`,
ninguno de los cuales existe igual en MySQL/MSSQL).

Los tipos usan `.with_variant(...)` para que Postgres siga usando sus tipos nativos (UUID,
JSONB, ARRAY) -- exactamente lo que ya tenían las tablas creadas por el schema SQL viejo,
así que esto NO requiere ninguna migración de datos en una instalación de Postgres ya
existente -- y que MySQL/MSSQL (sin esos tipos nativos) usen equivalentes portables
(CHAR(36), JSON) en su lugar.

Los ids se generan en Python (`uuid.uuid4()`) al insertar, no como default de la base --
así el mismo código de aplicación funciona igual sin importar qué tan bien soporte cada
motor los defaults de columna.
"""
from __future__ import annotations

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql

metadata = MetaData()

# Postgres: UUID nativo (coincide con las tablas ya creadas por el schema SQL viejo).
# MySQL/MSSQL: CHAR(36) -- ningún motor no-Postgres tiene un tipo UUID verdaderamente
# universal a través de SQLAlchemy, así que se guarda como texto de 36 caracteres.
UUID_TYPE = String(36).with_variant(postgresql.UUID(as_uuid=False), "postgresql")

# Postgres: JSONB nativo. MySQL/MSSQL: JSON genérico (SQLAlchemy lo mapea al tipo JSON de
# cada motor, o a TEXT si el motor no tiene JSON nativo).
JSON_TYPE = JSON().with_variant(postgresql.JSONB(), "postgresql")

# Postgres: ARRAY(TEXT) nativo (coincide con las columnas TEXT[] ya existentes).
# MySQL/MSSQL: se guarda como JSON (una lista), ya que ninguno de los dos tiene un tipo
# array nativo utilizable de forma portable.
STR_LIST_TYPE = JSON().with_variant(postgresql.ARRAY(Text()), "postgresql")


def _uuid_col(name: str = "id", primary_key: bool = True, fk: str | None = None) -> Column:
    if fk:
        return Column(name, UUID_TYPE, ForeignKey(fk), nullable=not primary_key)
    return Column(name, UUID_TYPE, primary_key=primary_key)


tenants = Table(
    "tenants", metadata,
    _uuid_col(),
    Column("name", String(255), nullable=False, unique=True),
    Column("status", String(20), nullable=False, server_default="active"),
    Column("created_at", DateTime, nullable=False),
    CheckConstraint("status IN ('active', 'suspended')", name="tenants_status_check"),
)

gateways = Table(
    "gateways", metadata,
    _uuid_col(),
    _uuid_col("tenant_id", primary_key=False, fk="tenants.id"),
    Column("type", String(30), nullable=False),
    Column("name", String(255), nullable=False),
    Column("credential_ref", Text, nullable=True),
    Column("status", String(20), nullable=False, server_default="active"),
    Column("created_at", DateTime, nullable=False),
    Column("rotated_at", DateTime, nullable=True),
    UniqueConstraint("tenant_id", "name", name="gateways_tenant_name_uq"),
    CheckConstraint(
        "type IN ('whatsapp','telegram','internal_api','cron','web_panel','subagent_delegate','other')",
        name="gateways_type_check",
    ),
    CheckConstraint("status IN ('active', 'revoked')", name="gateways_status_check"),
)

subagents = Table(
    "subagents", metadata,
    _uuid_col(),
    _uuid_col("tenant_id", primary_key=False, fk="tenants.id"),
    Column("name", String(255), nullable=False),
    Column("domain", String(255), nullable=False),
    Column("status", String(20), nullable=False, server_default="active"),
    # Auto-referencia (sub-subagentes, ver docs/design/0014-sub-subagents.md) -- se puede
    # declarar directo en la misma Table con un string "tabla.columna", SQLAlchemy la
    # resuelve una vez que la tabla completa está definida.
    Column("parent_subagent_id", UUID_TYPE, ForeignKey("subagents.id"), nullable=True),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("tenant_id", "name", name="subagents_tenant_name_uq"),
    CheckConstraint("status IN ('active', 'revoked')", name="subagents_status_check"),
)

subagent_subagent_allowlist = Table(
    "subagent_subagent_allowlist", metadata,
    _uuid_col("parent_subagent_id", primary_key=True, fk="subagents.id"),
    _uuid_col("child_subagent_id", primary_key=True, fk="subagents.id"),
    Column("allowed_intents", STR_LIST_TYPE, nullable=False),
    Column("created_at", DateTime, nullable=False),
)

pending_approvals = Table(
    "pending_approvals", metadata,
    _uuid_col(),
    _uuid_col("tenant_id", primary_key=False, fk="tenants.id"),
    Column("correlation_id", UUID_TYPE, nullable=False),
    _uuid_col("subagent_id", primary_key=False, fk="subagents.id"),
    Column("intent", JSON_TYPE, nullable=False),
    Column("status", String(20), nullable=False, server_default="pending"),
    Column("reason", Text, nullable=True),
    Column("created_at", DateTime, nullable=False),
    Column("decided_at", DateTime, nullable=True),
    Column("decided_by", String(255), nullable=True),
    CheckConstraint("status IN ('pending', 'approved', 'denied')", name="pending_approvals_status_check"),
    Index("idx_pending_approvals_status", "status"),
)

gateway_subagent_allowlist = Table(
    "gateway_subagent_allowlist", metadata,
    _uuid_col("gateway_id", primary_key=True, fk="gateways.id"),
    _uuid_col("subagent_id", primary_key=True, fk="subagents.id"),
    Column("allowed_intents", STR_LIST_TYPE, nullable=False),
    Column("created_at", DateTime, nullable=False),
)

subagent_policy = Table(
    "subagent_policy", metadata,
    _uuid_col("subagent_id", primary_key=True, fk="subagents.id"),
    Column("policy", JSON_TYPE, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)

cron_jobs = Table(
    "cron_jobs", metadata,
    _uuid_col(),
    _uuid_col("tenant_id", primary_key=False, fk="tenants.id"),
    _uuid_col("gateway_id", primary_key=False, fk="gateways.id"),
    Column("name", String(255), nullable=False),
    Column("schedule", String(255), nullable=False),
    Column("intent_type", String(255), nullable=False),
    Column("subagent_ids", STR_LIST_TYPE, nullable=False),
    Column("payload", JSON_TYPE, nullable=False),
    Column("enabled", Boolean, nullable=False, server_default="1"),
    Column("last_run_at", DateTime, nullable=True),
    Column("created_at", DateTime, nullable=False),
    UniqueConstraint("tenant_id", "name", name="cron_jobs_tenant_name_uq"),
)

subagent_llm_config = Table(
    "subagent_llm_config", metadata,
    _uuid_col("subagent_id", primary_key=True, fk="subagents.id"),
    Column("provider", String(30), nullable=False),
    Column("model", String(255), nullable=False),
    Column("credential_ref", Text, nullable=False),
    Column("updated_at", DateTime, nullable=False),
    CheckConstraint(
        "provider IN ('anthropic','openai','gemini','groq','xai')",
        name="subagent_llm_config_provider_check",
    ),
)

audit_log = Table(
    "audit_log", metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    _uuid_col("tenant_id", primary_key=False, fk="tenants.id"),
    Column("correlation_id", UUID_TYPE, nullable=False),
    Column("message_id", UUID_TYPE, nullable=False),
    Column("agent_id", String(255), nullable=False),
    Column("event_type", String(30), nullable=False),
    Column("detail", JSON_TYPE, nullable=False),
    Column("created_at", DateTime, nullable=False),
    Index("idx_audit_log_correlation_id", "correlation_id"),
    Index("idx_audit_log_tenant_id", "tenant_id"),
    Index("idx_audit_log_event_type", "event_type"),
    CheckConstraint(
        "event_type IN ('received','allowed','denied','forwarded','completed','failed',"
        "'pending_approval','approved','approval_denied')",
        name="audit_log_event_type_check",
    ),
)
