"""Operaciones sobre tenants/gateways/subagents/allowlist/audit_log -- vía SQLAlchemy Core
(ver `meridian.identity.schema_meta`), portable entre Postgres/MySQL/MSSQL (ver
docs/design/0017-database-compatibility.md).

Toda decisión de autorización del main (ver docs/design/0001-task-intent-schema.md,
sección 3) pasa por aquí -- nunca se confía en scopes que vengan en el mensaje entrante.

Los ids (UUID) se generan en Python y siempre se manejan como `str` -- ver el docstring de
`schema_meta.py` sobre por qué (portabilidad entre motores que no comparten un tipo UUID
nativo idéntico).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, insert, select, update

from meridian.identity import schema_meta as t
from meridian.identity.db import get_conn


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


def _row_to_dict(row) -> dict[str, Any]:
    return dict(row._mapping)


# ---- tenants ----------------------------------------------------------

def create_tenant(name: str) -> dict[str, Any]:
    row_id = _new_id()
    with get_conn() as conn:
        conn.execute(insert(t.tenants).values(id=row_id, name=name, status="active", created_at=_now()))
        row = conn.execute(select(t.tenants).where(t.tenants.c.id == row_id)).first()
        return _row_to_dict(row)


def list_tenants() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(select(t.tenants).order_by(t.tenants.c.created_at)).fetchall()
        return [_row_to_dict(r) for r in rows]


# ---- gateways -----------------------------------------------------------

def create_gateway(tenant_id, type_: str, name: str, credential_ref: str | None = None) -> dict[str, Any]:
    row_id = _new_id()
    with get_conn() as conn:
        conn.execute(insert(t.gateways).values(
            id=row_id, tenant_id=str(tenant_id), type=type_, name=name,
            credential_ref=credential_ref, status="active", created_at=_now(),
        ))
        row = conn.execute(select(t.gateways).where(t.gateways.c.id == row_id)).first()
        return _row_to_dict(row)


def get_gateway(gateway_id) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(select(t.gateways).where(t.gateways.c.id == str(gateway_id))).first()
        return _row_to_dict(row) if row else None


def revoke_gateway(gateway_id) -> None:
    with get_conn() as conn:
        conn.execute(update(t.gateways).where(t.gateways.c.id == str(gateway_id)).values(status="revoked"))


def rotate_gateway_credential(gateway_id, new_credential_ref: str) -> None:
    with get_conn() as conn:
        conn.execute(update(t.gateways).where(t.gateways.c.id == str(gateway_id)).values(
            credential_ref=new_credential_ref, rotated_at=_now(),
        ))


def list_gateways(tenant_id=None) -> list[dict[str, Any]]:
    query = select(t.gateways).order_by(t.gateways.c.created_at)
    if tenant_id:
        query = query.where(t.gateways.c.tenant_id == str(tenant_id))
    with get_conn() as conn:
        return [_row_to_dict(r) for r in conn.execute(query).fetchall()]


# ---- subagents ------------------------------------------------------------

def create_subagent(tenant_id, name: str, domain: str, parent_subagent_id=None) -> dict[str, Any]:
    row_id = _new_id()
    with get_conn() as conn:
        conn.execute(insert(t.subagents).values(
            id=row_id, tenant_id=str(tenant_id), name=name, domain=domain,
            status="active", parent_subagent_id=str(parent_subagent_id) if parent_subagent_id else None,
            created_at=_now(),
        ))
        row = conn.execute(select(t.subagents).where(t.subagents.c.id == row_id)).first()
        return _row_to_dict(row)


def get_subagent(subagent_id) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(select(t.subagents).where(t.subagents.c.id == str(subagent_id))).first()
        return _row_to_dict(row) if row else None


def list_subagents(tenant_id=None) -> list[dict[str, Any]]:
    query = select(t.subagents).order_by(t.subagents.c.created_at)
    if tenant_id:
        query = query.where(t.subagents.c.tenant_id == str(tenant_id))
    with get_conn() as conn:
        return [_row_to_dict(r) for r in conn.execute(query).fetchall()]


# ---- delegación subagente -> sub-subagente (ver docs/design/0014-sub-subagents.md) -----

def set_subagent_delegation_allowlist(parent_subagent_id, child_subagent_id, allowed_intents: list[str]) -> None:
    parent_id, child_id = str(parent_subagent_id), str(child_subagent_id)
    with get_conn() as conn:
        existing = conn.execute(
            select(t.subagent_subagent_allowlist).where(
                t.subagent_subagent_allowlist.c.parent_subagent_id == parent_id,
                t.subagent_subagent_allowlist.c.child_subagent_id == child_id,
            )
        ).first()
        if existing:
            conn.execute(
                update(t.subagent_subagent_allowlist)
                .where(
                    t.subagent_subagent_allowlist.c.parent_subagent_id == parent_id,
                    t.subagent_subagent_allowlist.c.child_subagent_id == child_id,
                )
                .values(allowed_intents=allowed_intents)
            )
        else:
            conn.execute(insert(t.subagent_subagent_allowlist).values(
                parent_subagent_id=parent_id, child_subagent_id=child_id,
                allowed_intents=allowed_intents, created_at=_now(),
            ))


def get_subagent_delegation_entry(parent_subagent_id, child_subagent_id) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            select(t.subagent_subagent_allowlist).where(
                t.subagent_subagent_allowlist.c.parent_subagent_id == str(parent_subagent_id),
                t.subagent_subagent_allowlist.c.child_subagent_id == str(child_subagent_id),
            )
        ).first()
        return _row_to_dict(row) if row else None


def list_subagent_delegation_allowlist(parent_subagent_id=None) -> list[dict[str, Any]]:
    query = select(t.subagent_subagent_allowlist)
    if parent_subagent_id:
        query = query.where(t.subagent_subagent_allowlist.c.parent_subagent_id == str(parent_subagent_id))
    with get_conn() as conn:
        return [_row_to_dict(r) for r in conn.execute(query).fetchall()]


# ---- aprobaciones pendientes (enforcement de subagent_policy) ----------------
# Ver docs/design/0013-policy-enforcement.md.

def create_pending_approval(tenant_id, correlation_id, subagent_id, intent: dict[str, Any], reason: str) -> dict[str, Any]:
    row_id = _new_id()
    with get_conn() as conn:
        conn.execute(insert(t.pending_approvals).values(
            id=row_id, tenant_id=str(tenant_id), correlation_id=str(correlation_id),
            subagent_id=str(subagent_id), intent=intent, status="pending", reason=reason,
            created_at=_now(),
        ))
        row = conn.execute(select(t.pending_approvals).where(t.pending_approvals.c.id == row_id)).first()
        return _row_to_dict(row)


def get_pending_approval(approval_id) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(select(t.pending_approvals).where(t.pending_approvals.c.id == str(approval_id))).first()
        return _row_to_dict(row) if row else None


def list_pending_approvals(status: str = "pending", tenant_id=None) -> list[dict[str, Any]]:
    query = select(t.pending_approvals).where(t.pending_approvals.c.status == status).order_by(t.pending_approvals.c.created_at)
    if tenant_id:
        query = query.where(t.pending_approvals.c.tenant_id == str(tenant_id))
    with get_conn() as conn:
        return [_row_to_dict(r) for r in conn.execute(query).fetchall()]


def decide_pending_approval(approval_id, status: str, decided_by: str) -> None:
    with get_conn() as conn:
        conn.execute(update(t.pending_approvals).where(t.pending_approvals.c.id == str(approval_id)).values(
            status=status, decided_at=_now(), decided_by=decided_by,
        ))


# ---- behavior policy (por subagente) -------------------------------------
# Ver docs/design/0005-behavior-policy.md.

def set_subagent_policy(subagent_id, policy: dict[str, Any]) -> None:
    sid = str(subagent_id)
    with get_conn() as conn:
        existing = conn.execute(select(t.subagent_policy).where(t.subagent_policy.c.subagent_id == sid)).first()
        if existing:
            conn.execute(update(t.subagent_policy).where(t.subagent_policy.c.subagent_id == sid).values(
                policy=policy, updated_at=_now(),
            ))
        else:
            conn.execute(insert(t.subagent_policy).values(subagent_id=sid, policy=policy, updated_at=_now()))


def get_subagent_policy(subagent_id) -> dict[str, Any]:
    """Devuelve la policy del subagente, o {} si nunca se configuró (el caller decide el
    default seguro -- ver `meridian.policy.resolve_policy`)."""
    with get_conn() as conn:
        row = conn.execute(select(t.subagent_policy.c.policy).where(t.subagent_policy.c.subagent_id == str(subagent_id))).first()
        return row[0] if row else {}


# ---- LLM provider config (por subagente) ---------------------------------
# Ver docs/design/0009-llm-provider-layer.md.

def set_subagent_llm_config(subagent_id, provider: str, model: str, credential_ref: str) -> None:
    sid = str(subagent_id)
    with get_conn() as conn:
        existing = conn.execute(select(t.subagent_llm_config).where(t.subagent_llm_config.c.subagent_id == sid)).first()
        if existing:
            conn.execute(update(t.subagent_llm_config).where(t.subagent_llm_config.c.subagent_id == sid).values(
                provider=provider, model=model, credential_ref=credential_ref, updated_at=_now(),
            ))
        else:
            conn.execute(insert(t.subagent_llm_config).values(
                subagent_id=sid, provider=provider, model=model, credential_ref=credential_ref, updated_at=_now(),
            ))


def get_subagent_llm_config(subagent_id) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(select(t.subagent_llm_config).where(t.subagent_llm_config.c.subagent_id == str(subagent_id))).first()
        return _row_to_dict(row) if row else None


# ---- allowlist --------------------------------------------------------

def set_allowlist(gateway_id, subagent_id, allowed_intents: list[str]) -> None:
    gid, sid = str(gateway_id), str(subagent_id)
    with get_conn() as conn:
        existing = conn.execute(
            select(t.gateway_subagent_allowlist).where(
                t.gateway_subagent_allowlist.c.gateway_id == gid,
                t.gateway_subagent_allowlist.c.subagent_id == sid,
            )
        ).first()
        if existing:
            conn.execute(
                update(t.gateway_subagent_allowlist)
                .where(t.gateway_subagent_allowlist.c.gateway_id == gid, t.gateway_subagent_allowlist.c.subagent_id == sid)
                .values(allowed_intents=allowed_intents)
            )
        else:
            conn.execute(insert(t.gateway_subagent_allowlist).values(
                gateway_id=gid, subagent_id=sid, allowed_intents=allowed_intents, created_at=_now(),
            ))


def get_allowlist_entry(gateway_id, subagent_id) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            select(t.gateway_subagent_allowlist).where(
                t.gateway_subagent_allowlist.c.gateway_id == str(gateway_id),
                t.gateway_subagent_allowlist.c.subagent_id == str(subagent_id),
            )
        ).first()
        return _row_to_dict(row) if row else None


def list_allowlist(gateway_id=None, subagent_id=None) -> list[dict[str, Any]]:
    query = select(t.gateway_subagent_allowlist)
    if gateway_id:
        query = query.where(t.gateway_subagent_allowlist.c.gateway_id == str(gateway_id))
    if subagent_id:
        query = query.where(t.gateway_subagent_allowlist.c.subagent_id == str(subagent_id))
    with get_conn() as conn:
        return [_row_to_dict(r) for r in conn.execute(query).fetchall()]


# ---- cron_jobs (gateway tipo cron, entregable 5) -------------------------

def create_cron_job(tenant_id, gateway_id, name: str, schedule: str, intent_type: str, subagent_ids: list[str], payload: dict[str, Any]) -> dict[str, Any]:
    row_id = _new_id()
    with get_conn() as conn:
        conn.execute(insert(t.cron_jobs).values(
            id=row_id, tenant_id=str(tenant_id), gateway_id=str(gateway_id), name=name,
            schedule=schedule, intent_type=intent_type, subagent_ids=list(subagent_ids),
            payload=payload, enabled=True, created_at=_now(),
        ))
        row = conn.execute(select(t.cron_jobs).where(t.cron_jobs.c.id == row_id)).first()
        return _row_to_dict(row)


def list_cron_jobs(tenant_id=None) -> list[dict[str, Any]]:
    query = select(t.cron_jobs).order_by(t.cron_jobs.c.created_at)
    if tenant_id:
        query = query.where(t.cron_jobs.c.tenant_id == str(tenant_id))
    with get_conn() as conn:
        return [_row_to_dict(r) for r in conn.execute(query).fetchall()]


def list_enabled_cron_jobs() -> list[dict[str, Any]]:
    query = (
        select(
            t.cron_jobs.c.id, t.cron_jobs.c.tenant_id, t.cron_jobs.c.gateway_id, t.cron_jobs.c.name,
            t.cron_jobs.c.schedule, t.cron_jobs.c.intent_type, t.cron_jobs.c.subagent_ids,
            t.cron_jobs.c.payload, t.cron_jobs.c.last_run_at, t.cron_jobs.c.created_at,
            t.gateways.c.type.label("gateway_type"),
        )
        .join(t.gateways, t.gateways.c.id == t.cron_jobs.c.gateway_id)
        .where(t.cron_jobs.c.enabled == True, t.gateways.c.status == "active")  # noqa: E712
    )
    with get_conn() as conn:
        return [_row_to_dict(r) for r in conn.execute(query).fetchall()]


def set_cron_job_enabled(cron_job_id, enabled: bool) -> None:
    with get_conn() as conn:
        conn.execute(update(t.cron_jobs).where(t.cron_jobs.c.id == str(cron_job_id)).values(enabled=enabled))


def mark_cron_job_run(cron_job_id, ran_at) -> None:
    with get_conn() as conn:
        conn.execute(update(t.cron_jobs).where(t.cron_jobs.c.id == str(cron_job_id)).values(last_run_at=ran_at))


# ---- audit --------------------------------------------------------------

def log_audit(tenant_id, correlation_id, message_id, agent_id: str, event_type: str, detail: dict[str, Any] | None = None) -> None:
    with get_conn() as conn:
        conn.execute(insert(t.audit_log).values(
            tenant_id=str(tenant_id), correlation_id=str(correlation_id), message_id=str(message_id),
            agent_id=agent_id, event_type=event_type, detail=detail or {}, created_at=_now(),
        ))


def prune_audit_log(older_than_days: int) -> int:
    """Borra entradas de audit_log más viejas que `older_than_days`. Ver
    docs/design/0008-observability.md para la política de retención por defecto (90 días)."""
    from datetime import timedelta
    cutoff = _now() - timedelta(days=older_than_days)
    with get_conn() as conn:
        result = conn.execute(delete(t.audit_log).where(t.audit_log.c.created_at < cutoff))
        return result.rowcount


def tail_audit(tenant_id=None, correlation_id=None, limit: int = 50) -> list[dict[str, Any]]:
    query = select(t.audit_log).order_by(t.audit_log.c.created_at.desc()).limit(limit)
    if tenant_id:
        query = query.where(t.audit_log.c.tenant_id == str(tenant_id))
    if correlation_id:
        query = query.where(t.audit_log.c.correlation_id == str(correlation_id))
    with get_conn() as conn:
        return [_row_to_dict(r) for r in conn.execute(query).fetchall()]
