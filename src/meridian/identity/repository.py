"""Operaciones sobre tenants/gateways/subagents/allowlist/audit_log.

Toda decisión de autorización del main (ver docs/design/0001-task-intent-schema.md,
sección 3) pasa por aquí -- nunca se confía en scopes que vengan en el mensaje entrante.
"""
from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from meridian.identity.db import get_conn


# ---- tenants ----------------------------------------------------------

def create_tenant(name: str) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "INSERT INTO tenants (name) VALUES (%s) RETURNING id, name, status, created_at",
            (name,),
        )
        return cur.fetchone()


def list_tenants() -> list[dict[str, Any]]:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute("SELECT id, name, status, created_at FROM tenants ORDER BY created_at")
        return cur.fetchall()


# ---- gateways -----------------------------------------------------------

def create_gateway(tenant_id: UUID, type_: str, name: str, credential_ref: str | None = None) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """INSERT INTO gateways (tenant_id, type, name, credential_ref)
               VALUES (%s, %s, %s, %s)
               RETURNING id, tenant_id, type, name, credential_ref, status, created_at""",
            (tenant_id, type_, name, credential_ref),
        )
        return cur.fetchone()


def get_gateway(gateway_id: UUID) -> dict[str, Any] | None:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT id, tenant_id, type, name, credential_ref, status, created_at, rotated_at
               FROM gateways WHERE id = %s""",
            (gateway_id,),
        )
        return cur.fetchone()


def revoke_gateway(gateway_id: UUID) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE gateways SET status = 'revoked' WHERE id = %s", (gateway_id,))


def rotate_gateway_credential(gateway_id: UUID, new_credential_ref: str) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "UPDATE gateways SET credential_ref = %s, rotated_at = now() WHERE id = %s",
            (new_credential_ref, gateway_id),
        )


def list_gateways(tenant_id: UUID | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        if tenant_id:
            cur.execute(
                """SELECT id, tenant_id, type, name, status, created_at
                   FROM gateways WHERE tenant_id = %s ORDER BY created_at""",
                (tenant_id,),
            )
        else:
            cur.execute(
                "SELECT id, tenant_id, type, name, status, created_at FROM gateways ORDER BY created_at"
            )
        return cur.fetchall()


# ---- subagents ------------------------------------------------------------

def create_subagent(tenant_id: UUID, name: str, domain: str) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """INSERT INTO subagents (tenant_id, name, domain)
               VALUES (%s, %s, %s)
               RETURNING id, tenant_id, name, domain, status, created_at""",
            (tenant_id, name, domain),
        )
        return cur.fetchone()


def get_subagent(subagent_id: UUID) -> dict[str, Any] | None:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT id, tenant_id, name, domain, status, created_at FROM subagents WHERE id = %s",
            (subagent_id,),
        )
        return cur.fetchone()


def list_subagents(tenant_id: UUID | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        if tenant_id:
            cur.execute(
                "SELECT id, tenant_id, name, domain, status, created_at FROM subagents WHERE tenant_id = %s ORDER BY created_at",
                (tenant_id,),
            )
        else:
            cur.execute(
                "SELECT id, tenant_id, name, domain, status, created_at FROM subagents ORDER BY created_at"
            )
        return cur.fetchall()


# ---- behavior policy (por subagente) -------------------------------------
# Ver docs/design/0005-behavior-policy.md: qué es irreversible, cuándo pedir aprobación,
# reintentos y tono son configuración por subagente, no reglas fijas en el código.

def set_subagent_policy(subagent_id: UUID, policy: dict[str, Any]) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO subagent_policy (subagent_id, policy)
               VALUES (%s, %s)
               ON CONFLICT (subagent_id)
               DO UPDATE SET policy = EXCLUDED.policy, updated_at = now()""",
            (subagent_id, json.dumps(policy)),
        )


def get_subagent_policy(subagent_id: UUID) -> dict[str, Any]:
    """Devuelve la policy del subagente, o el default seguro si nunca se configuró
    (ver DEFAULT_POLICY en meridian.policy)."""
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            "SELECT policy, updated_at FROM subagent_policy WHERE subagent_id = %s",
            (subagent_id,),
        )
        row = cur.fetchone()
        return row["policy"] if row else {}


# ---- allowlist --------------------------------------------------------

def set_allowlist(gateway_id: UUID, subagent_id: UUID, allowed_intents: list[str]) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO gateway_subagent_allowlist (gateway_id, subagent_id, allowed_intents)
               VALUES (%s, %s, %s)
               ON CONFLICT (gateway_id, subagent_id)
               DO UPDATE SET allowed_intents = EXCLUDED.allowed_intents""",
            (gateway_id, subagent_id, allowed_intents),
        )


def get_allowlist_entry(gateway_id: UUID, subagent_id: UUID) -> dict[str, Any] | None:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT gateway_id, subagent_id, allowed_intents
               FROM gateway_subagent_allowlist WHERE gateway_id = %s AND subagent_id = %s""",
            (gateway_id, subagent_id),
        )
        return cur.fetchone()


def list_allowlist(gateway_id: UUID | None = None, subagent_id: UUID | None = None) -> list[dict[str, Any]]:
    query = "SELECT gateway_id, subagent_id, allowed_intents, created_at FROM gateway_subagent_allowlist WHERE 1=1"
    params: list[Any] = []
    if gateway_id:
        query += " AND gateway_id = %s"
        params.append(gateway_id)
    if subagent_id:
        query += " AND subagent_id = %s"
        params.append(subagent_id)
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        return cur.fetchall()


# ---- cron_jobs (gateway tipo cron, entregable 5) -------------------------

def create_cron_job(
    tenant_id: UUID,
    gateway_id: UUID,
    name: str,
    schedule: str,
    intent_type: str,
    subagent_ids: list[str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """INSERT INTO cron_jobs (tenant_id, gateway_id, name, schedule, intent_type, subagent_ids, payload)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               RETURNING id, tenant_id, gateway_id, name, schedule, intent_type, subagent_ids, payload, enabled, created_at""",
            (tenant_id, gateway_id, name, schedule, intent_type, subagent_ids, json.dumps(payload)),
        )
        return cur.fetchone()


def list_cron_jobs(tenant_id: UUID | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        if tenant_id:
            cur.execute(
                """SELECT id, tenant_id, gateway_id, name, schedule, intent_type, subagent_ids,
                          payload, enabled, last_run_at, created_at
                   FROM cron_jobs WHERE tenant_id = %s ORDER BY created_at""",
                (tenant_id,),
            )
        else:
            cur.execute(
                """SELECT id, tenant_id, gateway_id, name, schedule, intent_type, subagent_ids,
                          payload, enabled, last_run_at, created_at
                   FROM cron_jobs ORDER BY created_at"""
            )
        return cur.fetchall()


def list_enabled_cron_jobs() -> list[dict[str, Any]]:
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """SELECT cj.id, cj.tenant_id, cj.gateway_id, cj.name, cj.schedule, cj.intent_type,
                      cj.subagent_ids, cj.payload, cj.last_run_at, cj.created_at, g.type AS gateway_type
               FROM cron_jobs cj
               JOIN gateways g ON g.id = cj.gateway_id
               WHERE cj.enabled = true AND g.status = 'active'"""
        )
        return cur.fetchall()


def set_cron_job_enabled(cron_job_id: UUID, enabled: bool) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE cron_jobs SET enabled = %s WHERE id = %s", (enabled, cron_job_id))


def mark_cron_job_run(cron_job_id: UUID, ran_at) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE cron_jobs SET last_run_at = %s WHERE id = %s", (ran_at, cron_job_id))


# ---- audit --------------------------------------------------------------

def log_audit(
    tenant_id: UUID,
    correlation_id: UUID,
    message_id: UUID,
    agent_id: str,
    event_type: str,
    detail: dict[str, Any] | None = None,
) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO audit_log (tenant_id, correlation_id, message_id, agent_id, event_type, detail)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (tenant_id, correlation_id, message_id, agent_id, event_type, json.dumps(detail or {})),
        )


def tail_audit(tenant_id: UUID | None = None, correlation_id: UUID | None = None, limit: int = 50) -> list[dict[str, Any]]:
    query = "SELECT id, tenant_id, correlation_id, message_id, agent_id, event_type, detail, created_at FROM audit_log WHERE 1=1"
    params: list[Any] = []
    if tenant_id:
        query += " AND tenant_id = %s"
        params.append(tenant_id)
    if correlation_id:
        query += " AND correlation_id = %s"
        params.append(correlation_id)
    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    with get_conn() as conn, conn.cursor(row_factory=dict_row) as cur:
        cur.execute(query, params)
        return cur.fetchall()
