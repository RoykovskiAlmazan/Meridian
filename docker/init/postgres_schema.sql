-- Schema mínimo de identidad/scopes/auditoría para el MVP (entregable 1/2 de Meridian).
-- Ver docs/design/0001-task-intent-schema.md para la justificación de cada tabla.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS tenants (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL UNIQUE,
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gateways (
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

CREATE TABLE IF NOT EXISTS subagents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id),
    name                TEXT NOT NULL,
    domain              TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    parent_subagent_id  UUID REFERENCES subagents(id),  -- NULL = subagente de primer nivel (invocado por un gateway); si no, es un sub-subagente invocado por otro subagente. Ver docs/design/0014-sub-subagents.md.
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, name)
);

-- Delegación subagente -> sub-subagente: mismo patrón que gateway_subagent_allowlist,
-- allowlist explícita, nunca implícita -- un subagente padre no puede invocar
-- automáticamente a cualquier hijo, tiene que estar autorizado igual que un gateway.
CREATE TABLE IF NOT EXISTS subagent_subagent_allowlist (
    parent_subagent_id  UUID NOT NULL REFERENCES subagents(id),
    child_subagent_id   UUID NOT NULL REFERENCES subagents(id),
    allowed_intents     TEXT[] NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (parent_subagent_id, child_subagent_id)
);

-- Aprobación humana pendiente (enforcement de subagent_policy.requires_approval_intents /
-- destructive.requires_approval -- ver docs/design/0005-behavior-policy.md sección 4, ya
-- no pendiente). Un intent que la requiere se guarda aquí en vez de reenviarse de inmediato.
CREATE TABLE IF NOT EXISTS pending_approvals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    correlation_id  UUID NOT NULL,
    subagent_id     UUID NOT NULL REFERENCES subagents(id),
    intent          JSONB NOT NULL,       -- el TaskIntent completo ya dirigido a este subagente, listo para reenviar tal cual si se aprueba
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'denied')),
    reason          TEXT,                 -- por qué requería aprobación (ej. 'requires_approval_intents', 'destructive_not_allowed')
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at      TIMESTAMPTZ,
    decided_by      TEXT                  -- usuario de SO que corrió `meridianctl approvals approve/deny`
);

CREATE INDEX IF NOT EXISTS idx_pending_approvals_status ON pending_approvals (status);

CREATE TABLE IF NOT EXISTS gateway_subagent_allowlist (
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
CREATE TABLE IF NOT EXISTS subagent_policy (
    subagent_id  UUID PRIMARY KEY REFERENCES subagents(id),
    policy       JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Gateway de tipo cron (entregable 5): cada fila es un disparo programado, configurable
-- por quien instale Meridian -- el intent/subagentes/payload que dispara son datos, no
-- código. Ver docs/design/0006-cron-gateway.md.
CREATE TABLE IF NOT EXISTS cron_jobs (
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

-- ALTER idempotente: agrega parent_subagent_id si la tabla subagents ya existía de antes
-- de esta columna (CREATE TABLE IF NOT EXISTS no altera una tabla ya creada).
ALTER TABLE subagents ADD COLUMN IF NOT EXISTS parent_subagent_id UUID REFERENCES subagents(id);

-- Modelo LLM configurable por subagente (decisión #8 del brief: multi-proveedor, no
-- atado a uno solo). credential_ref es siempre un SecretRef a Vault, nunca la API key en
-- claro. Ver docs/design/0009-llm-provider-layer.md.
CREATE TABLE IF NOT EXISTS subagent_llm_config (
    subagent_id     UUID PRIMARY KEY REFERENCES subagents(id),
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    credential_ref  TEXT NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id              BIGSERIAL PRIMARY KEY,
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    correlation_id  UUID NOT NULL,
    message_id      UUID NOT NULL,
    agent_id        TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    detail          JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_correlation_id ON audit_log (correlation_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_id ON audit_log (tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_event_type ON audit_log (event_type);

-- Los CHECK de enum de más abajo se recrean cada vez que se aplica este archivo (idempotente
-- vía DROP CONSTRAINT IF EXISTS + ADD) para poder agregar valores nuevos (proveedores LLM,
-- tipos de evento de auditoría) sin una migración aparte -- ver docs/design/0012 y 0013.
ALTER TABLE subagent_llm_config DROP CONSTRAINT IF EXISTS subagent_llm_config_provider_check;
ALTER TABLE subagent_llm_config ADD CONSTRAINT subagent_llm_config_provider_check
    CHECK (provider IN ('anthropic', 'openai', 'gemini', 'groq', 'xai'));

ALTER TABLE audit_log DROP CONSTRAINT IF EXISTS audit_log_event_type_check;
ALTER TABLE audit_log ADD CONSTRAINT audit_log_event_type_check
    CHECK (event_type IN (
        'received', 'allowed', 'denied', 'forwarded', 'completed', 'failed',
        'pending_approval', 'approved', 'approval_denied'
    ));
