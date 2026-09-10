"""Logging estructurado compartido por todos los procesos de Meridian (main, gateways,
subagentes, CLI). Ver docs/design/0008-observability.md.

Decisión: JSON lines a stdout, capturado por `docker logs`/journald/lo que sea -- sin
integración con Prometheus/OTel todavía (no hay un requisito concreto que la justifique;
agregarla ahora sería diseñar para un futuro hipotético). El registro durable y consultable
de "quién pidió qué y por qué se delegó" ya es `audit_log` en Postgres (sección 5 del
brief) -- estos logs son para depuración operativa, no reemplazan la auditoría.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra_fields", None)
        if extra:
            payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)


def configure(component: str, level: int = logging.INFO) -> logging.Logger:
    """Configura logging JSON a stdout para un proceso de Meridian. `component` identifica
    el proceso (ej. 'main_agent', 'cron_gateway', 'subagent:<id>') en cada línea de log."""
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    return logging.getLogger(component)
