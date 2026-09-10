-- Schema mínimo de identidad/scopes/auditoría para el MVP (entregable 1/2 de Meridian).
-- Ver docs/design/0001-task-intent-schema.md para la justificación de cada tabla.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE gateways (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    type            TEXT NOT NULL CHECK (type IN ('whatsapp', 'telegram', 'internal_api', 'cron', 'web_panel', 'other')),
    name            TEXT NOT NULL,
    credential_ref  TEXT,
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    rotated_at      TIMESTAMPTZ,
    UNIQUE (tenant_id, name)
);

CREATE TABLE subagents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id),
    name        TEXT NOT NULL,
    domain      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

CREATE TABLE gateway_subagent_allowlist (
    gateway_id      UUID NOT NULL REFERENCES gateways(id),
    subagent_id     UUID NOT NULL REFERENCES subagents(id),
    allowed_intents TEXT[] NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (gateway_id, subagent_id)
);

-- Comportamiento configurable por subagente: Meridian no asume ningún dominio (puede ser
-- inventario, organizar archivos, investigación, lo que sea), así que qué es "irreversible",
-- cuándo pedir aprobación humana, política de reintentos y tono NO viven hardcodeados en el
-- código ni en behavior/AGENTS.md -- son datos que quien instale Meridian configura por
-- subagente. Ver docs/design/0005-behavior-policy.md.
CREATE TABLE subagent_policy (
    subagent_id  UUID PRIMARY KEY REFERENCES subagents(id),
    policy       JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Gateway de tipo cron (entregable 5): cada fila es un disparo programado, configurable
-- por quien instale Meridian -- el intent/subagentes/payload que dispara son datos, no
-- código. Ver docs/design/0006-cron-gateway.md.
CREATE TABLE cron_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    gateway_id      UUID NOT NULL REFERENCES gateways(id),
    name            TEXT NOT NULL,
    schedule        TEXT NOT NULL,          -- expresión cron de 5 campos, ej. "*/15 * * * *"
    intent_type     TEXT NOT NULL,
    subagent_ids    TEXT[] NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled         BOOLEAN NOT NULL DEFAULT true,
    last_run_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    correlation_id  UUID NOT NULL,
    message_id      UUID NOT NULL,
    agent_id        TEXT NOT NULL,
    event_type      TEXT NOT NULL CHECK (event_type IN ('received', 'allowed', 'denied', 'forwarded', 'completed', 'failed')),
    detail          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_log_correlation_id ON audit_log (correlation_id);
CREATE INDEX idx_audit_log_tenant_id ON audit_log (tenant_id);
